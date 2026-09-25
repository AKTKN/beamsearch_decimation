# Preserved analysis implementation

These Python modules are byte-for-byte copies of the consumer implementation
immediately before the saved-data analysis migration. `snapshot.json` records the
original hashes. This snapshot already supported v1/v2 and hybrid telemetry; it
retains the original dictionary-based bootstrap and report behavior. It is not a
relabeled v1-only implementation. Relative imports keep statistics/report/plots
inside this package. Shared configuration and storage validators remain current.

Use `from analysis.legacy import load_run, create_report`, or the launchers in
`scripts/legacy/`. Legacy CLIs retain full benchmark YAML and execution setup;
legacy notebook calls route to this package. They use the active environment and
do not switch to an archived acceptance environment. Historical saved runs and
source archives are untouched. New optimization/features belong in `analysis/`.

Stage 6 also places the prior multi-schema `benchmark_plots.py` reader here.
It accepts the historical `baseline_results/1`, SEARCH-BP, and LPM-DP
layouts through `analysis.legacy.benchmark_plots`; active
`analysis.benchmark_plots` accepts only `benchmark_results/2`.
