# Active benchmark configuration

`baselines.yaml.example` and `baselines_workers2.yaml.example` are paired
serial/two-worker checks. `bposd_cs0_smoke.yaml.example` is an order-zero
single-baseline check. The first is the bounded, runnable Stage-1 smoke template. The
active registry accepts only `beam8` and `bposd`. `bposd.osd_order` is a
nonnegative integer option; default 10, with 0 supported. Other BP-OSD
parameters retain upstream minimum-sum/parallel/scale-1/OSD_CS behavior. Beam
width is fixed at 8. Names `af_bp` and `relay_bp` are reserved and rejected
until implemented.

The physical configuration remains strict: surface odd distance >=3, BB72 d6,
BB144 d12, Z memory/Z-check selection, explicit physical rates, fixed circuit
and DEM options. All paths resolve relative to the YAML file. Use
`python python_scripts/validate_config.py config/baselines.yaml.example` for a
dry run.

Old SEARCH-BP, LPM-DP and BP-OSD-CS0 example templates are preserved under
`legacy/decimation/`, with relative cache/output paths adjusted to retain
their original destinations. Earlier screened and hybrid templates remain
under `legacy/`. Historical files are not valid active configs.
