"""Build or verify local pinned dependencies; does not publish sources or run experiments."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import site
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
OPT_IN_FORK_FILES = (
    'src_cpp/reference_bp.hpp', 'src_python/ldpc/reference_bp/bindings.cpp',
    'src_python/ldpc/reference_bp/__init__.py', 'setup_reference.py',
    'src_cpp/hybrid_graph.hpp', 'src_cpp/stateful_min_sum.hpp', 'src_cpp/decimated_bp.hpp',
    'src_cpp/osd0_bridge.hpp', 'src_python/ldpc/hybrid_bp/bindings.cpp',
    'src_python/ldpc/hybrid_bp/__init__.py', 'src_python/ldpc/hybrid_bp/__init__.pyi',
    'src_python/ldpc/hybrid_bp/source_files.py', 'setup_hybrid.py',
)


def run(*args: str, cwd: Path=ROOT) -> None:
    subprocess.run(args,cwd=cwd,check=True)


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true',help='Only verify installed native imports and pins')
    args=parser.parse_args()
    if Path(sys.prefix).name!='search_decimation':
        raise RuntimeError('Run this command in conda environment search_decimation')
    manifest=json.loads((ROOT/'external_lib/manifest.lock.json').read_text())
    for name,record in manifest['dependencies'].items():
        path=ROOT/'external_lib'/name
        if not path.exists():
            if args.check: raise RuntimeError(f'Missing checkout: {name}')
            run('git','clone',record['url'],str(path))
            run('git','checkout','--detach',record['commit'],cwd=path)
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=path,text=True).strip()
        if commit!=record['commit']:
            raise RuntimeError(f'Checkout {name} differs from pinned commit; preserve changes before restoring it')
    if args.check:
        from qec_bp_benchmark.bp import verified_backend, verified_hybrid_backend
        import beam_search_decoder,stim,qldpc,ldpc
        print(json.dumps({'reference_bp':verified_backend().build_identity(),'hybrid_bp':verified_hybrid_backend().build_identity(),'ldpc':ldpc.__file__,
              'beam':beam_search_decoder.__file__,'stim':stim.__version__,'qldpc':qldpc.__file__},indent=2))
        return
    pip=[sys.executable,'-m','pip']
    run(*pip,'install','-r','requirements.lock.txt')
    fork=ROOT/'external_lib/ldpc'
    # Build pristine source separately, so local opt-in additions cannot enter it.
    pristine_source=ROOT/'external_lib/pristine_ldpc_source'
    wheel_dir=ROOT/'external_lib/wheels'
    wheel_dir.mkdir(exist_ok=True)
    pristine_wheels=list(wheel_dir.glob('ldpc-2.4.1-*.whl'))
    if not pristine_wheels:
        if not pristine_source.exists():
            run('git','worktree','add','--detach',str(pristine_source),manifest['dependencies']['ldpc']['commit'],cwd=fork)
        run(*pip,'wheel','--no-build-isolation','--no-deps',str(pristine_source),'-w',str(wheel_dir))
        pristine_wheels=list(wheel_dir.glob('ldpc-2.4.1-*.whl'))
    if len(pristine_wheels)!=1: raise RuntimeError('Expected one pristine ldpc wheel')
    reference=ROOT/'external_lib/pristine_ldpc'
    if not reference.exists():
        run(*pip,'install','--no-deps','--target',str(reference),str(pristine_wheels[0]))
    # Restore each missing opt-in file independently, preserving existing user
    # edits and recovering incomplete patch installations without overwriting.
    for name in OPT_IN_FORK_FILES:
        if not (fork/name).exists():
            run('git','apply','--include='+name,str(ROOT/'external_lib/patches/ldpc.patch'),cwd=fork)
            if not (fork/name).is_file(): raise RuntimeError(f'Locked patch does not restore {name}')
    remotes=subprocess.check_output(['git','remote'],cwd=fork,text=True).splitlines()
    if 'upstream' not in remotes: run('git','remote','add','upstream',manifest['dependencies']['ldpc']['url'],cwd=fork)
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=fork,text=True).strip()
    if branch!='screened-decimation-bp':
        branches=subprocess.check_output(['git','branch','--list','screened-decimation-bp'],cwd=fork,text=True).strip()
        if branches:
            existing=subprocess.check_output(['git','rev-parse','screened-decimation-bp'],cwd=fork,text=True).strip()
            if existing!=manifest['dependencies']['ldpc']['commit']:
                raise RuntimeError('Existing development branch has different commits; preserve it before restoring the pin')
            run('git','checkout','screened-decimation-bp',cwd=fork)
        else:
            run('git','checkout','-b','screened-decimation-bp',cwd=fork)
    run(*pip,'install','--no-build-isolation','--no-deps','-e',str(fork))
    run(sys.executable,'setup_reference.py','build_ext','--inplace',cwd=fork)
    run(sys.executable,'setup_hybrid.py','build_ext','--inplace',cwd=fork)
    run(*pip,'install','--no-build-isolation','--no-deps','-e','external_lib/qLDPC')
    beam=ROOT/'external_lib/BeamSearchDecoder/decoder'
    run(sys.executable,'setup.py','build_ext','--inplace',cwd=beam)
    (Path(site.getsitepackages()[0])/'beam_search_baseline.pth').write_text(str(beam)+'\n')
    run(*pip,'wheel','--no-build-isolation','--no-deps','external_lib/Stim','-w',str(wheel_dir))
    stim_wheels=list(wheel_dir.glob('stim-1.16.0-*.whl'))
    if len(stim_wheels)!=1: raise RuntimeError('Expected one pinned Stim wheel')
    run(*pip,'install','--force-reinstall','--no-deps',str(stim_wheels[0]))
    run(*pip,'install','--no-build-isolation','--no-deps','-e','.')
    run(sys.executable,'python_scripts/build_dependencies.py','--check')


if __name__=='__main__':
    main()
