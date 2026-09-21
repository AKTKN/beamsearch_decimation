# Shell launchers

prepare_circuits.sh CONFIG.yaml and build_dependencies.sh [--check] invoke the thin
Python entry points using the active search_decimation interpreter, including a
separate prefix with that basename. Activate the environment first. Paths to the Python
scripts resolve independently of the caller's working directory. Scientific settings
come only from YAML. See docs/build.md for actual tested commands.

run_benchmark.sh CONFIG.yaml and replay_samples.sh SOURCE_RUN CONFIG.yaml invoke the
paired runner/replay CLIs. Activate search_decimation before launch; wrappers contain
no scientific settings. New run locations are printed on success.
Pass -v/--verbose to either launcher for preparation and committed-batch progress
on stderr. For example: scripts/run_benchmark.sh config/smoke.yaml --verbose.

analyze_benchmark.sh and execute_notebook.sh invoke reusable analysis/notebook CLIs.
clean_build.sh OUTPUT_ROOT invokes an isolated pinned-source build with logged commands.
All source/script paths resolve from the repository; scientific parameters stay in YAML.

setup_local_files.sh copies versioned config/notebook .example templates to
missing editable local files. Existing files and symlinks are never replaced.


Hybrid Stage 1 templates use the existing setup glob, without overwriting local
rates, sweeps, edits or symlinks. `run_benchmark.sh config/bposd_cs0_smoke.yaml` is a
bounded upstream-baseline check. Enabled hybrid templates fail explicitly before
creating a run until Stage 4 adds v2 tables; they do not invoke another decoder as a substitute.

Hybrid workflows use the existing wrappers unchanged. See
config/hybrid_smoke.yaml.example, hybrid_latency.yaml.example and
hybrid_ablations.yaml.example. Analysis/bootstrap controls come from YAML; notebooks
can explicitly use the maintained .ipynb.example without overwriting local edits.

The full bounded hybrid acceptance entry point is
`python python_scripts/accept_hybrid.py --output NEW_DIRECTORY`; it invokes the
existing Python CLIs, records every command/log, and never overwrites old outputs.
