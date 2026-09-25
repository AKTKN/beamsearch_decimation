"""Capture pinned source/import/build identities and exact local patches."""
from __future__ import annotations
import hashlib
import importlib
import importlib.metadata
import json
from pathlib import Path
import platform
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "ldpc": ("https://github.com/quantumgizmos/ldpc", "ldpc", "MIT", "BP and BP-OSD; opt-in flooding and stateful hybrid interfaces"),
    "BeamSearchDecoder": ("https://github.com/ionq-publications/BeamSearchDecoder", "beam_search_decoder", "CC-BY-NC-SA-4.0; bundled ldpc components MIT", "Published beam baseline"),
    "qLDPC": ("https://github.com/qLDPCOrg/qLDPC", "qldpc", "Apache-2.0", "BB72 construction, edge-coloring memory and noise"),
    "Stim": ("https://github.com/quantumlib/Stim", "stim", "Apache-2.0", "Physical circuit sampling and undecomposed DEM"),
    "BivariateBicycleCodes": ("https://github.com/sbravyi/BivariateBicycleCodes", None, "Apache-2.0", "Algebra and original schedule reference; not executed"),
    "stimbposd": ("https://github.com/oscarhiggott/stimbposd", None, "Apache-2.0", "Converter comparison source; project implements conversion"),
}
PATHS = {
    'ldpc': ['src_cpp/bp.hpp','src_cpp/osd.hpp','src_cpp/reference_bp.hpp','src_python/ldpc/reference_bp','setup.py','setup_reference.py'],
    'BeamSearchDecoder': ['decoder/src_cpp/beam_search.hpp',
                          'decoder/beam_search_decoder/_beam_search_decoder.pxd',
                          'decoder/beam_search_decoder/_beam_search_decoder.pyx',
                          'decoder/beam_search_decoder/__init__.pyi',
                          'decoder/setup.py'],
    'qLDPC': ['src/qldpc/codes/quantum.py','src/qldpc/circuits/memory/memory.py','src/qldpc/circuits/memory/syndrome_measurement.py','src/qldpc/circuits/noise_model.py'],
    'Stim': ['setup.py','src/stim/dem/detector_error_model.cc','src/stim/simulators/error_analyzer.cc'],
    'BivariateBicycleCodes': ['decoder_setup.py'],
    'stimbposd': ['src/stimbposd/dem_to_matrices.py'],
}
HYBRID_SOURCES = runpy.run_path(str(ROOT/'external_lib/ldpc/src_python/ldpc/hybrid_bp/source_files.py'))['SOURCE_FILES']
PATHS['ldpc'] = list(dict.fromkeys([*PATHS['ldpc'], *HYBRID_SOURCES]))

