#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec python "$PROJECT_ROOT/python_scripts/prepare_circuits.py" "${1:?Usage: prepare_circuits.sh CONFIG.yaml}"
