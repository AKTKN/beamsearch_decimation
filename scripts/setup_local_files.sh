#!/usr/bin/env bash
# Materialize editable settings/notebooks without replacing existing local work.
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
while IFS= read -r -d '' template; do
  target=${template%.example}
  if [[ ! -e "$target" && ! -L "$target" ]]; then
    cp -n -- "$template" "$target"
  fi
done < <(find "$root/config" "$root/notebook" -type f \( -name '*.yaml.example' -o -name '*.ipynb.example' \) -print0)
