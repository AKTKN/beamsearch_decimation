# Recorded verification evidence

Actual logs from the final stages 1–3 environment. summary.json records counts and
checksums; source_pins.md identifies the exact external revisions. project_tests.txt
contains the complete project-suite result; upstream_tests.txt contains selected
upstream tests. Native debug and ASan/UBSan outputs, compiler logs, import checks,
production-template refusal and repeated physical artifact paths are retained.

These finite tests establish implementation behavior, not decoder performance.
The current accepted fixtures are listed in simulation_data/stage_1_3_validation_index.json.

Stages 4–5: stage_4_5_summary.json records six final real-native CLI runs and exact
paired comparisons, plus 91 project tests, 560 full-search oracle comparisons and
native Debug/ASan/UBSan results. stage_4_5_pytest.log is the final suite output.
stage_4_5_build.log is the final optimized binding build. stage_5_* logs contain
accepted final run paths; earlier development runs remain on disk but are not the
accepted evidence. verify_stage_4_5.py revalidates committed checksums/schema/pairing,
all-observable shapes, and non-timing equality from these paths. The source-bearing
run archives are immutable snapshots; later documentation/evidence updates do not
rewrite old runs. stage_1_3_status.md preserves the previous implementation status.

Stages 6–7: stage_6_7_summary.json records the fresh prefix/workspace, exact command
argv/cwd/return codes, dependency versions/pins, compiled identities/import paths,
four full 32-shot smoke runs, replay, exact comparisons, reports and notebook.
stage_7_*.log contains actual clean-environment checks: 117 project tests, 15 selected
upstream regressions, native Debug/ASan/UBSan 2/2 each, complete simulation/replay/
analysis/notebook commands and expected production rejection. stage_6_7_main_pytest.log
records the independent working-environment 117-test pass. stage_7_dependency_manifest.json
preserves fresh build identities without overwriting the main dependency manifest.
stage_6_* retains focused analysis/build/notebook evidence. stage_4_5_status.md preserves
the previous status; docs/acceptance_report.md describes the final gate and limits.

Verbose-mode maintenance: verbose_pytest.log records 121 passing tests; verbose_smoke.log
and verbose_smoke_path.txt preserve the real two-worker/all-four-code CLI progress
and completed run path (16 samples, 48 decoder rows, eight batches). The saved run
also passed verify_benchmark.py integrity validation. Historical acceptance is unchanged.


`hybrid_stage_1_*.log` record the separate hybrid
migration's Stage 1 validation. They do not replace historical acceptance logs.
See STATUS.md for commands, counts and limitations; no production sweep was run.

`hybrid_stage_2_*`, `hybrid_stage_3_*` and `hybrid_stage_2_3_*` logs preserve all
validation attempts for Stages 2-3, including the source-edit race and CMake
relative-hash reconfiguration failures and their successful follow-ups. STATUS.md
identifies accepted results; earlier failures are retained rather than overwritten.

Hybrid Stages 4–5 evidence is in hybrid_stage_4_5_final_pytest.log (253 full-suite
passes), final_boundary_tests.log (49 focused passes after the event-policy guard),
and hybrid_stage_5_integer_accounting_tests.log (21 paired-analysis passes after
int64-before-float subtraction). hybrid_stage_4_5_dependencies.log verifies native
source/build identities without changing dependencies. hybrid_stage_4_* logs/path
files preserve smoke, latency, ablations, worker, replay and none runs. Comparisons
are in hybrid_stage_4_compare_*.log; verification.json indexes all-12-BB labels,
row/event counts and output identities. hybrid_stage_5_report.log and final_report.log
record successful report CLI outputs; notebook.log records the executed saved-data
notebook. These checks do not establish scientific performance or accuracy advantage.

Hybrid Stage 6 evidence: hybrid_stage_6_clean_restore_final.log verifies both
source-restored opt-in bindings, a fresh project extension and native 4/4 tests.
The initial clean_restore.log records a corrected harness identity-key error;
no failed check is represented as passing. Native release/debug/sanitize logs each
record 4/4. Project build/dependency check, full Python, selected upstream and final
storage corruption tests have distinct logs. hybrid_stage_6_e2e_verification.json
indexes the new six-case fresh-circuit workflow, exact scientific comparisons,
65 checksummed report files, 12 paired groups and executed notebook. No production
sweep or scientific advantage is asserted by these software checks.
