# AF-BP benchmark workspace

This repository benchmarks adaptive graph refactorization BP (AF-BP) against
published Beam Search width 8 (`beam8`), ordinary upstream BP-OSD (`bposd`),
and pinned upstream Relay-BP (`relay_bp`). All four are active, truth-free
decoder services on the same physical shots. AF-BP supports parallel, serial,
and qDither BP variants, graph factorization policies, and exact total BP work.
Relay uses the F64 Rust-backed `decode_detailed` API, with exact total BP
iterations and no decoder-side batch parallelism. The BP-OSD
`osd_order` is a config option; its default is 10 and order 0 is also valid.

The physical simulation pipeline remains the one from
`search-bp-lpmdp-v1`: surface, BB72 and BB144 Z-memory circuits, paired Stim
shots, selected Z-check detectors, full logical truth, and an undecomposed DEM.
See [active architecture](docs/architecture.md) and
[simulation output](docs/simulation_output.md).

```bash
conda activate search_decimation
scripts/build_dependencies.sh --check
python python_scripts/validate_config.py config/baselines.yaml.example
python python_scripts/validate_config.py config/relay_bp_smoke.yaml.example
python python_scripts/validate_config.py config/af_bp_smoke.yaml.example
python -m pytest -q
scripts/run_benchmark.sh config/baselines.yaml.example
```

The smoke config runs two physical shots at p=0.003 for a surface d3 circuit.
It does not establish decoder performance. A run writes `config_resolved.json`
and one named Parquet result file per condition under `data/`. Rows hold
`shot_id`, `decoder_name`, `logical_error`, complete-service `latency_ns`,
exact `total_iterations`, `converged`, and nullable AF-BP initial/first-transform
convergence flags. Read one run with
`analysis.simple_results.summarize_run(path)`; plot through the public
`analysis.plot_decode_time_histogram`, `plot_logical_error_rate`,
`plot_mean_decode_time`, `plot_mean_total_iterations`, and
`plot_convergence_rate` functions. New results use `benchmark_results/3`;
previous `benchmark_results/2` files remain readable without inferred
convergence. See [comparison configs](config/README.md) for the Phase 1–6
paired experiment templates copied from the local `config/main.yaml` setup.

Screened decimation, Hybrid Search/BP, SEARCH-BP and LPM-DP are historical.
Their source, configs, readers, tests and prior evidence are preserved; see
[legacy map](docs/legacy/decimation/README.md). Old results retain their own
identities and schemas. The normative AF-BP design is
[adaptive_graph_refactorization_bp_spec.tex](adaptive_graph_refactorization_bp_spec.tex).
Current migration evidence and limitations are in [STATUS.md](STATUS.md).
Relay source/build and Stage-5 evidence are in [Stage-5 report](docs/af_bp_stage5.md).
The active integration and bounded BB144 evidence are in the
[Stage-6 report](docs/af_bp_stage6.md).
The [final implementation report](docs/af_bp_final_report.md) records clean
source restoration, mathematical and baseline validation, sanitizer results,
bounded BB144 memory, and the future standalone-package file boundary.
The standalone Stage-4 service API is documented in
[src/af_bp_core/README.md](src/af_bp_core/README.md).
