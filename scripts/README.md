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
