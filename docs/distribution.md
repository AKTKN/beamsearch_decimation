# Git distribution

The source repository is prepared for `AKTKN/beamsearch_decimation` on GitHub.
It includes implementation, tests, contracts, historical acceptance logs, pinned
dependency manifests/patches, and portable configuration/notebook templates.

The following remain local and are ignored by Git:

- `simulation_data/` scientific artifacts and `assets/` runs/reports/acceptance
  workspaces (their directory READMEs remain tracked).
- Editable `config/**/*.yaml`, `config/**/*.yml`, and all `*.ipynb` notebooks.
- Dependency checkouts, wheels, environments, native binaries and caches.

Historical logs in `docs/test_results/` remain versioned evidence. Paths in those
logs and the dependency manifest describe the original machine; the referenced
run snapshots are not shipped. Git exclusion does not delete local files or
change the scientific provenance captured within future runs.

After cloning, activate `search_decimation` and run:

```bash
scripts/setup_local_files.sh
scripts/build_dependencies.sh
python python_scripts/audit_dependencies.py
scripts/build_dependencies.sh --check
python -m pytest -q
```

See [build.md](build.md) for environment creation. Setup copies `.example` files
beside their templates, preserving relative configuration paths and existing
local work. `config/main.yaml` is not distributed. The production template still
requires user-selected physical rates. No simulation runs during local-file setup.

Edit the ignored working files for experiments. Edit `.example` files deliberately
to publish defaults. Notebook templates contain no outputs, execution counts or
machine-specific run selection. Dependencies are cloned from their original URLs
at locked commits; the ldpc additions are restored from the versioned patch,
including the upstream-ignored authored binding. No nested repository gitlinks
or hosted dependency fork are required. This is a Git source distribution;
installation requires the documented native dependency build.
