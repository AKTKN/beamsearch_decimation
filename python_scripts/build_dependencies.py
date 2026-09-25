"""Build or verify pinned active Beam8/BP-OSD/Relay dependencies."""
from __future__ import annotations
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys
import sysconfig

ROOT = Path(__file__).resolve().parents[1]
ACTIVE = ('ldpc', 'BeamSearchDecoder', 'relay', 'qLDPC', 'Stim')


def run(*args: str, cwd: Path = ROOT) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def verify() -> dict:
    if Path(sys.prefix).name != 'search_decimation':
        raise RuntimeError('Use conda environment search_decimation')
    manifest = json.loads((ROOT / 'external_lib/manifest.lock.json').read_text())
    for name in ACTIVE:
        source = ROOT / 'external_lib' / name
        commit = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
        if commit != manifest['dependencies'][name]['commit']:
            raise RuntimeError(f'{name} checkout differs from pinned commit')
    modules = {'ldpc': 'ldpc', 'BeamSearchDecoder': 'beam_search_decoder',
               'relay': 'relay_bp', 'qLDPC': 'qldpc', 'Stim': 'stim'}
    locations = {}
    for name, module_name in modules.items():
        module = importlib.import_module(module_name)
        path = Path(module.__file__).resolve()
        if name != 'Stim' and (ROOT / 'external_lib' / name).resolve() not in path.parents:
            raise RuntimeError(f'unintended {name} import: {path}')
        locations[name] = str(path)
    from beam_search_decoder import BeamSearchDecoder
    if not hasattr(BeamSearchDecoder, 'total_iterations'):
        raise RuntimeError('Beam8 total-iteration binding is unavailable; rebuild it')
    beam = ROOT / 'external_lib/BeamSearchDecoder'
    for relative, expected in manifest['dependencies']['BeamSearchDecoder']['source_hashes'].items():
        current = hashlib.sha256((beam / relative).read_bytes()).hexdigest()
        if current != expected:
            raise RuntimeError(f'Beam8 source hash mismatch: {relative}')
    from relay_bp import RelayDecoderF64
    if not hasattr(RelayDecoderF64, 'decode_detailed'):
        raise RuntimeError('Relay F64 detailed binding is unavailable; rebuild it')
    relay = ROOT / 'external_lib/relay'
    for relative, expected in manifest['dependencies']['relay']['source_hashes'].items():
        current = hashlib.sha256((relay / relative).read_bytes()).hexdigest()
        if current != expected:
            raise RuntimeError(f'Relay source hash mismatch: {relative}')
    return locations


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if not args.check:
        pip = (sys.executable, '-m', 'pip')
        run(*pip, 'install', '-r', 'requirements.lock.txt')
        run(*pip, 'install', '--no-build-isolation', '--no-deps', '-e', 'external_lib/ldpc')
        run(*pip, 'install', '--no-build-isolation', '--no-deps', '-e', 'external_lib/qLDPC')
        run(*pip, 'install', '--no-build-isolation', '--no-deps', '-e', 'external_lib/relay')
        beam_root = ROOT / 'external_lib/BeamSearchDecoder'
        beam_record = json.loads((ROOT / 'external_lib/manifest.lock.json').read_text())['dependencies']['BeamSearchDecoder']
        source_matches = all(
            (beam_root / relative).is_file() and
            hashlib.sha256((beam_root / relative).read_bytes()).hexdigest() == expected
            for relative, expected in beam_record['source_hashes'].items()
        )
        if not source_matches:
            changes = subprocess.check_output(
                ['git', '-C', str(beam_root), 'status', '--porcelain'], text=True).strip()
            if changes:
                raise RuntimeError('Beam checkout has local changes; preserve them before patch restoration')
            patch = ROOT / beam_record['patch_file']
            if hashlib.sha256(patch.read_bytes()).hexdigest() != beam_record['patch_sha256']:
                raise RuntimeError('Beam patch hash mismatch')
            run('git', 'apply', '--check', str(patch), cwd=beam_root)
            run('git', 'apply', str(patch), cwd=beam_root)
        run(sys.executable, 'setup.py', 'build_ext', '--inplace',
            cwd=beam_root / 'decoder')
        (Path(sysconfig.get_paths()['purelib']) / 'beam_search_baseline.pth').write_text(
            str(beam_root / 'decoder') + '\n')
        run(*pip, 'install', '--no-build-isolation', '--no-deps', '-e', '.')
        # Editable installs add their import roots via .pth files at interpreter
        # startup. Verify in a fresh interpreter, including in a clean prefix.
        run(sys.executable, __file__, '--check')
        return
    print(json.dumps(verify(), indent=2))


if __name__ == '__main__':
    main()
