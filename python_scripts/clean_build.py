"""Build locked sources in a fresh checkout and conda prefix, preserving this workspace."""
from __future__ import annotations
import argparse
import hashlib
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import traceback
import uuid

ROOT=Path(__file__).resolve().parents[1]
FIRST_PARTY=('src','analysis','notebook','python_scripts','scripts','config','docs','prompts','tests','reference_modules')
ROOT_FILES=('CMakeLists.txt','pyproject.toml','requirements.lock.txt','environment.conda.lock.txt','README.md','AGENTS.md','STATUS.md')


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output_root',help='Parent for a new isolated acceptance build')
    parser.add_argument('--conda',default='conda',help='Conda executable, default resolved from PATH')
    args=parser.parse_args()
    base=Path(args.output_root).resolve()/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'_'+uuid.uuid4().hex[:10])
    base.mkdir(parents=True,exist_ok=False); workspace=base/'workspace'; prefix=base/'envs/search_decimation'
    record={'status':'incomplete','workspace':str(workspace),'prefix':str(prefix),'commands':[],
        'isolation':'new conda prefix; new pinned Git checkouts; no copied native binaries, wheels, build directories or circuit cache'}
    def save(): (base/'build.json').write_text(json.dumps(record,indent=2,allow_nan=False)+'\n')
    def run(command, *, cwd=ROOT, env=None):
        record['commands'].append({'argv':command,'cwd':str(cwd) });save()
        with (base/'build.log').open('a') as log:
            subprocess.run(command,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
    save(); print(base,flush=True)
    try:
        workspace.mkdir()
        for name in FIRST_PARTY:
            shutil.copytree(ROOT/name,workspace/name,
                            ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.so','*.o','*.a','*.whl','build','dist'))
        for name in ROOT_FILES: shutil.copyfile(ROOT/name,workspace/name)
        for name in ('assets','simulation_data'):
            (workspace/name).mkdir();shutil.copyfile(ROOT/name/'README.md',workspace/name/'README.md')
        (workspace/'external_lib').mkdir()
        for name in ('manifest.lock.json','README.md'): shutil.copyfile(ROOT/'external_lib'/name,workspace/'external_lib'/name)
        shutil.copytree(ROOT/'external_lib/patches',workspace/'external_lib/patches')
        lock=json.loads((ROOT/'external_lib/manifest.lock.json').read_text())
        for name,dependency in lock['dependencies'].items():
            source=ROOT/'external_lib'/name; target=workspace/'external_lib'/name
            if source.is_dir(): run(['git','clone','--no-local',str(source),str(target)])
            else: run(['git','clone',dependency['url'],str(target)])
            run(['git','-C',str(target),'checkout','--detach',dependency['commit']])
            run(['git','-C',str(target),'remote','set-url','origin',dependency['url']])
            if list(target.rglob('*.so')): raise ValueError(f'{name} clone contains unexpected prebuilt native binaries')
            patch=workspace/dependency['patch_file']
            if sha(patch)!=dependency['patch_sha256']:
                raise ValueError(f'{name} patch differs from locked digest')
            if patch.stat().st_size:
                run(['git','apply','--check',str(patch)],cwd=target)
                run(['git','apply',str(patch)],cwd=target)
            for relative,expected in dependency['source_hashes'].items():
                source_file=target/relative
                if not source_file.is_file() or sha(source_file)!=expected:
                    raise ValueError(f'{name} source restoration mismatch: {relative}')
        ldpc=workspace/'external_lib/ldpc'
        run(['git','remote','add','upstream',lock['dependencies']['ldpc']['upstream_remote']],cwd=ldpc)
        run([args.conda,'create','--yes','--prefix',str(prefix),'--file',str(ROOT/'environment.conda.lock.txt')])
        env=dict(os.environ,PATH=str(prefix/'bin')+os.pathsep+os.environ['PATH'],PYTHONNOUSERSITE='1',PIP_NO_CACHE_DIR='1',
                 OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
        env.pop('PYTHONPATH',None)
        python=str(prefix/'bin/python')
        run([python,'python_scripts/build_dependencies.py'],cwd=workspace,env=env)
        for binding in ('setup_reference.py','setup_hybrid.py','setup_af_bp.py'):
            run([python,binding,'build_ext','--inplace'],cwd=ldpc,env=env)
        # Build Stim from its pinned source; the wheel installed by the lock
        # only bootstraps Python dependencies. Its extensions share object paths.
        stim=workspace/'external_lib/Stim'
        run([python,'setup.py','build_ext','--inplace','--force'],cwd=stim,env=env)
        wheel_dir=workspace/'external_lib/wheels';wheel_dir.mkdir()
        run([python,'-m','pip','wheel','--no-build-isolation','--no-deps',str(stim),'-w',str(wheel_dir)],cwd=workspace,env=env)
        wheels=list(wheel_dir.glob('stim-*.whl'))
        if len(wheels)!=1: raise ValueError('Expected exactly one pinned Stim wheel')
        run([python,'-m','pip','install','--force-reinstall','--no-deps',str(wheels[0])],cwd=workspace,env=env)
        # The active BP-OSD regression imports an independent pristine ldpc
        # installation by PYTHONPATH. Build that exact pin without fork patches.
        pristine_source=workspace/'external_lib/pristine_ldpc_source'
        pristine_target=workspace/'external_lib/pristine_ldpc'
        run(['git','clone','--no-local',str(ldpc),str(pristine_source)])
        run(['git','-C',str(pristine_source),'checkout','--detach',lock['dependencies']['ldpc']['commit']])
        if list(pristine_source.rglob('*.so')):
            raise ValueError('pristine ldpc clone contains a prebuilt native binary')
        run([python,'-m','pip','wheel','--no-build-isolation','--no-deps',str(pristine_source),
             '-w',str(wheel_dir)],cwd=workspace,env=env)
        pristine_wheels=list(wheel_dir.glob('ldpc-*.whl'))
        if len(pristine_wheels)!=1: raise ValueError('Expected exactly one pristine ldpc wheel')
        run([python,'-m','pip','install','--no-deps','--ignore-installed',
             '--target',str(pristine_target),str(pristine_wheels[0])],cwd=workspace,env=env)
        pristine_env=dict(env,PYTHONPATH=str(pristine_target))
        run([python,'-c',
             'import ldpc; from pathlib import Path; '
             f'assert Path(ldpc.__file__).resolve().is_relative_to(Path({str(pristine_target)!r}))'],
            cwd=workspace,env=pristine_env)
        run([python,'python_scripts/audit_dependencies.py'],cwd=workspace,env=env)
        audited=json.loads((workspace/'external_lib/manifest.lock.json').read_text())
        for name,expected in lock['dependencies'].items():
            current=audited['dependencies'][name]
            for field in ('commit','source_hashes','patch_sha256'):
                if current[field]!=expected[field]:
                    raise ValueError(f'{name} audited {field} differs from lock')
        run([python,'-c',
             'from qec_bp_benchmark.af_bp_service import build_identity, source_digest; '
             'assert build_identity()["source_sha256"] == source_digest()'],cwd=workspace,env=env)
        run([python,'python_scripts/build_dependencies.py','--check'],cwd=workspace,env=env)
        run([python,'-m','pip','check'],cwd=workspace,env=env)
        record['status']='complete'; save()
    except BaseException as error:
        record['error']={'type':type(error).__name__,'message':str(error)};save()
        (base/'exception.txt').write_text(traceback.format_exc());raise


if __name__=='__main__': main()
