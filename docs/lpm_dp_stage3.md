# LPM-DP-BP-1.0 Stage 3: native decoder state machine

Stage 3 implements the complete native recursive BP state machine without adding
a Python binding, configuration model, adapter, worker route or simulator profile.
Its distinct identity is:

| Field | Value |
|---|---|
| kind | `lpm_dp_bp` |
| profile/name | `lpm_dp_bp_v1` |
| algorithm version | `LPM-DP-BP-1.0` |

The implementation is `native/lpm_dp_decoder.hpp`. `DecoderSettings` centrally
validates the note's eight candidate-generator parameters plus root/child BP
budgets, retained-parent count, cycle count, min-sum scaling and optional OSD-0.
Its defaults exactly match `local_parity_decimation_note.tex`: 30 root iterations,
20 child iterations, eight parents, ten cycles, scaling one and no OSD fallback.
Both iteration budgets must be at least the eight-sample history window.

## Architecture and state machine

The decoder owns one immutable graph/model, one non-reentrant hard-decimated BP
session and one native OSD-0 bridge. Each retained `ParentState` owns one BP
snapshot, the complete canonical fixation pattern, the post-BP retention score and
a monotone child ID. The exact clipped mean is
derived after restoring each parent into the reusable session; it is not duplicated
in retained states. The graph and history ring likewise are not copied separately.

For each shot the decoder:

1. resets BP from the physical channel, runs the root budget and returns only if
   the correction passes the original `H/s`;
2. captures the unsuccessful root only after a complete `W`-sample history;
3. processes retained parents in prior retention order and generates at most `K`
   locally ordered LPM-DP patterns independently for each parent;
4. restores that parent's snapshot for every pattern, structurally adds the new
   hard fixations, rejects zero-degree contradictions before an iteration, and
   retains ancestor fixations and all free variable-to-check messages;
5. resets child history through `inherit_descendant`, runs the child BP budget,
   and returns the first correction that passes the original `H/s`;
6. scores each remaining noncontradictory child by the main-note reliability
   equation and inserts it into an online, deterministically ordered top-`B_keep`;
7. destroys the old generation, promotes the retained children and repeats;
8. returns declared failure after bounded exhaustion, or calls native OSD-0 once
   if explicitly enabled.

When candidate preprocessing finds zero residual syndrome, the decoder constructs
the note's existing fixed completion (fixed values plus zero free variables),
validates it against the original `H/s`, and returns it. This is verification of
an existing conditioned solution, not a candidate-generated correction search.

Candidate local probabilities are never compared between parents. There is no
global run quota: eight parents and `K=2` permit sixteen sequential child BP
evaluations in a cycle. Children with identical full fixation patterns are not
merged because their inherited messages can differ. Ties are descending
reliability, full-pattern lexicographic order, then child ID.

## Reuse and exclusions

Reused components are only the Stage-1 LPM-DP generator, the Stage-2
`ldpc::decimated::Session`, immutable graph conventions, and the existing native
OSD-0 bridge/fallback LLR convention. No SEARCH-BP search or admission header is
included. In particular the decoder does not use `LocalSearch`, `f_solve`,
fractional completion costs, `f_guide`, ambiguity gain, solve/guide quotas, global
admission or search-produced corrections. The SEARCH-BP-2.1 implementation and
identity are unchanged.

The generator additionally accepts `AveragedParentView`. The decoder supplies the
session's exact running-sum mean only after `history_count == W`; focused tests
prove agreement with the original explicit-history interface on a non-wrapped
fixture. This avoids an otherwise redundant `O(NW)` history copy per parent. The
decoder deliberately inherits the current decimation API's documented running-sum
addition order; after ring eviction it is mathematically the same clipped mean but
is not claimed bitwise identical to resumming the ring in chronological order.

## Bounded live memory

Let

```
S = 8(2E + NW + 2N) + N + M
P(D) = S + 8D
Q = S + N + M
```

where `S` is snapshot vector payload, `P(D)` adds a retained state's `D` canonical
`(int,int)` fixations, and `Q` is the reusable session payload. At cycle
`c`, old-parent depth is at most `c*q_max` and child depth at most
`(c+1)*q_max`. A conservative state-machine bound is

```
B_keep * P(c*q_max)
+ B_keep * P((c+1)*q_max)
+ Q
+ one temporary 8N mean and 8D pattern
+ one-parent candidate-generator scratch and O(K*q_max) result metadata.
```

Only competitive children are snapshotted. If the retained set is full, its worst
snapshot is destroyed before the replacement snapshot is taken. Thus there are at
most `B_keep` old parents, `B_keep` full retained child snapshots and one reusable
session; never `B_keep*K` child snapshots. Candidate records for only one parent
are live, and memory has no `raw_candidate_count*E` or `raw_candidate_count*N`
term. Online insertion is exactly equivalent to sorting all post-BP children by
the normative total order.

For the largest checked-in BB72 d6/r6 model (`M=252`, `N=2232`, `E=7776`) with
the reference `W=8`, `B_keep=8`, `q_max=4`, `C_max=10`, the final-cycle core
vector bound is 5,218,344 bytes: eight depth-36 parents, eight depth-40 children,
the session, one temporary mean and one temporary depth-40 pattern. Including the
validation ABI's inline `ParentState`, `Session` and temporary vector objects gives
5,223,048 bytes. Shared graph/OSD storage, allocator bookkeeping and the separately
bounded candidate-generator scratch are additional.

The focused six-variable recursive fixture measured a 1,896-byte core vector bound,
never exceeded two parent or two retained-child snapshots, evaluated at most
`B_keep*K` children per cycle, and used 4,308 KiB process peak RSS under
`/usr/bin/time -v`. RSS includes executable, runtime, graph, OSD and test harness;
it is not a per-state measurement or performance claim.

## Verification and scope

`tests/native/test_lpm_dp_decoder.cpp` covers defaults/identity, root and zero-
syndrome success, one and multiple parents, both hard-fixed values, exact warm
start, structural contradiction, child convergence, original `H/s` validation,
online retention against a full-sort reference, parent-generation release,
multiple cycles, deterministic replay, bounded four-candidate generation,
exhaustion, empty survivor sets, one-time OSD and its flag, decoder reuse and
non-reentrancy. `test_lpm_dp.cpp` also compares explicit-history and exact averaged
parent views.

There are no algorithmic deviations from the main-body retention rule. The
numeric convention is the existing decimation session's running-sum order, which
the note explicitly permits implementations to fix with the algorithm version.
The appendix's debiased alternative is not implemented. OSD remains the explicitly
optional outer extension described by the note and is never called per child.
Stage 4 simulator integration is intentionally absent.
