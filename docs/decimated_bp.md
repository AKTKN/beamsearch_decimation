# Stateful hard-decimated BP API (Stage 2)

Stage-4 integration: the [project-native decoder](search_bp_stage4.md) now uses
this API and maps fixed signed infinities to signed DBL_MAX only at its OSD
boundary, as approved by the user. The generic fork implementation is unchanged.

The opt-in `ldpc.hybrid_bp.DecimatedMinSumSession` implements only parallel
minimum-sum BP, exact structural fixation, bounded LLR history and state transfer.
C++ consumers include `external_lib/ldpc/src_cpp/decimated_bp.hpp` and use
`ldpc::decimated::Session`, sharing a `shared_ptr<const ldpc::hybrid::Graph>`.
No SEARCH-BP scoring, selection, search, recursion, truth, or OSD orchestration
is implemented here. The existing `StatefulMinSumSession`, reference BP,
upstream BP/OSD and direct `Osd0Bridge` retain their source and behavior.

## Public API

```python
from ldpc.hybrid_bp import DecimatedMinSumSession

bp = DecimatedMinSumSession(
    rows=[[0, 1], [1, 2], [0, 2]], n=3,
    probabilities=[.1, .19, .27],
    history_window=3, history_clip=25., scaling_factor=.75,
)
bp.reset_from_channel([1, 0, 0], fixed=[], shot_id=7)
advance = bp.continue_iterations(5)
parent = bp.snapshot()
bp.inherit_descendant(parent, additional_fixations=[(0, 1)])
child_advance = bp.continue_iterations(4)
bp.restore(parent)
```

`rows` are sorted unique zero-based column indices per check, and probabilities
have shape `(N,)`, finite in `(0, 0.5]`. The graph owns copies of both. A session
owns all mutable buffers and is **non-reentrant**; callers must serialize access
to the same session. Separate sessions may run independently. Python mutation
methods release the GIL; Python array properties return detached list copies.
Native const views last until the next mutation or destruction.

| Method/property | Contract |
|---|---|
| `reset_from_channel(syndrome, fixed=[], shot_id=0)` | Binary `(M,)` syndrome; complete sorted unique `(index, 0/1)` pattern. Replaces prior messages, fixations, counters and history. Disables every edge of a fixed column and XORs fixed-one contributions. |
| `continue_iterations(requested_iterations)` | Nonnegative signed-int64 budget. Returns requested, actual and instance-total iteration counts, status and `valid`. Checks validity/contradiction before work and after each complete parallel round. |
| `snapshot()` | Owned immutable-by-interface state copy; no borrowed buffers. C++ snapshots support ordinary copy/move construction and assignment. |
| `restore(snapshot)` | Requires an already reset session with the same graph/prior identity, shot token, original syndrome, scaling, W and L_c. Restores counters/history as well as messages. A new matching session can restore after reset. |
| `inherit_descendant(snapshot, additional_fixations)` | Same compatibility checks as restore; additions must be nonempty, sorted, unique and disjoint from ancestor fixations. Even reasserting an existing bit is rejected. Parent snapshot remains unchanged. |
| `decision` | Full binary `(N,)` correction, including exact fixed bits. Available even on nonconvergence/contradiction. |
| `posterior_llr` | Signed `(N,)` posterior; fixed bits use positive infinity for 0, negative infinity for 1, representing exact fixation. Free posteriors stay finite. |
| `check_to_variable` | Exact edge-aligned check-to-variable messages from the last completed iteration. The session and snapshot expose the same owned buffer; reset initializes it to zero. |
| `fixed`, `residual_syndrome` | `(N,)` mask with -1 free, 0/1 fixed; binary `(M,)` residual. |
| `clipped_mean_llr`, `history_count`, `total_iterations` | `(N,)` bounded mean, number of real completed samples currently retained, and rounds completed since reset/inheritance. |
| `status` | Current `READY`, `CONVERGED`, or `LOCAL_CONTRADICTION`. An advance result instead reports `BUDGET_EXHAUSTED` when its budget ends without a terminal state. |
| `snapshot_payload_bytes` | Allocated logical vector payload of a snapshot, excluding container/allocator/control overhead. |

`DecimatedBPAdvance.actual_iterations` counts full rounds only, never requested
work or the channel/transition decision. A valid initial/transition decision or
local contradiction consumes zero rounds. Repeated calls on a converged state
consume zero. Early convergence is `valid` with `actual_iterations <
requested_iterations`; convergence exactly at the budget boundary remains valid.
This is a BP result, not a claim of minimum physical cost.

Malformed dimensions, priors, masks, budgets and incompatible snapshots raise
`ValueError` (`std::invalid_argument`); unavailable state raises `RuntimeError`
(`std::logic_error`). Unrepresentable ring sizes raise `std::length_error` and
allocation failure propagates. Invalid reset or inheritance invalidates the
session until another reset. Rejected restore or iteration budgets leave valid
prior state unchanged. Snapshots cannot be constructed or edited from Python;
their C++ buffers are private and read-only through accessors. Shot tokens are
caller-assigned: use a distinct token per physical shot to reject old snapshots.

## Continuation, inheritance and history

