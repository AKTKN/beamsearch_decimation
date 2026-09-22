# Minimal simulation output

The current runner saves one directory per invocation:

```text
output.root/
  YYYY_MM_DD_HH_MM_<config-hash-8>/
    config_resolved.json
    data/
      <code>_d<distance>_r<rounds>_p<rate>_<basis>_<dataset>.parquet
```

The timestamp uses the machine's local timezone. The final eight hexadecimal
characters are the first eight characters of the SHA-256 content identity of
the exact `config_resolved.json` value. A duplicate config in the same minute is
rejected instead of overwriting data.

The physical-rate tag removes `0.` without rounding: `0.003` becomes `p003`,
`0.01` becomes `p01`, and `0.5` becomes `p5`. For example:

```text
bb72_d6_r6_p003_Z_logicalerror.parquet
```

`logicalerror.parquet` contains the per-shot/per-decoder result and logical
failure labels. `samples.parquet` contains sampled detector and observable data.
Hybrid/frontier telemetry keeps its descriptive dataset suffix, such as
`cycles`, `bp_updates`, or `solution_events`. Typed empty files are retained when
a configured telemetry dataset produced no rows.

Circuit text, detector-error models, check matrices, source archives, manifests,
inventories, summaries, schemas, and log files are not copied into the result
directory. Prepared circuit inputs remain in `circuit.cache` and are referenced
only while the simulation runs. Worker errors are reported on stderr; after an
error the result directory still has the same two-entry shape and may contain
readable partial Parquet data.

The runner does not perform an end-of-run read-back/checksum validation pass.
Strict config validation, typed conversion when writing Parquet, and the decoder's
truth-free H/A correctness boundary remain active. `analysis.simple_search_bp`
reads the new files directly without manifests or inventories.

`analysis.simple_search_bp.summarize_run` reads both standard and frontier files
directly; `summarize_frontier_run` remains as a compatibility alias.

For `search_bp`, a worker emits one column-oriented chunk after all decoders for a
physical shot finish. The worker delivers that chunk before its physical sampling
batch completes. Multi-worker runs use a bounded queue with writer backpressure;
they do not accumulate a complete batch of telemetry in each future. The parent
coalesces the configured `shots_per_flush` completed shots independently for each
condition. Every nonempty dataset in that group is written as one Parquet row group;
a final smaller group is flushed before close. Empty typed files are still created
once and contain no row groups.

The active path does not construct the historical generic `results`, `rounds`, or
`phases` rows alongside typed search_bp data. Native search_bp events cross the
binding as Arrow-compatible column mappings rather than accumulated per-event
Python dictionaries. The schema and scientific fields are unchanged. Output memory
is bounded by the queue plus the configured shot groups, but all telemetry produced
by one such group must fit in memory; no decoder work limit is introduced here.

The former manifest/shard/replay format is historical code under the existing
legacy modules and is not emitted by the current runner.
