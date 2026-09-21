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
