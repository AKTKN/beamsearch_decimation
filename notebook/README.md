# Notebook consumer

benchmark_analysis.ipynb contains only explicit run selection, calls to the installed
analysis package, and display. It never implements a decoder, samples circuits or
repeats statistics. Interactive users set RUN_PATHS and optionally CONFIG_PATH, or
QEC_ANALYSIS_RUN / QEC_ANALYSIS_CONFIG. Relative defaults discover the repository;
there are no hard-coded workstation paths in the source notebook.

Execute with the active search_decimation interpreter and an ephemeral local IPC
kernel (no dependency on the user's global python3 kernel registration):

```bash
scripts/execute_notebook.sh config/smoke.yaml --run /path/to/saved/run \
  --output assets/notebook/smoke_executed.ipynb
```

The output path must be new. Parameters are recorded in an injected first cell of
the executed artifact. The notebook prints its separately timestamped analysis
folder and displays its exported PNG figures; matching PDFs/JSON/manifests remain
there. Notebook dependencies are pinned in requirements.lock.txt and the `notebook`
project extra. Tiny smoke figures are software validation, not performance evidence.

The editable benchmark_analysis.ipynb and all executed notebooks are ignored.
The versioned benchmark_analysis.ipynb.example is an output-free portable template;
scripts/setup_local_files.sh creates a working copy only when missing. Existing
local notebooks are preserved.

The maintained .ipynb.example now also displays stage/cycle and paired-cost/error
JSON from the saved-data report. It contains no statistical implementation.
Execute it with `--notebook notebook/benchmark_analysis.ipynb.example` to use the
new template while preserving an edited local notebook. Bootstrap settings and
physical-trial repetition metadata are retained in the report manifest.

Final hybrid E2E acceptance executes the maintained template through the existing
CLI and verifies every code cell completed without error. The acceptance index
records the executed notebook hash and its separately saved report artifacts.
