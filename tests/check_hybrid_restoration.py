"""Restore the audited ldpc patch and build both opt-in bindings and project anew.

Run with search_decimation. Uses an isolated source tree with no old binaries;
other installed dependencies/environment are reused. Never changes working sources.
"""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def main() -> None:
    """Verify every locked source, compile and execute fresh bindings/native tests.

    Raises on missing patch bytes, source/build hash mismatch, compile or test
    failure. The temporary Git worktree is removed even after a failing check.
    """
    manifest=json.loads((ROOT/'external_lib/manifest.lock.json').read_text())['dependencies']['ldpc']
    patch=ROOT/manifest['patch_file']
    assert hashlib.sha256(patch.read_bytes()).hexdigest()==manifest['patch_sha256']
    with tempfile.TemporaryDirectory(prefix='qec-hybrid-restore-') as temporary:
        project=Path(temporary)/'project'; project.mkdir()
        shutil.copyfile(ROOT/'CMakeLists.txt',project/'CMakeLists.txt')
        shutil.copytree(ROOT/'src',project/'src',ignore=shutil.ignore_patterns('*.so','__pycache__','*.pyc'))
        shutil.copytree(ROOT/'tests/native',project/'tests/native')
        checkout=project/'external_lib/ldpc';checkout.parent.mkdir()
        subprocess.run(['git','-C',str(ROOT/'external_lib/ldpc'),'worktree','add','--detach',str(checkout),manifest['commit']],check=True)
        try:
            subprocess.run(['git','-C',str(checkout),'apply',str(patch)],check=True)
            for name,expected in manifest['source_hashes'].items():
                assert hashlib.sha256((checkout/name).read_bytes()).hexdigest()==expected,name
            assert not list(project.rglob('*.so'))
            for setup in ('setup_reference.py','setup_hybrid.py'):
                subprocess.run([sys.executable,setup,'build_ext','--inplace'],cwd=checkout,check=True)
            program='''
from pathlib import Path
import hashlib
import importlib.util
import runpy
root=Path.cwd()
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
module=load('_hybrid_bp',next((root/'src_python/ldpc/hybrid_bp').glob('_hybrid_bp*.so')))
sources=runpy.run_path(str(root/'src_python/ldpc/hybrid_bp/source_files.py'))
assert module.build_identity()['source_sha256']==sources['source_digest'](root)
reference=load('_reference_bp',next((root/'src_python/ldpc/reference_bp').glob('_reference_bp*.so')))
digest=hashlib.sha256()
for name in ('src_cpp/reference_bp.hpp','src_python/ldpc/reference_bp/bindings.cpp','src_python/ldpc/reference_bp/__init__.py','setup_reference.py'):
    digest.update(name.encode()+b'\\0'+(root/name).read_bytes())
assert reference.build_identity()['source_sha256']==digest.hexdigest()
session=module.StatefulMinSumSession([[0],[0]],1,[.1])
session.reset([1,1]);session.replace_hint([(0,0)],8)
assert session.advance(1).valid and session.snapshot().decision==[1]
osd=module.Osd0Bridge([[0],[0]],1,[.1])
assert osd.decode([1,1],[-2]).valid and not osd.decode([1,0],[-2]).valid
print('Both restored bindings, complete source digests, stateful BP and direct OSD passed')
'''
            subprocess.run([sys.executable,'-c',program],cwd=checkout,check=True)
            import pybind11
            build=project/'build'
            subprocess.run(['cmake','-S',str(project),'-B',str(build),'-DCMAKE_BUILD_TYPE=Release',
                '-DQEC_BUILD_TESTS=ON',f'-DPython_EXECUTABLE={sys.executable}',f'-Dpybind11_DIR={pybind11.get_cmake_dir()}'],check=True)
            subprocess.run(['cmake','--build',str(build),'--target','_native','test_reference_bp','test_search','test_hybrid_bp','test_hybrid','-j2'],check=True)
            subprocess.run(['ctest','--test-dir',str(build),'--output-on-failure'],check=True)
            program='''
from pathlib import Path
import importlib.util
import runpy
root=Path.cwd()
path=next((root/'build').glob('_native*.so'))
spec=importlib.util.spec_from_file_location('_native',path)
native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
project=runpy.run_path(str(root/'src/qec_bp_benchmark/native_sources.py'))
fork=runpy.run_path(str(root/'external_lib/ldpc/src_python/ldpc/hybrid_bp/source_files.py'))
identity=native.hybrid_source_identity()
assert identity['project_sha256']==project['hybrid_project_digest'](root)
assert identity['fork_sha256']==fork['source_digest'](root/'external_lib/ldpc')
decoder=native.HybridDecoder([[0],[0]],1,[.1],[[0]],native.HybridSettings())
result=decoder.decode([1,1],True)
assert result.valid and result.correction==[1] and result.prediction==[1]
assert decoder.export_telemetry()['phases']
print('Fresh project extension source/build identities and complete native hybrid service passed')
'''
            subprocess.run([sys.executable,'-c',program],cwd=project,check=True)
        finally:
            subprocess.run(['git','-C',str(ROOT/'external_lib/ldpc'),'worktree','remove','--force',str(checkout)],check=True)


if __name__=='__main__': main()
