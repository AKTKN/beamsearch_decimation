# Saved-data analysis consumer migration

The default consumer now supports the native hybrid, warm/cold/search-only
ablations, CS0/CS10 and beam baseline results through the verified v1/v2 reader.
Decoder identity comes from each saved manifest. Loading a run never constructs a
decoder or changes simulation settings. All existing schema, artifact, provenance,
paired-shot, context and telemetry checks remain in place.

## Entry points and configuration

```bash
conda activate search_decimation
scripts/analyze_benchmark.sh config/analysis.yaml.example --run SOURCE_RUN --verbose
scripts/execute_notebook.sh config/analysis.yaml.example --run SOURCE_RUN \
  --output assets/notebook/new.ipynb --timeout -1
```

The config argument is optional and defaults to the checked-in analysis template.
Analysis-only YAML has one strict `analysis` section; it requires no noise, decoder,
sampling, or execution settings. Paths resolve relative to its file. Simulation YAML
is a separate strict interface and is rejected here. CLI selection/filtering and
committed-subset rules are unchanged. Verbose progress goes to stderr, while stdout
contains the final report path. Notebook execution uses the active interpreter,
the maintained template by default, and a configurable per-cell timeout.

The original notebook failure arose from a kernel under assets/acceptance loading
an older Config union. New notebooks check the installed analysis API and checkout,
display runtime paths, use an analysis-only config, and advertise the registered
search_decimation kernel. A saved notebook cannot itself replace a running Python
interpreter: select the current environment, restart, then execute all cells.

## Preserved implementation

`analysis/legacy/*.py` contains byte-preserved copies of every previous analysis
module. snapshot.json and a test verify the original Python hashes. This is the
pre-consumer-migration v1/v2 implementation, including the original hybrid analysis;
it is not an invented historical v1-only version. Dedicated scripts in
python_scripts/legacy/ and scripts/legacy/, and notebook/legacy/, route to it.
Shared simulation/storage/configuration infrastructure remains installed once.
Existing editable notebooks, acceptance snapshots, saved runs and native decoder
sources are preserved. Simulation/replay commands remain configuration-driven.

## Exact paired bootstrap

The old implementation reconstructed all dictionary-derived statistics for every
bootstrap draw. The current implementation prepares additive integer sufficient
statistics once per compatible decoder pair. Each replicate draws the same unit
indices using the same seed/order as the preserved implementation, then weights
unit totals by their draw counts. Unequal batches retain their full shot counts;
ratios use sampled numerator/denominator totals. Null/unmeasured diagnostics remain
null and zero baseline totals yield null ratios.

Subtraction precedes conversion to binary64. A conservative bound selects int64
only when every possible reduction is safe; otherwise Python integers are used.
This preserves exact per-shot/aggregate accounting, including totals beyond int64.
No batch pooling, reduced bootstrap count, changed random sampling, dropped failed
shots or independent decoder resampling is used for speed. Replay groups stay
separate. Conditional denominators, zero-event bounds and insufficient tails retain
their previous meanings. Tests compare complete estimates, intervals and decisions
against the preserved implementation, including large integers and unequal batches.

Memory remains proportional to materialized run tables and per-comparison unit
statistics. This is not an out-of-core reader. Bootstrap is descriptive and does
not establish equivalence without the configured predeclared margin.

## Evidence

See STATUS.md and docs/test_results/analysis_migration_verification.json for the
full test command/result, verified requested-data report/notebook, output checksums,
and current consumer source audit. The initial suite failure (a test treating the
new analysis-only YAML as a simulation config) is preserved separately from the
corrected final run. No native/dependency source changed; no production simulation
was launched. The saved-data validation uses the user's existing 60,000 physical
shots, retaining 180,000 decoder rows and all protected contexts.
