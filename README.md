# AF-BP benchmark workspace

This repository is being reset around a future adaptive graph refactorization
BP decoder (AF-BP). **AF-BP and Relay-BP are not implemented yet.** The active
comparison surface currently has two established baselines: published Beam
Search width 8 (`beam8`) and ordinary upstream BP-OSD (`bposd`). The BP-OSD
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
python -m pytest -q
scripts/run_benchmark.sh config/baselines.yaml.example
```

The smoke config runs two physical shots at p=0.003 for a surface d3 circuit.
It does not establish decoder performance. A run writes `config_resolved.json`
and one named Parquet result file per condition under `data/`. Rows hold
`shot_id`, `decoder_name`, `logical_error`, complete-service `latency_ns`, and
exact `total_iterations`. Read one run with
`analysis.simple_results.summarize_run(path)`; plot through the public
`analysis.plot_decode_time_histogram`, `plot_logical_error_rate` and
`plot_mean_decode_time` functions.

Screened decimation, Hybrid Search/BP, SEARCH-BP and LPM-DP are historical.
Their source, configs, readers, tests and prior evidence are preserved; see
[legacy map](docs/legacy/decimation/README.md). Old results retain their own
identities and schemas. The normative AF-BP design is
[adaptive_graph_refactorization_bp_spec.tex](adaptive_graph_refactorization_bp_spec.tex).
Current migration evidence and limitations are in [STATUS.md](STATUS.md).
