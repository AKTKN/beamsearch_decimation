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


The historical algorithm/benchmark contracts above remain authoritative for the
preserved screened profile. The hybrid migration uses the additional unchanged
hybrid_search_soft_bp_osd0_specification.md and
hybrid_benchmark_data_and_hypothesis_specification.md. hybrid_migration.md records
Stage 1 configuration, implementation boundaries, decisions and pending stages.

Current hybrid Stages 2-3 APIs, ownership, clocks, exact counter meanings, build/hash
inventories and engineering limits are in hybrid_native.md. hybrid_migration.md is
the preserved Stage 1 decision record; its planned interfaces are superseded there.

- hybrid_data.md: current v2 schema fields, atomic event policy, timing/label
  validation, paired hypothesis APIs and reproducible Stage 4–5 workflows.
- hybrid_acceptance.md: final source restoration, Release/Debug/sanitizer and E2E
  commands, contract review, evidence scope and handoff limitations.
