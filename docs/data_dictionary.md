# search_bp typed data dictionary

New search_bp runs use `search_bp_parquet/2`. The normative field types,
nullability, enums, primary keys and partition columns are defined in
`specifications/search_bp_parquet_schema.json`; the implementation
does not infer schemas.

The physical key is `(run_id, condition_id, shot_id)`. Adding `decoder_id` gives a
decode key. `shot_inputs` stores syndrome and truth once. `decode_results` stores
one normalized invocation per enabled decoder. V2 invocations additionally have
exactly one `search_summary` and `bp_summary`; their event grains are `cycles`,
`patterns`, `bp_updates`, `bp_beam_membership`, `solution_events`, `osd_calls`,
optional `phase_timings`, and optional debug `search_nodes`. `conditions` and
`decoder_profiles` are static run tables.

Bit vectors are packed little-endian. Dimensions come from `conditions`; byte
lengths and zero high padding are validated. Scores are finite binary64. IDs and
counters are uint64 unless the contract declares a uint32 index. Durations are
nonnegative signed int64 nanoseconds. Null means unavailable or inapplicable, not
zero. Every valid solution event receives its own offline truth label; earlier
events never inherit the final winner's label.

The inventory validator verifies file hashes and Arrow metadata, exact keys and
foreign keys, complete shot/decoder pairing, vector dimensions, pattern canonicality,
donor provenance, cycle continuity, summary/event counter equations, final winner
agreement and phase sums. Analysis loads only inventory-listed shards.
