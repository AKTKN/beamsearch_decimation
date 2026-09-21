#!/usr/bin/env bash
# Materialize editable settings/notebooks without replacing existing local work.
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
shopt -s nullglob
for template in "$root"/config/*.yaml.example "$root"/config/legacy/*.yaml.example "$root"/notebook/*.ipynb.example "$root"/notebook/legacy/*.ipynb.example; do
  target=${template%.example}
  if [[ ! -e "$target" && ! -L "$target" ]]; then
    cp -n -- "$template" "$target"
  fi
done
