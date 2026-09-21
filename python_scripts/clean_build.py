"""Build locked sources in a fresh checkout and conda prefix, preserving this workspace."""
from __future__ import annotations
import argparse
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
        run([args.conda,'create','--yes','--prefix',str(prefix),'--file',str(ROOT/'environment.conda.lock.txt')])
        env=dict(os.environ,PATH=str(prefix/'bin')+os.pathsep+os.environ['PATH'],PYTHONNOUSERSITE='1',PIP_NO_CACHE_DIR='1',
                 OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
        env.pop('PYTHONPATH',None)
        python=str(prefix/'bin/python')
        run([python,'python_scripts/build_dependencies.py'],cwd=workspace,env=env)
        run([python,'python_scripts/audit_dependencies.py'],cwd=workspace,env=env)
        run([python,'python_scripts/build_dependencies.py','--check'],cwd=workspace,env=env)
        run([python,'-m','pip','check'],cwd=workspace,env=env)
        record['status']='complete'; save()
    except BaseException as error:
        record['error']={'type':type(error).__name__,'message':str(error)};save()
        (base/'exception.txt').write_text(traceback.format_exc());raise


if __name__=='__main__': main()
