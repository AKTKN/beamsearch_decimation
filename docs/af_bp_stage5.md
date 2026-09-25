# AF-BP Stage 5: comparison decoders and exact iterations

Stage 5 registers upstream Relay-BP as `kind/profile: relay_bp` alongside
`beam8` and `bposd`. AF-BP remains a separately callable native service and
is not in the simulator registry. Circuit construction, DEM conversion,
sampling, worker scheduling, timing boundaries, and the five-field Parquet
storage implementation were not changed.

## Pinned Relay source and build

On 2026-09-25, upstream `https://github.com/trmue/relay.git` reported
`d185194ba0cb4101ced4340d82b2ee6d42f225f0` as `main` HEAD. The
checkout is detached at that commit and has no local source changes. Its
Apache-2.0 license and Copyright IBM 2025 source notices remain intact.
`maturin==1.15.0` is locked in `requirements.lock.txt`; the upstream Cargo
locks, source, build manifests, license, imported native binary, and empty
`external_lib/patches/relay.patch` are audited in `manifest.lock.json`.
`scripts/build_dependencies.sh` builds the upstream editable package and
`--check` verifies commit, source hashes, import location and the F64 API.
No Relay Rust/Python scientific implementation was modified.

## Adapter contract

The active `RelayBP` config exposes `alpha`,
`alpha_iteration_scaling_factor`, `gamma0`, `pre_iter`, `num_sets`,
`set_max_iter`, `gamma_dist_interval`, `stop_nconv`, and `seed`. Defaults
follow the upstream constructor, without Gross-code parameter presets.
`explicit_gammas` is rejected because the active config has no reproducible
content-addressed array source and shape/hash contract. The adapter fixes
upstream `stopping_criterion=nconv` and `logging=false`, constructs
`RelayDecoderF64` from the canonical H and binary64 mechanism priors, and
calls only single-shot `decode_detailed`. It never invokes Relay's batch or
Rayon parallel batch APIs inside a worker. The upstream success declaration
is followed by independent original-H validation and A prediction. Neither
construction nor decode receives logical truth.

The truth-free internal result exposes owned `correction` (or null),
`declared_failure`, and `total_iterations`. Relay reads exactly
`DecodeResult.iterations`: upstream adds the initial BP leg and every executed
relay leg, including unsuccessful legs. The impossible two-check/one-column
test executes 2 initial plus 3×4 relay iterations and reports 14, while the
retained initial result's `max_iter` remains 2. Beam8's previously tracked
instrumentation-only patch remains unchanged; its counter increments once
for each completed initial or masked BP iteration. Ordinary BP-OSD uses
native `.iter` for nonzero syndromes and zero for its zero shortcut; OSD adds
zero BP iterations. The existing simulator result schema is unchanged.

## Verification

- The Relay checkout commit matched upstream `main` via `git ls-remote`.
  `scripts/build_dependencies.sh --check`, source audit, and `pip check`
  passed in `search_decimation`.
- A clean pristine Beam checkout at upstream `084a475` was built in a
  temporary directory. Its corrections and convergence for all 16 four-bit
  syndromes were recorded as a fixed regression, which the patched active
  Beam build passed. A tiny known Beam path counted 4 total iterations,
  exceeding its last-path `.iter`, and a zero shortcut reset the count.
- Relay tests cover direct upstream F64 result equality, original-H rejection
  of an invalid claimed success, exact 14-iteration multi-leg failure,
  seeded repeatability across two worker-owned adapters, one-round BB144
  construction and syndrome smoke, and rejection of truth input.
  BP-OSD's early convergence counted 1 with `max_iter=30`; a separate OSD
  path counted only its one BP iteration.
- Config discovery, strict Relay settings, explicit-gamma rejection and the
  Relay smoke config dry run passed. The full Python suite passed 92/92,
  and the focused Relay/config/Beam8/BP-OSD suite passed 51/51.
- A two-shot Relay surface d3 smoke completed under
  `assets/runs/2026_09_25_21_34_c1d1ace0`: both rows used `relay_bp`
  and reported 1 and 2 total BP iterations in the existing five-field
  output. The paired beam8/BP-OSD surface d3 smoke completed under
  `assets/runs/2026_09_25_21_35_871b9d6a`: four rows used the two
  original baseline identities. These tiny checks are implementation
  evidence, not performance or logical-rate estimates. No production sweep
  was run.
