# Preserved analysis launchers

Activate search_decimation first. These thin wrappers call the preserved Python
consumers and `analysis.legacy`:

```bash
scripts/legacy/analyze_benchmark.sh config/legacy/smoke.yaml.example --run SOURCE_RUN
scripts/legacy/execute_notebook.sh config/legacy/smoke.yaml.example --run SOURCE_RUN \
  --output assets/notebook/legacy_new.ipynb
```

Full benchmark YAML is required. Output paths must be new for notebook execution;
reports always create new timestamped folders. These consumers retain the original
bootstrap performance and do not select archived acceptance kernels.

Simulation and replay remain shared:

```bash
scripts/run_benchmark.sh config/legacy/smoke.yaml.example --verbose
scripts/replay_samples.sh SOURCE_RUN config/legacy/decoder_sweep.yaml.example --verbose
```
