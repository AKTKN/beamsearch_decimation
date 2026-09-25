# Current saved-data notebook

`benchmark_analysis.ipynb.example` is the maintained current-layout consumer, and
`benchmark_analysis.ipynb` is its editable local copy. They read both
`search_bp_results/2` and `lpm_dp_results/1` through the public `analysis` summary
and plotting APIs. The configured default is the BB72 d6 LPM-DP run
`assets/runs/2026_09_23_16_16_7411703b`; set `QEC_ANALYSIS_RUN` or edit `RUN_PATH`
to analyze another supported current run.

The notebook performs no simulation or decoding. One BB physical shot is one block
trial across all 12 logical labels. The current schemas supply only the saved
logical-error boolean, complete wall latency and OSD-called flag. SEARCH-BP's
six-field schema additionally saves its exact direct-search correction flag;
LPM-DP's five-field schema does not. CPU time,
failure components, correction vectors and internal decoder telemetry cannot be
reconstructed.

Activate the required environment and execute the local notebook with:

```bash
conda activate search_decimation
jupyter execute --inplace --kernel_name=search_decimation \
  notebook/benchmark_analysis.ipynb
```

For interactive use, register the environment once and select it in Jupyter:

```bash
conda activate search_decimation
python -m ipykernel install --user --name search_decimation \
  --display-name 'Python (search_decimation)'
```

The setup cell checks that `analysis` comes from this checkout and that the selected
run contains resolved config. `CODES`, `PHYSICAL_RATES`, `DISTANCES` and `DECODERS`
are optional exact selectors. `None` includes every saved value. The histogram has
its own single-condition code/rate/distance selectors.

The summary table reports shots, logical-error counts and Wilson intervals,
mean/median/p95/p99 wall latency, and OSD counts with known and unknown denominators.
Figure cells create logical-error curves, mean wall-latency curves, and a
selected-condition latency histogram. They save PNG/PDF under
`assets/analysis/<run-name>/`. The event table reports OSD-call rates for each
decoder over its nonnull saved flags. A separate table cell selects the
`correction_by_search_rate` columns when stored. LPM-DP and legacy results/1 runs
show that metric as unavailable rather than inferring it.

The notebook keeps different run/execution contexts separate and does not bootstrap,
pool runs, build a report manifest or infer unavailable metrics. Throughput wall
times include failed decoder calls and worker contention. The bounded run does not
establish production accuracy, tail latency or decoder superiority.

The editable notebook may contain saved outputs after execution and is ignored by
Git. The maintained `.ipynb.example` has no saved outputs. Historical verified
v1/v2 notebook consumers and execution scripts remain under `notebook/legacy/`,
`analysis/legacy/` and `scripts/legacy/`.
