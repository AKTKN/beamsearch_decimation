# Current saved-data notebook

`benchmark_analysis.ipynb.example` is the tracked template;
`benchmark_analysis.ipynb` is the editable local copy. Both use the active
`benchmark_results/3` result schema and read earlier `/2` files without
guessing convergence. The default run is
`assets/runs/2026_09_25_22_46_d822b5bc`. Set `QEC_ANALYSIS_RUN` or edit
`RUN_PATH` in the setup cell to select another active run.

```bash
conda activate search_decimation
jupyter execute --inplace --kernel_name=search_decimation notebook/benchmark_analysis.ipynb
```

The notebook discovers each saved `*_results.parquet` condition from
`config_resolved.json` and validates its schema. `CODES`, `PHYSICAL_RATES`,
`DISTANCES`, and `DECODERS` are optional selectors; `None` includes all saved
values. It displays a condition/decoder summary and saves PNG/PDF figures for
logical error rate, convergence rate when saved, mean complete-service wall
latency, mean total BP iterations,
and a wall-latency histogram for every selected condition under
`assets/analysis/<run-name>/`. The module plotting functions only return figures;
the notebook writes the files.

One physical BB shot is one block trial. Failed decoder calls remain in latency
and iteration statistics. Wilson intervals describe logical-error uncertainty;
Student-t intervals describe uncertainty in mean latency and iteration count.
With only one saved physical rate, the rate figures show points rather than a
trend. The result schema has no CPU time, correction vectors, per-observable
outcomes, or internal decoder events. The notebook performs no simulation or
decoding and does not change source run data.

The editable notebook may contain saved outputs after execution and is ignored by
Git. The tracked template has no saved outputs. Historical notebook consumers are
under `notebook/legacy/`.
