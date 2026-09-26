# Active benchmark configuration

## Paired AF-BP comparison templates

The `af_bp_phase*.yaml.example` files copy the **physical simulation setup**
from the local `config/main.yaml`: BB72 d6/R6, Z memory, p=0.001/0.0015/0.002,
10,000 shots per rate, batches of 100, 10 warmups, 8 workers, and the same
circuit cache and output root. Only `experiment.name`, `experiment.purpose`,
and `decoders` differ. They are ready to validate, but no experiment is run
automatically. Runs use fresh directories and paired physical samples; shared
scientific/sampling settings keep the shot identities equal across templates.
Decoder counts differ between templates, so throughput wall latencies from
separate template runs have different contention. Compare timing within one
template and retain its execution context.

| Template suffix | Paired decoder comparison |
|---|---|
| `phase1_schedule_budget` | AF-BP without transforms as parallel/serial BP-30 and BP-130; AF-P/P, AF-P/S, AF-S/S; ordinary BP-OSD-30/OSD_CS-5 |
| `phase2_factorization_policy` | `adaptive_cycle` versus `shen_cycle_count`, all other decoder fields equal |
| `phase3a_failure_top_k` | `U_top_k`: 8, 16, 32, 64 |
| `phase3b_residual_radius` | Radius: 1, 2, 3, with distance decay 0.5 |
| `phase3c_distance_decay` | Decay: 0.25, 0.5, 0.75, 1.0, with radius 2 |
| `phase4_failure_weights` | `(uncertainty_weight, oscillation_weight)`: (1,0), (2,1), (1,1), (1,2), (0,1) |
| `phase5_feedback_frequency` | `(n_fact, graph_rounds)`: (1,4), (2,2), (4,1) |
| `phase6a_qdither_control` | AF-P/P versus graph-warm qDither |
| `phase6b_qdither_interval` | Change alpha or beta separately from the qDither base |
| `phase6c_qdither_rho` | Change qDither rho alone |
| `phase6d_qdither_chains` | 1, 2, 3 chains |
| `phase6e_qdither_chain_iterations` | 3, 5, 7 iterations per chain |

The plain BP controls use the same native AF-BP BP engine with
`graph_rounds: 0` and `n_fact: 0`; their names indicate the kernel and budget.
They are not new decoder profiles. `initial_parallel` selects the actual
initial schedule. The Phase 5 variants match the maximum number of graph
transformations but have different maximum total BP iterations (110, 70, 50);
compare the saved `total_iterations` alongside convergence and logical error.
Phase 6 uses 5 phase-one iterations, 2 chains and 5 iterations per chain at
its base, so the qDither chain work fits within the 20-iteration transformed
BP budget. The Phase 6 variants change one qDither setting from that base.

New runs save `converged` and AF-BP stage flags in `benchmark_results/3`.
`analysis.simple_results.summarize_run` reports convergence,
`P(logical_error | converged)`, and first-transform rescue counts. The final
decoder convergence rate and the first-transform rescue rate have different
denominators; see `docs/simulation_output.md`.

Validate a template without launching the configured 10,000-shot experiment:

```bash
conda activate search_decimation
python python_scripts/validate_config.py config/af_bp_phase1_schedule_budget.yaml.example
```

`baselines.yaml.example` and `baselines_workers2.yaml.example` are paired
serial/two-worker checks. `bposd_cs0_smoke.yaml.example` is an order-zero
single-baseline check. `relay_bp_smoke.yaml.example` exercises the pinned
F64 Relay adapter with two physical shots. The first is the bounded, runnable
Stage-1 smoke template. The active registry accepts `af_bp`, `relay_bp`,
`beam8`, and `bposd`. `bposd.osd_order` is a
nonnegative integer option; default 10, with 0 supported. Other BP-OSD
parameters retain upstream minimum-sum/parallel/scale-1/OSD_CS behavior. Beam
width is fixed at 8.

`af_bp_smoke.yaml.example`, `af_bp_variants.yaml.example`,
`af_bp_factorization.yaml.example`, and `af_bp_n_fact.yaml.example` are
bounded checks for the AF-BP service and its scientific options.
`bb144_tiny.yaml.example` runs one BB144 d12/R1 shot through all four active
decoders. Every example is non-production. AF-BP exposes the full graph,
failure/U-selection, factorization, BP schedule, qDither, and seed settings in
`config.AFBP`; unknown and legacy decimation fields are rejected.

`all_decoders_full.yaml.example` is a complete four-decoder template. It spells
out every accepted decoder field and uses AF-BP 30/20 iterations, 5 graph
rounds and 1 factorization; Relay 30 pre-iterations, 50 sets and 1 iteration
per set; Beam8 8 rounds with 30 initial and 20 per-round iterations; and
ordinary BP-OSD 30 BP iterations with OSD order 5. The BB72 p=0.001,
two-shot physical setup is only a bounded example. Set physical rates and
shot counts for the intended experiment before running it. Fixed values such
as `beam_width: 8`, `bp_method: minimum_sum`, and `osd_method: OSD_CS` are
listed for clarity but cannot be changed through the active config schema.

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
