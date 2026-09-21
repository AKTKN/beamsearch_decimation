"""Consumer environment diagnostics and hashes, without importing native decoders."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys


def analysis_runtime() -> dict:
    """Return interpreter, consumer source locations and SHA256 hashes of Python files.

    New reports identify the analysis code separately from immutable simulation
    provenance. This reads source bytes only; no build or decoder is initialized.
    """
    import qec_bp_benchmark.config as config

    package = Path(__file__).resolve().parent
    paths = sorted(package.glob('*.py'))
    hashes = {f'analysis/{p.name}': hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    config_path = Path(config.__file__).resolve()
    hashes['qec_bp_benchmark/config.py'] = hashlib.sha256(config_path.read_bytes()).hexdigest()
    return {'api_version': 2, 'python_executable': sys.executable,
            'analysis_path': str(package), 'config_path': str(config_path), 'source_sha256': hashes}
