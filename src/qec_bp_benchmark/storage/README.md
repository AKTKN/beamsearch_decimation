# Arrow and paired storage

`schema.py` defines explicit version 1 samples/decodes schemas (metadata includes
little bit order). Identifiers and required values are non-null. Batch seeds/shot
indices/candidate counts use uint64, durations use signed int64 nanoseconds. Raw
selected detector bits and optional corrections use numpy.packbits(bitorder=little),
with zero high padding. Actual and predicted observable vectors retain all k_Z bits,
including all 12 BB observables. n is physical code length; correction dimension is
the number of canonical mechanisms in saved H, not n.

Samples occur once per shot; decodes are long-form one row per shot and decoder ID.
Common columns include run/instance/sampling/batch/shot IDs, physical metadata,
noise/model/source/config hashes. Decode rows include native/normalized status,
validity, predictions, physical cost, CPU/wall ns, execution/thread/profiling labels,
optional native counters, selected pattern, traces and correction. A full source
hash addresses archived bytes; decoder IDs include actual binary and adapter hashes.

Decoding failure = declared failure OR invalid correction. Block failure = decoding
failure OR any valid logical mismatch. valid_logical_mismatch is false on failed
decodes (an unconditional contribution with denominator all shots). The per-observable
mismatch vector is null on failure; observable_total_failure counts a failure for
every observable on failed decodes. Conditional mismatch uses valid_outputs as its
denominator, with null rate when that denominator is zero. Failed predictions,
corrections and costs are null; unavailable counters are null. No NaN sentinel.

commit_batch validates exact pairing/labels/schema, writes and fsyncs both temporary
Parquet files, atomically links each to an exclusive final path, then publishes the
commit manifest last. Atomic links provide no-overwrite publication on the same
filesystem, stronger than replacement for shards. Run manifests use atomic replace.
Checksums/counts are in per-batch manifests. An orphan shard cannot be overwritten
or read as committed; use a new run. committed_batches validates checksums, exact
schemas and pairing, independent of the enclosing run's complete/incomplete status.
No resume or partial-batch recovery is claimed. Interrupted readable batches can be
replayed into a new run. Parent completion requires every planned batch/decoder,
correct per-instance shot counts and non-overlapping intervals.

## Current hybrid migration

The v1 descriptions above are retained for historical files. New runner output
uses run/batch v2 and decodes/2: invalid valid_logical_mismatch is null. samples/1
is unchanged. `schema.py` retains both exact versions and declares hybrid_rounds/1
and decoder_phases/1. `telemetry.py` labels owned post-service events and validates
foreign keys, terminal/candidate labels, counters, durations and signed residuals.
Under phases, commit_batch(version=2) publishes four typed shards (including empty
events) before its marker. Under none it explicitly omits events. Existing callers
may still explicitly write v1. See docs/hybrid_data.md for all fields and units.

Final acceptance also checks the enumerated phase result, the successful terminal
phase's kind/position, OSD reach versus terminal stage, and separation of prefix
phase intervals from the OSD interval. Corrupt event metadata is rejected even
when its foreign keys, row counts and arithmetic duration sums are consistent.
