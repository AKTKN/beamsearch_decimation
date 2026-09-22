# HSBP-FB run manifest

Schema-version 3 manifests identify `HSBP-FB-2.0`, `hsbp_fb_config/1` and
`hsbp_fb_parquet/1`, and embed the fully resolved configuration, deterministic
sampling recipe, timing/thread policy, source/environment provenance, decoder
implementation identities, condition artifacts, dataset schemas and observed
validation counts. Static tables and `inventory/committed_batches.json` complete
the manifest's typed data description.

Workers produce bounded private tables. The parent validates, writes and closes
temporary Parquet shards, checks their schemas, atomically renames all files, and
publishes the batch inventory entry last. Empty datasets remain declared with zero
rows and shards. Missing/corrupt published files fail validation; unlisted orphan
files are ignored. IDs do not depend on worker completion order.

An interrupted run remains `incomplete`; its committed batches may be inspected or
replayed. This repository deliberately creates a new timestamped directory instead
of resuming in place. Replay copies and verifies model artifacts and decodes the
saved `shot_inputs`; it does not resample or reinterpret the YAML physical grid.
