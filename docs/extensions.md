# Extension points and maintenance

- **Code provider:** extend the strict family model and circuits/providers.py, retain
  physical extraction of both sectors, explicit Z-check measurement provenance and
  complete logical mapping. Validate CSS/logical algebra and noiseless controlled
  faults; state schedule/boundary and circuit-distance limits. Artifacts must hash the
  actual circuit/DEM/mapping bytes and remain immutable.
- **Noise or DEM convention:** add explicit validated parameters and identity inputs,
  never silent approximations. Test fault-parity maps, separators, logical-only columns,
  zero normalization, prior constraints and reconstruction. All decoders share one
  canonical problem and no logical truth enters their interface.
- **Decoder:** add a discriminated configuration profile and DecoderAdapter branch,
  recording implementation/binary/source identity and all supported parameters. Own
  native state per worker, validate full H parity, predict through A only on valid
  output and propagate unexpected exceptions. Test direct APIs, fresh/reused/reordered
  shots and failure flags. All project per-pattern/per-iteration work stays native.
  Algorithm variants (warm starts, propagation, adaptive budgets or different BP) must
  use separately named profiles, not change the reference implementation invisibly.
- **Storage:** change schema versions deliberately and add round-trip/migration tests.
  Preserve physical sample pairing, nullable failures, uint64 seeds, complete BB vectors,
  atomic paired commit/no-overwrite behavior and incomplete-run readability. New fields
  must document units, availability, ownership and identity effects.
- **Analysis:** place reusable loading/statistics/plotting in analysis/, call it from
  notebooks/CLIs, and test hand-computable expectations. Keep run/model/noise/decoder/
  execution groups protected. Any future pooling requires an explicit policy including
  duplicate/replayed shots and dependent-observable uncertainty. Add native units and
  tail-support metadata to new timing statistics.

Configuration is frozen, rejects unknown fields and resolves paths relative to YAML.
CLI/shell wrappers contain no scientific settings. Timing encloses DecoderAdapter.decode
including input/reset/residual work/validation/prediction; do not move shot-dependent
work into untimed setup. Source edits require tests appropriate to the affected boundary,
updated module READMEs, dependency audit/patches, traceability and actual STATUS evidence.
The pinned dependencies and project are built in search_decimation; scientific smoke
validation stays small, with no automatic production sweep or performance claim.
