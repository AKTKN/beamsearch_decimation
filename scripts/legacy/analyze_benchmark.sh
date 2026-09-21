#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
exec python "$root/python_scripts/legacy/analyze_benchmark.py" "$@"
