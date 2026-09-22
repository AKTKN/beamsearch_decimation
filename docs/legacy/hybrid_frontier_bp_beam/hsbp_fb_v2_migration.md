# HSBP-FB-2.0 migration and acceptance

This repository implements the opt-in decoder kind
`hybrid_frontier_bp_beam_osd0`, profile
`hybrid_frontier_bp_beam_ms_osd0_v2`, algorithm `HSBP-FB-2.0`.  The normative
algorithm and data contracts are [the report](specifications/hybrid_frontier_bp_beam_report.tex)
and [the Arrow contract](specifications/hybrid_frontier_bp_beam_parquet_schema.json).
Historical screened-reference, HSBP-ALG-1.0, BP-OSD, and published beam identities
are unchanged.

## Implementation map

- `config.py` owns frozen strict v2 search/BP/stopping/fallback and typed-output
  models. Scalar cycle budgets resolve to arrays before identity generation.
- `native/frontier_search.hpp` owns the independent persistent Q/G heaps, compact
  node arena, canonical branching and physical fractional-cover score.
- `native/frontier.hpp` owns the retained candidate-state beam, frozen donor set,
  fixed per-candidate-visit scheduler, solution incumbent and direct OSD0 handoff.
- The maintained ldpc fork's `stateful_min_sum.hpp` owns mutable flooding messages
  and validated snapshots. Graph data are shared; snapshots own all mutable arrays.
- `decoders/__init__.py` is the truth-free Python adapter. `runner/worker.py` adds
  truth labels only after the decode service timer.
- `storage/frontier_schema.py` and `storage/frontier.py` build and validate the 14
  separate Parquet datasets. `analysis/io.py` reads only committed inventory files.

Q, G and the BP beam have independent lifecycles. A node admitted to BP leaves G
but stays in Q. At cycle entry, at most W retained snapshots are frozen. Continuing
candidates use their own state; fresh candidates use the nearest retained strict
ancestor or a cold seed. Same-cycle results cannot donate. Every candidate runs
sequentially on one native thread, while each min-sum iteration is flooding/parallel.

The prefix validates all solutions on original H/s and ranks complete corrections
by physical cost then full bits. Truth never enters the native API. If the prefix
has no incumbent, the decoder calls the pinned direct OSD-CS0 bridge exactly once,
using the configured guided/channel/released signed LLR source.

## Configuration and stopping

Run `python python_scripts/validate_config.py CONFIG` for a no-execution dry run.
The production-sized user template is
`config/hybrid_frontier_bp_beam_example.yaml.example`; it is not run implicitly.
The bounded smoke and controlled named variants are adjacent. Width 1/2/4 retain
the same search limits and fixed 20-iteration candidate visits.

`max_cycles: 0` creates no search root, resolves all cycle arrays empty, requires
zero global BP work and exercises direct CS0. A zero-syndrome shot creates neither
root nor cycle but emits real zero summary counters and one solution event. Numeric
caps are marked hit only when they block requested work. In-place resume remains
intentionally unsupported by the repository contract: completed committed batches
are readable/replayable, while a continuation always uses a new timestamped run.

## Source and dependency audit

The implementation started from project commit
`f7128e94b746e3c8a2fa7923d5e2318195712f0a`. The ldpc upstream remains
`d3429964cd4ffe1abfc041c6ec8b8425cb174f40` on the local
`screened-decimation-bp` branch. Its rebuilt hybrid source identity is
`119b15823559ac0845293a296ff164e5cdb8f8b9a12d864a99c1b453007aea8b`.
The final project native source identity is
`4eeb0923b4824fb832aef0b2c0114428f0666fd8d2cd781555f0b790fd7d1740`;
the installed extension SHA-256 is
`6f7126333803fdf04d4ecc80f928d92eca955d3436a00c6fbaed9d4b42363dc6`.
The exact compiler, flags, fork patch and binary hashes are in
`external_lib/manifest.lock.json` and each saved run's provenance.

The published beam baseline is still exact source commit
`084a475b05fb64308103317a1ce5a0c4b0be58aa`. Its compiled source excludes
candidate variables of Tanner degree at most two. If no eligible variable improves
the initialized selection, its implementation retains an existing/default index.
This behavior was audited but not changed; `beam8` therefore remains a historical
baseline, not a corrected profile.

## Bounded acceptance (2026-09-21)

- `python -m pytest -q`: 290 passed, 1 skipped in 173.05 s.
- Release CMake/CTest: reference_bp, search, hybrid_bp, hybrid, frontier — 5/5.
- ASan+UBSan ownership targets: hybrid_bp and frontier — 2/2.
- Source-only ldpc patch restoration rebuilt both opt-in bindings, rebuilt the
  project extension and passed all five restored native tests.
- One-worker surface d=3 and BB72 d=6 smoke: 16 physical shots, 48 decode rows,
  four committed batches, full schema/accounting validation.
- Saved-source replay: 16 inputs and 48 results equal outside timing.
- Two spawn workers: the same 16 inputs, 48 results and native scientific events
  equal to one worker; timing and worker assignment are excluded.
- Saved-data report and the API-only notebook completed. These small samples are
  software validation, not accuracy or latency evidence.

Accepted paths:

- smoke: `assets/runs/20260921T134138.088393Z_375c9f8e3501`
- replay: `assets/runs/20260921T134242.745156Z_ed27824301be`
- two workers: `assets/runs/20260921T134201.783401Z_51e53369ed9d`
- isolated phase timing: `assets/runs/20260921T134114.166426Z_aa20dad4f108`
- analysis: `assets/analysis/20260921T134316.299523Z_d3d3586863`
- notebook: `assets/notebook/frontier_v2_final_smoke.ipynb`

## Interpretation and next experiment

No result here establishes superiority over beam8. Start with held-out matched-work
width 1/2/4 and architecture controls, then retention/inheritance/hint ablations,
then search/detector-beam/stopping and OSD-handoff controls. Run the isolated
one-worker latency configuration separately from throughput. Choose a production
physical-rate grid and accuracy margin before sampling; do not tune and claim on
the same shots.
