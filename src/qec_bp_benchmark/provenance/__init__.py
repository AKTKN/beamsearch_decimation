"""Preserve actual source bytes, dirty patches, worktree identity and native builds."""
from __future__ import annotations
import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import zipfile
from ..storage import atomic_json,sha256
from ..identity import content_hash

ROOT=Path(__file__).resolve().parents[3]
SOURCE_SUFFIXES={'.pyi','.py','.pyx','.pxd','.pxi','.hpp','.h','.c','.cc','.cpp','.cmake','.toml','.txt','.md','.yaml','.yml','.json','.sh','.ipynb'}


def repository_state(path: Path) -> dict:
    """Inspect .git directories or files; absence is explicit, never a fake revision."""
    if not (path/'.git').exists(): return {'commit':None,'status':'not a Git repository','dirty':None}
    def git(*args): return subprocess.check_output(['git','-C',str(path),*args],text=True).strip()
    status=git('status','--porcelain')
    return {'commit':git('rev-parse','HEAD'),'branch':git('branch','--show-current'),'dirty':bool(status),
            'status':status,'git_metadata_kind':'file' if (path/'.git').is_file() else 'directory'}


def timer_diagnostics() -> dict:
    """Clock metadata and 101 empty-call deltas in integer ns; no subtraction."""
    results={}
    for name,fn in [('process_time',time.process_time_ns),('perf_counter',time.perf_counter_ns)]:
        values=[]
        for _ in range(101):
            start=fn(); values.append(fn()-start)
        info=time.get_clock_info(name)
        results[name]={'resolution_seconds':info.resolution,'implementation':info.implementation,
            'monotonic':info.monotonic,'adjustable':info.adjustable,'empty_call_ns':values}
    results['native']={'cpu':'CLOCK_PROCESS_CPUTIME_ID','wall':'CLOCK_MONOTONIC',
        'cpu_resolution_seconds':time.clock_getres(time.CLOCK_PROCESS_CPUTIME_ID),
        'wall_resolution_seconds':time.clock_getres(time.CLOCK_MONOTONIC),'residual_tolerance_ns':0,
        'libc':platform.libc_ver()}
    return results


def capture(destination: Path, execution: dict) -> dict:
    """Archive relevant first-party/dependency bytes and preserve dirty Git patches.

    Native paths/hashes and source revisions are provenance; ZIP hashes address the
    actual preserved content. Does not capture arbitrary environment variables.
    """
    from threadpoolctl import threadpool_info
    destination.mkdir(exist_ok=False)
    files=set()
    for directory in ('src','analysis','notebook','python_scripts','scripts','config','docs','prompts','tests','reference_modules'):
        for path in (ROOT/directory).rglob('*'):
            source_name = path.with_suffix('') if path.suffix == '.example' else path
            if path.is_file() and source_name.suffix in SOURCE_SUFFIXES and not any(x in path.parts for x in ('__pycache__','test_results')):
                files.add(path)
    for name in ('CMakeLists.txt','pyproject.toml','requirements.lock.txt','environment.conda.lock.txt','README.md','AGENTS.md','STATUS.md','external_lib/manifest.lock.json'):
        files.add(ROOT/name)
    files.update((ROOT/'external_lib/patches').glob('*.patch'))
    repos={'project':repository_state(ROOT)}
    # Keep source trees in the run, including relevant untracked headers/bindings;
    # exclude build products, wheels and unrelated third-party nested checkouts.
    manifest=json.loads((ROOT/'external_lib/manifest.lock.json').read_text())
    for name in manifest['dependencies']:
        path=ROOT/'external_lib'/name
        if not (path/'.git').exists(): continue
        repos[name]=repository_state(path)
        patch=subprocess.check_output(['git','-C',str(path),'diff','--binary','HEAD'])
        (destination/f'{name}.patch').write_bytes(patch)
        repos[name]['patch_sha256']=hashlib.sha256(patch).hexdigest()
        listed=set(subprocess.check_output(['git','-C',str(path),'ls-files','--cached','--others','--exclude-standard','-z']).decode().split('\0'))
        # Audited authored sources can match upstream ignores (the pybind .cpp
        # does). Preserve these exact bytes as well as the ordinary Git inventory.
        listed.update(manifest['dependencies'][name].get('source_hashes',{}))
        for relative in sorted(listed):
            source=path/relative
            if relative and source.is_file() and (source.suffix in SOURCE_SUFFIXES or source.name.startswith(('LICENSE','COPYING'))):
                if not any(part in ('build','dist','__pycache__') for part in Path(relative).parts): files.add(source)
    if repos['project']['commit'] is not None:
        (destination/'project.patch').write_bytes(subprocess.check_output(['git','-C',str(ROOT),'diff','--binary','HEAD']))
    hashes={}
    with zipfile.ZipFile(destination/'sources.zip','x',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            payload=path.read_bytes(); name=str(path.relative_to(ROOT))
            hashes[name]=hashlib.sha256(payload).hexdigest(); archive.writestr(name,payload)
    atomic_json(destination/'source_hashes.json',hashes,exclusive=True)
    modules={}
    for name in ('qec_bp_benchmark._native','ldpc','ldpc.reference_bp._reference_bp',
                 'ldpc.hybrid_bp._hybrid_bp','ldpc.bposd_decoder._bposd_decoder','beam_search_decoder._beam_search_decoder','qldpc','stim','pyarrow'):
        module=importlib.import_module(name); path=Path(module.__file__).resolve()
        modules[name]={'path':str(path),'sha256':sha256(path)}
    compiler=subprocess.check_output(['c++','--version'],text=True).splitlines()[0]
    cpu_info=Path('/proc/cpuinfo').read_text() if Path('/proc/cpuinfo').exists() else platform.processor()
    cpu_model=next((line.split(':',1)[1].strip() for line in cpu_info.splitlines() if line.startswith('model name')),platform.processor())
    environment={'python':sys.version,'executable':sys.executable,'prefix':sys.prefix,'platform':platform.platform(),
        'cpu_model':cpu_model,'cpu_count':os.cpu_count(),'execution':execution,'threadpools':threadpool_info(),
        'dependencies':{d.metadata['Name']:d.version for d in importlib.metadata.distributions() if d.metadata['Name']},
        'native_modules':modules,'compiler':compiler,'project_flags':['Release','C++17','-fno-fast-math','-ffp-contract=off'],
        'dependency_build_details':'source_provenance/sources.zip:external_lib/manifest.lock.json',
        'repositories':repos,'timers':timer_diagnostics(),'argv':sys.argv}
    atomic_json(destination.parent/'environment.json',environment,exclusive=True)
    return {'source_hash':content_hash(hashes),'archive_sha256':sha256(destination/'sources.zip'),
            'source_files':len(hashes),'environment_sha256':sha256(destination.parent/'environment.json')}
