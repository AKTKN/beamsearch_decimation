# Minimal simulation output: search_bp_results/2

SEARCH-BP-2.1 uses this schema. Decoder-only
microbenchmark/profile evidence lives under `docs/test_results/`, outside run
directories; it adds no production telemetry or columns. See the
[active implementation audit](search_bp_implementation.md).

Every new run contains exactly:

```text
YYYY_MM_DD_HH_MM_<config-hash-8>/
  config_resolved.json
  data/
    <code>_d<distance>_r<rounds>_p<rate>_<basis>_results.parquet
```

The timestamp is local time. The suffix is the first eight hex digits of the
resolved configuration content hash. A collision is rejected, never overwritten.
Rate tags preserve decimal values without rounding: 0.003 is p003. The resolved
configuration stores physical conditions, decoder parameters and algorithm version,
noise, sampling plan, worker settings and timing mode once for the run. No schema
file, manifest, inventory, source/model/circuit copy, summary or file log is emitted.

There is one result file per physical condition, including a typed empty file if
execution fails before any row is saved. All enabled decoders share each physical
shot. The Arrow schema metadata is `qec_schema=search_bp_results/2`:

| Field | Arrow type | Meaning |
|---|---|---|
| shot_id | nonnull string | Existing instance:sampling:index identity; unique within a condition for a physical shot |
| decoder_name | nonnull string | Unique configured decoder name; parameters/version are in config_resolved.json |
| logical_error | nonnull bool | Decoder failure (declared or invalid) OR any logical mismatch |
| latency_ns | nonnull int64 | Nonnegative complete per-shot decoder service wall time |
| osd_called | nullable bool | Whether this invocation called OSD; null only for a baseline API that cannot establish it |
| correction_by_search | nullable bool | True only when SEARCH-BP local combinatorial search directly constructed a valid correction; false for initial/descendant BP, OSD and failure; null for other decoders |

The primary key within a condition file is (shot_id, decoder_name). SEARCH-BP-2.1
must provide exact boolean OSD and correction-by-search flags; null is rejected. Current baselines all
expose exact information: screened/beam do not call OSD; hybrid supplies its
native invocation flag; upstream BP-OSD calls OSD iff its nonzero-syndrome BP did
not converge. Zero-syndrome and algebraic empty-model exits are false, independent
of stale upstream flags. No convergence claim is inferred from OSD invocation.

`latency_ns` uses perf_counter_ns around the entire DecoderAdapter.decode call,
including syndrome input conversion, native decode, original-H validation,
A prediction, and physical cost computation. Construction, warmup, sampling,
truth comparison, result conversion and file I/O are outside that boundary.
Failed decodes remain in all latency and logical-error denominators. Logical
error is a block trial per physical shot, with no division by rounds or the 12
BB observables. No truth enters the decoder service.

No sample/syndrome/correction vectors, search nodes, BP iterations, candidate or
beam tables, solution events, phase breakdowns or raw messages are persisted.
The worker returns only six-field scalar result rows and generic batch metadata;
it does not construct or transport raw-sample or wide telemetry rows. The generic
scheduler keeps bounded physical batch futures. Parent shot grouping
uses output.parquet.shots_per_flush when minimal_results is configured, or the
physical batch size for compatible baseline Output configs. It creates one row
group per completed shot group plus the final partial group. Compression options
remain explicit. A Parquet row group is not an atomic multi-file batch commit.

Interrupted runs may contain closed partial files; readers report saved rows,
not completion. Buffered unsaved rows can be lost. There is no in-place resume,
manifest-based replay or final read-back validation. Use a new output directory.
Parent stderr progress reports completed batches, which may include buffered rows.

`analysis.simple_search_bp.summarize_run` reads named result files and config
without inventories. It reports logical-error count/rate/Wilson bounds, wall
latency including failures, OSD count/fraction, and direct-search correction
count/fraction over known flags with unknown counts separate. Zero-event intervals are bounds, not zero-risk claims;
small samples cannot establish tail precision. It processes one run at a time,
keeps physical conditions and decoder/execution settings separate, and rejects a
CPU-clock request because CPU latency is not saved in this contract. Earlier minimal `_logicalerror.parquet` files remain readable without being
rewritten. Historical
wide schemas dispatch to the legacy reader and are never relabeled as this schema.
Historical `search_bp_results/1` runs remain read-only and report the new search
indicator as unavailable; it cannot be reconstructed from their OSD flag.
