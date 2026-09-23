# LPM-DP 1.0 Stage 2: exact final check messages

The Stage-0 audit found that `ldpc::decimated::Session::iteration()` already
computes the required final check-to-variable message
`mu_(a->j)^(T)` in its `z_` workspace and uses that same value to form the
completed iteration's posterior and next variable-to-check messages. The buffer
was neither owned by `Snapshot` nor preserved by `restore()`: restore explicitly
zeroed it. Consequently the exact completed-iteration value needed by
`local_parity_decimation_note.tex` was unavailable and a fork change was required.

## Minimal API and ownership change

`Snapshot` now owns the existing edge-aligned check-message vector. No second
copy remains in `Session`; iteration writes `state_.z_` directly. The native API
adds `Snapshot::check_to_variable()` and `Session::check_to_variable()`, and the
Python opt-in binding exposes read-only `check_to_variable` properties. Python
receives detached lists only at that public diagnostic/test boundary; no Python
processing was added to a decoding loop.

Reset initializes the array to zero. A completed parallel round first overwrites
every active entry from the previous `q` array, then uses those exact entries for
the posterior and extrinsic update. Restore copies the array exactly and performs
no check update or reconstruction approximation. Descendant reconstruction zeros
the messages on all fixed columns, including newly fixed columns; free entries
remain the parent's exact final messages until the next round overwrites all of
them before use. BP equations, stopping, hard decisions, Beam Search, BP-OSD and
SEARCH-BP orchestration are unchanged.

One snapshot owns:

- fixed mask `(N,)` and original syndrome `(M,)`;
- variable-to-check messages `(E,)`;
- final check-to-variable messages `(E,)`;
- current posterior LLRs `(N,)`;
- clipped LLR-history ring `(W,N)` and running sums `(N,)`;
- model/shot identity, completed-iteration count, history window/count/cursor,
  scaling factor and clip metadata.

It does not own the shared immutable graph/probabilities/adjacency, residual
syndrome, current decision or a derived mean. Residual and decision are reusable
session buffers reconstructed from the snapshot's original syndrome, fixed mask
and posterior. Keeping final check messages only in the reusable session would be
incorrect for several retained parents: restoring a parent must also restore the
exact array associated with that parent's completed iteration. Defaulted C++
copy operations deep-copy all vectors; defaulted moves transfer their ownership.

## Exact logical live memory gate

For binary64 messages, byte-sized masks/syndromes, `E` edges, `N` variables,
`M` checks and history window `W`:

```
snapshot before = 8(E  + NW + 2N) + N + M
snapshot after  = 8(2E + NW + 2N) + N + M
eight parents   = 8 * snapshot after
session after   = snapshot after + N + M
one child       = snapshot after
```

These are exact logical vector payloads; fixed-size C++ vector/control objects and
allocator bookkeeping are excluded. The session total is unchanged: the new 8E
snapshot array is the old 8E session workspace moved into owned state. A child
evaluated in the reusable session needs no second child snapshot until it is
materialized for retention; the table conservatively counts one materialized
temporary child.

The largest checked-in model is BB72 d6/r6 with `M=252`, `N=2232`, `E=7776`.
At `W=8`:

| Quantity | Before | After |
|---|---:|---:|
| One retained parent snapshot | 243,252 B | 305,460 B |
| `B_keep=8` parents | 1,946,016 B | 2,443,680 B |
| Reusable session | 307,944 B | 307,944 B |
| One materialized temporary child | 243,252 B | 305,460 B |

The conservative simultaneous total for eight retained parents, the reusable
session and one materialized child is 3,057,084 vector-payload bytes after the
change. On the validation GCC/libstdc++ ABI, `sizeof(Snapshot)` is 232 bytes after
the change (208 before) and `sizeof(Session)` is 304 bytes both before and after.
Including those inline objects, but necessarily excluding implementation-specific
heap allocator bookkeeping, the requested live figures are:

| Quantity | Before | After |
|---|---:|---:|
| Bytes per retained parent snapshot | 243,460 B | 305,692 B |
| Bytes for `B_keep=8` parents | 1,947,680 B | 2,445,536 B |
| Bytes for reusable session | 308,248 B | 308,248 B |
| Bytes for one temporary child | 243,460 B | 305,692 B |

The corresponding conservative simultaneous live total is 3,059,476 bytes.
Storage is
`O((B_keep+1)(E+NW+N+M))`; there is no
`raw_candidate_count * E` or `raw_candidate_count * N` allocation and no
truncation cap was introduced.

## Verification

`tests/test_decimated_bp.py` compares every exposed final check message with an
independent scalar excluded-edge min-sum calculation on every completed round,
and independently rebuilds each posterior from those messages. It verifies
detached Python ownership, exact snapshot restore and zero `q`/check messages on
fixed columns before and after child iteration. `tests/native/test_decimated_bp.cpp`
checks copy construction, copy assignment, move construction, move assignment,
restore and child masking in native C++ in addition to its pinned BP comparisons.

The fork patch/source manifest, clean restoration, upstream tests, native tests,
and deterministic Beam Search, BP-OSD and SEARCH-BP regressions are regenerated
and recorded in `STATUS.md`. No Stage-3 decoder work is included.
