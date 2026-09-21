# Saved-data notebook consumer

`benchmark_analysis.ipynb.example` is the maintained hybrid/baseline consumer.
It reads verified v1/v2 runs, uses analysis-only settings, and displays
failure and timing summaries with selected PNG/PDF plots. It contains no simulation, decoding,
or statistical implementation. BB uses one physical block trial with all 12 labels.

```bash
conda activate search_decimation
scripts/execute_notebook.sh config/analysis.yaml.example --run /path/to/saved/run \
  --output assets/notebook/new.ipynb
```

The CLI defaults to the maintained template, independent of a stale or edited local
`benchmark_analysis.ipynb`. To execute an edited notebook, pass `--notebook PATH`.
It creates an ephemeral IPC kernel using the current interpreter; `--timeout` sets
seconds per cell (600 by default, -1 disables the limit). Output must be new.
Parameters are recorded in an injected first cell. Statistics and progress messages
are captured in outputs; the CLI prints only the completed notebook path.

Interactive use: register the current environment once, then select
**Python (search_decimation)**, restart the kernel and execute all cells:

```bash
conda activate search_decimation
python -m ipykernel install --user --name search_decimation \
  --display-name 'Python (search_decimation)'
```

Set RUN_PATHS explicitly and optionally CONFIG_PATH, or use QEC_ANALYSIS_RUN and
QEC_ANALYSIS_CONFIG. Defaults find config/analysis.yaml.example from the repository.
The first cell checks the analysis API/checkout and displays interpreter/source
paths. It raises an actionable error for an archived acceptance package instead of
attempting to change sys.path or reload an already-imported decoder package.

The notebook validates and loads saved runs once, then keeps `records`, `failures`
and `timings` in memory. Separate cells aggregate failure rates with analytic Wilson
intervals, summarize measured timings and draw configured PNG/PDF figures. Rerunning
the plotting cell creates a new figure directory without reloading the data.
There is no report manifest/JSON export, bootstrap, hybrid stage analysis or paired
hypothesis comparison. Relevant settings are output, confidence, quantiles, plots,
timing strata and tail-support threshold. Bootstrap/accuracy-margin settings apply
only to the separate full-report CLI. Loading still verifies all saved-data integrity
and materializes the selected runs; large datasets can remain expensive to load.

Editable notebooks and executed artifacts are ignored. setup_local_files.sh creates
missing copies only, including notebook/legacy/, and preserves local edits/symlinks.
The pre-migration template and consumers remain in notebook/legacy/ and
analysis.legacy; use scripts/legacy/execute_notebook.sh for that workflow.
See docs/analysis_migration.md for actual migration verification and limits.

The local `benchmark_analysis.ipynb` is an interactive path-editable template for
the current analysis API. Edit CONFIG_PATH and RUN_PATHS in its first code cell,
then run all cells with search_decimation. Paths may be absolute, home-relative,
or repository-relative. Its explicit path cell is intended for interactive use;
for CLI-injected parameters, use the maintained `.ipynb.example` default instead.
The local template contains no saved outputs or statistical implementation.

### Local notebook: trusted, on-demand plotting

At the user's request, the local `benchmark_analysis.ipynb` now differs from the
maintained `.ipynb.example`: setup reads configuration only. Each of five separate
plot cells calls `analysis.quick_plots.plot_saved_data` to read just its required
Parquet decode columns. Run only the desired plot cells. There is no shared load,
summary table, integrity verification, bootstrap, hybrid comparison or timing-path
stratification in this local notebook. PNG/PDF output uses a fresh per-plot folder.
Input paths are retained. The maintained CLI template still uses verified loading.
