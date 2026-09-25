# Current documentation

Current architecture: see `architecture.md`, `simulation_output.md`,
`../config/README.md` and `legacy/decimation/README.md`. AF-BP is a callable
native service awaiting simulator integration; Relay-BP is an active pinned
comparison decoder. `af_bp_stage5.md` records Relay integration and exact
iteration evidence. The remaining index below describes historical work.

---

# docs

The unchanged algorithm specification and benchmark_contract.md are normative.
build.md and fork_maintenance.md cover installation and pinned external sources;
architecture.md, circuits.md, reference_bp.md and pipeline.md describe implementation,
scientific conventions, timing and replay. configuration.md and schema.md document
all settings and stored data. analysis.md covers summaries, figures and notebooks;
extensions.md describes supported extension points. traceability.md and
configuration_audit.md map requirements to code/tests. acceptance_report.md records
final clean-build commands and evidence; test_results/ preserves historical logs.

distribution.md documents the Git publication boundary and first-clone setup.
simulation_output.md defines the current two-entry result directory and data naming.


The historical algorithm/benchmark contracts above remain authoritative for the
preserved screened profile. The hybrid migration uses the additional unchanged
hybrid_search_soft_bp_osd0_specification.md and
hybrid_benchmark_data_and_hypothesis_specification.md. hybrid_migration.md records
Stage 1 configuration, implementation boundaries, decisions and pending stages.

Current hybrid Stages 2-3 APIs, ownership, clocks, exact counter meanings, build/hash
inventories and engineering limits are in hybrid_native.md. hybrid_migration.md is
the preserved Stage 1 decision record; its planned interfaces are superseded there.

- hybrid_data.md: current v2 schema fields, atomic event policy, timing/label
- simulation_timing_benchmark.md: developer-only end-to-end simulation timing
  decomposition with decoder calls kept opaque.
  validation, paired hypothesis APIs and reproducible Stage 4–5 workflows.
- hybrid_acceptance.md: final source restoration, Release/Debug/sanitizer and E2E
  commands, contract review, evidence scope and handoff limitations.
- search_bp_v2_design.md: root refined.tex map and unresolved numerical policies.
- simulation_output.md and data_dictionary.md: active six-field contract.
- legacy/hybrid_frontier_bp_beam/: preserved HSBP-FB-2.0 sources and evidence.

search_bp_implementation.md is the active SEARCH-BP-2.1 equation/function map,
complete defaults, allocation/memory audit and final validation record.
search_bp_stage5.md documents the SEARCH-BP-2.1 simulator integration,
strict native mapping, six-field schema and smoke-sized invariant tests.

lpm_dp_stage1.md documents the standalone LPM-DP 1.0 candidate generator, its
immutable native API, exact local marginal DP, bounded memory, and Stage-1 tests.
It is not a decoder or simulator integration.
lpm_dp_stage2.md documents the minimal fork snapshot/API extension that preserves
the exact final check-to-variable messages required by that generator, including
ownership, memory-gate arithmetic and regression scope.
lpm_dp_stage3.md documents the separate native LPM-DP-BP-1.0 decoder state
machine, bounded online post-BP retention, one-time optional OSD and native tests.
lpm_dp_stage4.md documents its strict configuration, truth-free native adapter,
five-column result contract, timing boundary and bounded simulator smoke tests.
lpm_dp_final_report.md records final clean-build, test/sanitizer, deterministic
worker, memory, call-graph and simulator audits, plus the separate appendix-scoring
assessment and known limitations.