COMMANDS = {
    'ldpc': ['python -m pip wheel --no-build-isolation --no-deps external_lib/ldpc -w external_lib/wheels (before opt-in changes)',
             'python -m pip install --no-build-isolation --no-deps -e external_lib/ldpc',
             '(cd external_lib/ldpc && python setup_reference.py build_ext --inplace)',
             '(cd external_lib/ldpc && python setup_hybrid.py build_ext --inplace)'],
    'BeamSearchDecoder': ['(cd external_lib/BeamSearchDecoder/decoder && python setup.py build_ext --inplace)'],
    'qLDPC': ['python -m pip install --no-build-isolation --no-deps -e external_lib/qLDPC'],
    'Stim': ['(cd external_lib/Stim && python setup.py build_ext --inplace --force)',
             'python -m pip wheel --no-build-isolation --no-deps external_lib/Stim -w external_lib/wheels',
             'python -m pip install --force-reinstall --no-deps external_lib/wheels/stim-1.16.0-*.whl'],
    'BivariateBicycleCodes': [], 'stimbposd': [],
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    """Write manifest and patches for inspected local sources, preserving exact identities."""
    records = {}
    patches = ROOT / 'external_lib/patches'
    patches.mkdir(exist_ok=True)
    for name, (url, module, license_name, role) in SOURCES.items():
        directory = ROOT / "external_lib" / name
        def git(*args):
            return subprocess.check_output(["git", "-C", str(directory), *args], text=True).strip()
        imported = importlib.import_module(module) if module else None
        diff_command = ['git','-C',str(directory),'diff','--binary','HEAD']
        if name == 'BeamSearchDecoder':
            # The tracked Cython-generated C++ contains machine-specific paths and
            # can be regenerated from the authored pyx/pxd sources on each build.
            diff_command += ['--', '.', ':(exclude)decoder/beam_search_decoder/_beam_search_decoder.cpp']
        patch = subprocess.check_output(diff_command,text=True)
        # Upstream ignores *.cpp under src_python, including our authored pybind
        # source. Explicitly audited files must survive even when Git ignores them.
        source_paths=[]
        for rel in PATHS[name]:
            path=directory/rel
            source_paths.extend([p for p in path.rglob('*') if p.is_file() and p.suffix in ('.py','.pyi','.pyx','.hpp','.cpp')]
                                if path.is_dir() else [path])
        untracked=set(git('ls-files','--others','--exclude-standard').splitlines())
        for source in source_paths:
            relative=str(source.relative_to(directory))
            tracked=subprocess.run(['git','-C',str(directory),'ls-files','--error-unmatch',relative],capture_output=True)
            if source.is_file() and tracked.returncode!=0: untracked.add(relative)
        for filename in sorted(untracked):
            path=directory/filename
            if path.suffix not in ('.py','.pyi','.hpp','.cpp','.md') or '__pycache__' in str(path):
                continue
            extra=subprocess.run(['git','-C',str(directory),'diff','--no-index','--','/dev/null',filename],
                                 capture_output=True,text=True)
            if extra.returncode not in (0,1):
                raise RuntimeError(extra.stderr)
            patch+=extra.stdout
        patch_path=patches/f'{name}.patch'
        patch_path.write_text(patch)
        native_files = [path for path in directory.rglob('*.so') if 'build' not in path.parts
                        and not any(part.startswith(('build','python_build')) for part in path.parts)] if module else []
        if name=='Stim':
            native_files=list(Path(imported.__file__).parent.glob('*.so'))
        records[name] = {"url": url, "commit": git("rev-parse", "HEAD"),
                         "branch": git("branch", "--show-current"), "license": license_name,
                         "role": role, "import_location": getattr(imported, "__file__", None),
                         "version": getattr(imported, "__version__", None),
                         "version_status": "upstream package version" if getattr(imported, "__version__", None)
                                           else "no package version exposed; identify by exact source commit",
                         "local_changes": git("status", "--porcelain"),
                         "relevant_paths":PATHS[name],"build_commands":COMMANDS[name],
                         "source_hashes":{str(p.relative_to(directory)):digest(p) for p in source_paths if p.is_file()},
                         "native_files":{str(p):digest(p) for p in native_files},
                         "patch_file":str(patch_path.relative_to(ROOT)),"patch_sha256":digest(patch_path),
                         "compiler": subprocess.check_output(["g++", "--version"], text=True).splitlines()[0] if name in ('Stim','ldpc','BeamSearchDecoder') else None,
                         "flags": ('-O3 -std=c++2a; reference/hybrid: -O3 -std=c++17 -fno-fast-math -ffp-contract=off'
                                   if name=='ldpc' else '-O3 -std=c++2a' if name=='BeamSearchDecoder'
                                   else '-O3 -std=c++20 -fno-strict-aliasing -g0; upstream polyfill/SSE2 selection' if name=='Stim' else None),
                         "hosted_fork": False}
    from ldpc.reference_bp import build_identity
    records['ldpc']['reference_build_identity']=build_identity()
    from ldpc.hybrid_bp import build_identity as hybrid_identity
    records['ldpc']['hybrid_build_identity']=hybrid_identity()
    records['ldpc']['upstream_remote']=subprocess.check_output(['git','-C',str(ROOT/'external_lib/ldpc'),'remote','get-url','upstream'],text=True).strip()
    output = {"schema_version": 1, "python": sys.version, "executable": sys.executable,
              "platform": platform.platform(), "dependencies": records,
              "wheels":{p.name:digest(p) for p in sorted((ROOT/'external_lib/wheels').glob('*.whl'))},
              "package_versions":{d.metadata['Name']:d.version for d in importlib.metadata.distributions() if d.metadata['Name']},
              "dependency_lock_sha256":digest(ROOT/'requirements.lock.txt'),
              "conda_lock_sha256":digest(ROOT/'environment.conda.lock.txt')}
    (ROOT / "external_lib/manifest.lock.json").write_text(json.dumps(output, indent=2,sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
