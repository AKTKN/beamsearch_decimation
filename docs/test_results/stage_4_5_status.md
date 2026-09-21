# Implementation status — stages 1–5 complete

Implemented and verified in the `search_decimation` conda environment on 21 September
2026 (Asia/Tokyo). The requested scope ends at Stage 5. No production sweep was run.
Stages 6 (analysis/notebooks) and 7 (clean-environment acceptance) remain unfinished.
The historical Stage 1–3 status is preserved in docs/test_results/stage_1_3_status.md.

## Delivered

- Stages 1–3: strict YAML/identities and pinned native builds; physical surface
  d=5,7,9 and BB [[72,12,6]] Z-memory circuits with R=d; common circuit noise and
  verified Z-check projection; canonical undecomposed DEM artifacts preserving
  hyperedges/separators/logical-only mechanisms; forked opt-in C++ flooding BP.
- Stage 4: project C++ static-U exhaustive fixed-q enumeration, structural residual
  scoring with all-free-variable lower bounds, exact bounded-heap top K, cold-start
  completion of every retained pattern and physical-cost/lexicographic selection.
  Typed common adapters use the actual unchanged BP-OSD and published beam matrix
  APIs. All per-pattern work, including optional diagnostic formatting, is native.
  Every output receives independent H validation and A prediction; failures have
  null correction/prediction/cost. Actual source/binary/adapter hashes identify builds.
- Stage 5: immutable lazy deterministic tasks; physical sampling once per batch;
  paired truth-free decoding; bounded spawn and serial scheduling; worker-local
  caches; complete per-shot CPU/wall timing and separate setup/warmup clocks;
  thread/affinity/load labels; versioned Arrow/Parquet schemas; atomic paired shards,
  checksums/counts, incomplete-run tracebacks and readable committed subsets;
  source/build/environment archives; saved-sample replay and thin YAML CLIs.

## Verification

Final command logs, six accepted run paths, row counts and paired-comparison evidence
are in docs/test_results/stage_4_5_summary.json and neighboring stage_4_5/stage_5 logs.

| Check | Result |
|---|---|
| `python -m pip install --no-build-isolation -e .` | Optimized native extension built/installed |
| `python -m pytest -q` | **91 passed**, including actual native serial/spawn/replay tests |
| Full screened C++ versus independent Python orchestrator | **560 comparisons**, including reversed shot order |
| Unmodified fork BP-OSD versus pristine pinned build | **288 comparisons**, included in suite |
| `ctest --test-dir build/debug --output-on-failure` | **2/2 passed**, BP and search |
| `ctest --test-dir build/sanitize --output-on-failure` | **2/2 passed**, ASan and UBSan |
| `scripts/build_dependencies.sh --check` | Intended fork/beam/Stim/qLDPC imports verified |
| Four-shot all-four-code one/two-worker/isolated runs | Identical physical samples and non-timing decoder results |
| `config/smoke.yaml` versus `config/latency_smoke.yaml` | 128 samples and 384 decode rows each; non-timing results identical |
| Replay with an added screened K=4 configuration | Physical samples and all shared-decoder scientific results identical |
| Production-template runner invocation | Expected validation error for empty physical grid, before run creation |

The tests cover worked-example scores, exact small-system lower bounds/top K/IDs,
initial success, fixed-zero/one rescue, no completion, multiple successful costs,
full reconstruction, direct upstream adapters, shot reset, all 12 BB observables,
short batches, bounded out-of-order completion, warmup isolation, input pairing,
complete timing boundaries, optional diagnostic/phase output, worker/run exceptions,
uint64/null/schema round trips, duplicate guards, failure between shard publications,
partial-run replay, preserved source bytes and Git worktree metadata files.

## Entry points and outputs

```bash
conda activate search_decimation
scripts/run_benchmark.sh config/stage5_validation.yaml
scripts/run_benchmark.sh config/smoke.yaml
scripts/run_benchmark.sh config/latency_smoke.yaml
scripts/replay_samples.sh /path/to/source/run config/decoder_sweep.yaml
```

The serial and isolated four-shot variants are stage5_validation_serial.yaml and
stage5_validation_latency.yaml. All scientific settings come from YAML. Every run
uses a new UTC timestamp/nonce directory under output.root (default assets/runs/),
with copied immutable artifacts and sources. Replay uses source batches as its
physical plan and the new YAML's decoder/execution/output configuration.

See docs/pipeline.md, docs/configuration.md, docs/traceability.md and the native,
decoders, runner, storage and provenance READMEs. Existing Stage 1–3 circuit artifacts
remain unchanged; simulation_data/stage_1_3_validation_index.json identifies them.
Exact dependency versions/imports/commits/build flags and the opt-in fork patch are
in external_lib/manifest.lock.json. Added runtime dependencies are pyarrow 25.0.1
and threadpoolctl 3.7.0. The project remains a local workspace without root Git
metadata; nothing was published and no hosted fork was created.

## Limits

No unresolved Stage 4–5 blocker remains. Smoke data validate software, not decoder
performance. The reference implementation allocates residual graphs per candidate
and uses literal exclusion products/sums; no latency advantage is claimed. The BB
schedule is qLDPC edge coloring, not the paper's optimized seven-layer schedule,
and published distance six is not a proof of circuit distance. Thread/affinity
settings control this run, not unrelated host activity. Baseline unavailable search
counters remain null. Stim bitwise resampling requires a fixed environment and
batch plan; stored samples provide exact replay. In-place resume is not implemented.
Analysis, notebooks, large experiments and clean-environment acceptance were not run.
