# Active benchmark configuration

`baselines.yaml.example` and `baselines_workers2.yaml.example` are paired
serial/two-worker checks. `bposd_cs0_smoke.yaml.example` is an order-zero
single-baseline check. `relay_bp_smoke.yaml.example` exercises the pinned
F64 Relay adapter with two physical shots. The first is the bounded, runnable
Stage-1 smoke template. The active registry accepts `beam8`, `bposd`, and
`relay_bp`. `bposd.osd_order` is a
nonnegative integer option; default 10, with 0 supported. Other BP-OSD
parameters retain upstream minimum-sum/parallel/scale-1/OSD_CS behavior. Beam
width is fixed at 8. `af_bp` remains reserved for simulator integration.

`relay_bp` exposes upstream `alpha`, `alpha_iteration_scaling_factor`,
`gamma0`, `pre_iter`, `num_sets`, `set_max_iter`, `gamma_dist_interval`,
`stop_nconv`, and `seed`. It fixes `stopping_criterion=nconv`, disables
upstream file logging, and uses single-shot `decode_detailed`, so each worker
does no Relay batch parallelism. Generic defaults follow the upstream API;
the smoke template uses small explicit budgets. `explicit_gammas` is rejected:
the active config has no content-addressed gamma-array source or shape/hash
contract to reproduce it across workers and checkouts.

The physical configuration remains strict: surface odd distance >=3, BB72 d6,
BB144 d12, Z memory/Z-check selection, explicit physical rates, fixed circuit
and DEM options. All paths resolve relative to the YAML file. Use
`python python_scripts/validate_config.py config/baselines.yaml.example` for a
dry run.

Old SEARCH-BP, LPM-DP and BP-OSD-CS0 example templates are preserved under
`legacy/decimation/`, with relative cache/output paths adjusted to retain
their original destinations. Earlier screened and hybrid templates remain
under `legacy/`. Historical files are not valid active configs.
