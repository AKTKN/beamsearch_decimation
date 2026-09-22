# Shared shell launchers

Activate search_decimation before use. The simulation launcher serves both
decoder workflows. scripts/legacy/
preserves the previous analysis/notebook entry points. Older simulation configs
live in config/legacy/.

- run_benchmark.sh CONFIG executes paired sampling/decoding.
- legacy/analyze_benchmark.sh and legacy/execute_notebook.sh remain available only
  for historical manifest-format data.
- prepare_circuits.sh CONFIG prepares physical circuit/DEM artifacts.
- build_dependencies.sh [--check] and clean_build.sh OUTPUT_ROOT build/check sources.
- setup_local_files.sh materializes missing config/, config/legacy/ and notebook/
  templates, including notebook/legacy/, without replacing edited files or symlinks.

Source paths resolve independently of the caller's working directory. Run
accept -v/--verbose for parent-only stderr progress; stdout remains the final run path.

```bash
scripts/run_benchmark.sh config/hybrid_smoke.yaml.example --verbose
scripts/run_benchmark.sh config/legacy/smoke.yaml.example --verbose
```

Historical manifest/replay acceptance commands are retained only in archived docs.
`benchmark_simulation.sh CONFIG [--repeats N --shots N --batch-size N --output JSON]`
runs the isolated developer timing decomposition. Decoder calls remain black boxes;
temporary scientific results are removed and the optional JSON report is not placed
inside a simulation run directory.