Each full round consumes old variable-to-check messages for all checks, then
updates free-variable posteriors and completes all new extrinsic messages.
Continuation preserves that state exactly, including the trailing history across
separate calls. A strict descendant preserves ancestor free-edge messages and
free posterior decisions, disables newly fixed edges, applies the new residual,
and immediately tests the reconstructed full correction. Its next round updates
all remaining checks using that inherited state. There is no cold restart of free
messages. The exact check-to-variable array produced by that completed round is
part of the snapshot. Restore copies it without recomputation; descendant
reconstruction zeros only edges belonging to fixed columns. The next complete
round overwrites every remaining active check message before it is consumed.

A descendant starts a **fresh history and instance iteration counter**. Old
posterior samples describe a different masked BP instance; they are not silently
included in the descendant's time average. This policy is explicit because the
root TeX leaves inherited-history handling unspecified.

The ring stores at most W clipped posterior samples per free variable in an
allocated contiguous `(W,N)` array. A `(N,)` running sum subtracts the evicted
entry and adds the new sample. Update work is O(N) per round, with no allocation;
memory is O(NW). Exact sliding-window removal needs the evicted values, so a
clear ring is used instead of an approximate O(N) history. No tanh/confidence,
check ambiguity, or per-iteration event record is produced.

With W completed samples the mean implements `refined.tex`'s `eq:average_llr`:
clip each posterior, then average. With fewer samples it divides by the **actual
sample count**, exposed as `history_count`. With zero samples it returns clipped
current LLRs and count zero, without pretending the channel/transition state is
an iteration. Fixed entries are signed +/-L_c placeholders; every consumer must
exclude them using `fixed`. Future SEARCH-BP orchestration must explicitly handle
short history; this utility convention does not rewrite the TeX's full-window rule.

## Snapshot and session memory

Let E be original edge count, N variable count, M check count. Snapshot payload:

| Contents | Bytes |
|---|---:|
| Variable-to-check messages q | 8E |
| Final check-to-variable messages | 8E |
| Current signed LLRs and rolling sums | 16N |
| Clipped history ring | 8NW |
| Fixed mask and original syndrome | N + M |

Total logical vector payload is **8(2E + NW + 2N) + N + M** bytes, plus fixed-size
metadata/container overhead. Metadata is model/shot/iteration identity, window
size/count/cursor and scaling/clip values. Rolling sums are saved to preserve
floating-point continuation order exactly. Graph, probabilities, adjacency,
decision, residual and derived means are not duplicated in a snapshot. The session
additionally holds only decision/residual buffers (N+M) and a shared immutable
graph; its former 8E check-message workspace is now the snapshot-owned array, so
total session vector payload is unchanged. A mean query creates
one N-double return vector outside the iteration loop. Snapshot copying costs
O(E+NW+N+M); moves transfer vector ownership. Reset/restore/inheritance reuse
preallocated same-shape vectors, as do all iterations.

## Numerical conventions for later SEARCH-BP stages

- Binary64, C++17, no fast-math or contraction. Physical LLRs use the existing
  graph convention `log1p(-p) - log(p) = log(P(0)/P(1))`.
- Parallel normalized min-sum scaling is finite in `(0,1]`. The upstream optional
  zero-scaling adaptive schedule is **not** supported by this API.
- Hard decisions and check-message signs use `LLR <= 0` as bit one, including
  signed zero, matching pinned parallel min-sum. Original index order breaks
  equal minima deterministically. The initial decision is checked before any
  iteration, unlike upstream C++ BP's unconditional first round.
- L_c clips history only. It never clips BP priors, edge messages or posteriors.
  Degree-one checks use the upstream `DBL_MAX` magnitude sentinel, scaled normally.
  Prefix/suffix variable sums avoid subtracting saturated posteriors. Additions
  saturate only on binary64 overflow to +/-DBL_MAX, preventing infinities/NaNs in
  free messages. This defined extreme-value policy differs from upstream overflow;
  ordinary finite-regime equivalence is tested. No narrow soft-hint clip is used.
- To prevent accumulator overflow, `L_c <= DBL_MAX/(2W)` is required. Running-sum
  rounding can differ from recomputing a window sum; tests use a tight binary64
  tolerance. Splitting calls or restoring a snapshot preserves exact state.
- Fixed posterior infinities are exact delta constraints, never fed into message
  arithmetic. The unchanged OSD bridge requires **finite** signed input. A later
  project-native fallback must explicitly define fixed-column OSD reliability;
  this stage does not invent that SEARCH-BP policy or call OSD from BP.

## Build and evidence

The new header is in `ldpc.hybrid_bp.source_files.SOURCE_FILES`, so the established
fork patch/source audit, opt-in build identity and project transitive digest cover
it and the binding. Run in `search_decimation`:

```bash
(cd external_lib/ldpc && python setup_hybrid.py build_ext --inplace)
python python_scripts/audit_dependencies.py
python -m pip install --no-build-isolation --no-deps -e .
scripts/build_dependencies.sh --check
python -m pytest -q
python tests/check_hybrid_restoration.py
```

`tests/test_decimated_bp.py` is the fork-facing Python suite; its scalar oracle
uses explicit excluded-edge sums/minima. `tests/native/test_decimated_bp.cpp`
adds 360 pinned C++ BP comparisons and state/history checks; it participates in
Debug, sanitizer and clean-restoration builds. STATUS.md records actual outcomes.
