# Circuit-level BP benchmark

All seven implementation stages are complete: physical Z-memory circuits, canonical
DEM artifacts, native screened-decimation search using the forked ldpc flooding
kernel, unchanged BP-OSD and published beam baselines, paired serial/spawn simulation,
exact replay, verified analysis, figures and executable notebooks. A fresh pinned-source
build passed the full acceptance suite. See [acceptance report](docs/acceptance_report.md)
and [status](STATUS.md) for actual evidence and limits.

```bash
# Create once; use the existing environment if already installed.
conda create -n search_decimation --file environment.conda.lock.txt
conda activate search_decimation
scripts/setup_local_files.sh
scripts/build_dependencies.sh
python python_scripts/audit_dependencies.py
scripts/build_dependencies.sh --check
python -m pytest -q

scripts/run_benchmark.sh config/smoke.yaml
scripts/run_benchmark.sh config/latency_smoke.yaml
scripts/analyze_benchmark.sh config/smoke.yaml --run /path/to/run
scripts/replay_samples.sh /path/to/run config/decoder_sweep.yaml
scripts/execute_notebook.sh config/smoke.yaml --run /path/to/run \
  --output assets/notebook/smoke_executed.ipynb
```

Add `-v` or `--verbose` to simulation/replay commands for preparation and committed-batch
progress on stderr, for example `scripts/run_benchmark.sh config/smoke.yaml --verbose`.
stdout remains the completed run directory. Progress updates once per committed batch.

The smoke YAML runs all three native decoders on rotated surface d=5,7,9 and
BB [[72,12,6]], R=d, with circuit-level noise and Z-check detector inputs. BB retains
all twelve logical Z observables. It uses 32 shots per instance and four workers;
smoke_serial.yaml and smoke_two_workers.yaml use the identical plan with one/two
workers. latency_smoke.yaml uses one isolated worker. The four-shot
stage5_validation.yaml remains available for a shorter integration check.

Edit `noise.rates` or `noise.sweep` (exactly one), `decoders` entries, sampling counts
and execution workers for the requested experiment. The production template rejects
its empty physical grid until edited. The example p=0.001 is for implementation
validation only; these smoke data establish no decoder advantage or tail precision.

Immutable circuits/DEMs/matrices/maps go to simulation_data/. Every run copies its
artifacts and sources into a UTC timestamp/nonce folder under output.root (default
assets/runs/). Reports use analysis.output (default assets/analysis/), and executed
notebooks use the requested new output path. Final clean acceptance artifacts are
indexed in [stage_6_7_summary.json](docs/test_results/stage_6_7_summary.json).
Interrupted runs expose committed subsets for reading/replay; in-place resume is
not implemented. Analysis materializes selected finite datasets in memory.

[Build](docs/build.md), [fork maintenance](docs/fork_maintenance.md),
[pipeline/replay/timing](docs/pipeline.md), [scientific contract](docs/benchmark_contract.md),
[YAML](docs/configuration.md), [schema](docs/schema.md), [analysis](docs/analysis.md),
[extension points](docs/extensions.md), [traceability](docs/traceability.md),
[source locks](external_lib/manifest.lock.json).
The algorithm specification and all six supplied reference modules are preserved.

## Git distribution

See [repository setup](docs/distribution.md). Editable `config/*.yaml` files,
analysis notebooks, scientific artifacts, reports, caches and dependency checkouts
are local and ignored. Versioned `.example` templates initialize a new checkout
without replacing local work. Dependency commits and fork patches remain versioned.
