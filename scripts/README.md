# Shared shell launchers

Activate search_decimation before use. Simulation/replay launchers serve both
decoder workflows. Current saved-data consumers read v1/v2; scripts/legacy/
preserves the previous analysis/notebook entry points. Older simulation configs
live in config/legacy/.

- run_benchmark.sh CONFIG executes paired sampling/decoding.
- replay_samples.sh SOURCE_RUN CONFIG decodes the same saved physical shots.
- analyze_benchmark.sh [CONFIG] --run RUN [-v] creates saved-data reports.
- execute_notebook.sh [CONFIG] --run RUN --output NEW.ipynb [--timeout SECONDS] executes the consumer notebook.
- prepare_circuits.sh CONFIG prepares physical circuit/DEM artifacts.
- build_dependencies.sh [--check] and clean_build.sh OUTPUT_ROOT build/check sources.
- setup_local_files.sh materializes missing config/, config/legacy/ and notebook/
  templates, including notebook/legacy/, without replacing edited files or symlinks.

Source paths resolve independently of the caller's working directory. Run/replay
accept -v/--verbose for parent-only stderr progress; stdout remains the final run path.

```bash
scripts/run_benchmark.sh config/hybrid_smoke.yaml.example --verbose
scripts/run_benchmark.sh config/legacy/smoke.yaml.example --verbose
```

Full bounded hybrid acceptance uses
`python python_scripts/accept_hybrid.py --output NEW_DIRECTORY`. It invokes the same
Python CLIs and preserves every command/log without overwriting old outputs.
