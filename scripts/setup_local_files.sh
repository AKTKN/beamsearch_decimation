#!/usr/bin/env bash
# Materialize editable settings/notebooks without replacing existing local work.
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
for template in "$root"/config/*.yaml.example "$root"/notebook/*.ipynb.example; do
  target=${template%.example}
  if [[ ! -e "$target" && ! -L "$target" ]]; then
    cp -n -- "$template" "$target"
  fi
done
