# Circuit-level BP benchmark

The current simulation runner uses a minimal result layout: a local-time
`YYYY_MM_DD_HH_MM_<config-hash-8>` directory containing only `data/` and
`config_resolved.json`. Data filenames begin with code, distance, rounds, physical
rate and basis, for example `bb72_d6_r6_p003_Z_logicalerror.parquet`. See
[minimal simulation output](docs/simulation_output.md).

All seven historical implementation stages are complete: physical Z-memory circuits, canonical
DEM artifacts, native screened-decimation search using the forked ldpc flooding
kernel, unchanged BP-OSD and published beam baselines, paired serial/spawn simulation,
exact replay, verified analysis, figures and executable notebooks. A fresh pinned-source
build passed the full acceptance suite. See [acceptance report](docs/acceptance_report.md)
and [status](STATUS.md) for actual evidence and limits.


The separate hybrid migration has completed Stages 1-6: strict configuration,
audited stateful min-sum and OSD-only fork interfaces, and native bounded search
with warm/cold/search-only profiles and CPU/wall telemetry. The hybrid is callable
through `DecoderAdapter` and paired run/replay with v2 storage and reports. See
[the native API](docs/hybrid_native.md) and [current status](STATUS.md).
The upstream `bposd_ms30_cs0` baseline remains runnable through the existing runner.

The active search/BP decoder is `search_bp` (`SEARCH-BP-1.0`). Search assignments
are hard fixations: fixed variable nodes and all incident edges are removed from
BP and fixed ones are folded into the residual syndrome. Beam width controls new
candidate admission and retained BP states; cycle expansion and candidate iteration
work are scalar settings with no independent global expansion/iteration cap. See
[the specification](docs/specifications/search_bp_specification.md). Validate the
bounded template with `python python_scripts/validate_config.py
config/search_bp.yaml.example`.

```bash
# Create once; use the existing environment if already installed.
conda create -n search_decimation --file environment.conda.lock.txt
conda activate search_decimation
scripts/setup_local_files.sh
scripts/build_dependencies.sh
python python_scripts/audit_dependencies.py
scripts/build_dependencies.sh --check
python -m pytest -q

scripts/run_benchmark.sh config/search_bp.yaml.example
python -c "from analysis.simple_search_bp import summarize_run; print(summarize_run('/path/to/run'))"
```

Add `-v` or `--verbose` to simulation commands for preparation and saved-batch
progress on stderr, for example `scripts/run_benchmark.sh config/hybrid_smoke.yaml.example --verbose`.
stdout remains the completed run directory. Progress updates once per saved batch.

The search_bp template runs search_bp, upstream BP-OSD-CS10 and published beam
on surface d=3 and BB [[72,12,6]], with bounded smoke counts. BB retains all twelve
logical Z observables. Historical soft-hint and HSBP-FB configurations are under
`config/legacy/hybrid/`.

Historical screened-reference/CS10 configs and existing local main.yaml are in
`config/legacy/`. Their scientific settings and resolved data/output paths are
preserved. Simulation/replay commands remain shared. Current analysis uses an independent
`config/analysis.yaml.example`; the preserved consumer implementation is available
as `analysis.legacy` and through `scripts/legacy/`. See [analysis migration](docs/analysis_migration.md).

Edit `noise.rates` or `noise.sweep` (exactly one), `decoders` entries, sampling counts
and execution workers for the requested experiment. The production template rejects
its empty physical grid until edited. The example p=0.001 is for implementation
validation only; these smoke data establish no decoder advantage or tail precision.

Immutable circuits/DEMs/matrices/maps remain execution inputs in `simulation_data/`
and are never copied into a result. Runs write the minimal layout under output.root
(default `assets/runs/`). Interrupted runs may contain readable partial Parquet
data; in-place resume and manifest-based replay are not part of the current runner.

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

Historical Hybrid Stages 4–5 evidence and limitations remain documented in
[hybrid acceptance](docs/hybrid_acceptance.md). Those manifest/replay acceptance
commands are legacy evidence, not the current minimal-output workflow.
