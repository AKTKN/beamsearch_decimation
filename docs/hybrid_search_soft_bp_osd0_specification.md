# Bounded Correction Search with Stateful Soft-Guided Min-Sum BP and OSD-0

**Document ID:** HSBP-ALG-1.0  
**Date:** 2026-09-21  
**Status:** Proposed implementation contract; performance remains to be measured.  
**Companion documents:** `hybrid_benchmark_data_and_hypothesis_specification.md` and `codex_hybrid_decoder_migration_prompts.md`.

## 1. Purpose and scope

Implement a decoder that spends a bounded amount of work searching for a complete correction, uses a small number of search-derived soft hints to continue min-sum belief propagation, and invokes order-zero OSD if neither stage succeeds. Its intended benefit is a reduction in average CPU service time at an acceptable logical failure rate. Neither improvement is assumed.

The sequence is **search first**, then soft-guided BP, then another search slice and BP attempt, followed by OSD-0 when the prefix budget is exhausted. Search state and BP state have separate lifetimes and responsibilities. The search frontier persists across slices. The BP edge messages persist across BP attempts within one shot. Both are reset between shots.

This document fixes choices that would otherwise be underspecified: the search branching set, partial assignments, hint selection, finite LLR construction, exact warm-start transition, flooding schedule, goal-test timing, budget semantics, and the OSD-only entry point. These choices define a new experimental profile, `hybrid_search_soft_ms_osd0_v1`; they are design decisions, not claims that this exact hybrid has established performance in the literature.

The inspected application revision is [`AKTKN/beamsearch_decimation@a98279b5bca906a4c41c59f68c35b93d6996bbc2`](https://github.com/AKTKN/beamsearch_decimation/tree/a98279b5bca906a4c41c59f68c35b93d6996bbc2). Its historical `screened_reference` decoder remains reproducible. The present user request authorizes a new algorithm and supersedes old-algorithm restrictions in the repository's instructions for this new profile.

## 2. Detector-model problem

### 2.1 Inputs and conventions

Let

\[
H\in\mathbb F_2^{m\times n},\qquad
A\in\mathbb F_2^{k_Z\times n},\qquad
s\in\mathbb F_2^m.
\]

Here, a column is a retained **circuit detector-error-model mechanism**, not a data qubit. A row is a selected detector. `n` in these equations is the number of retained mechanisms; it must not be confused with the physical code length recorded in experiment metadata. An error hypothesis is \(e\in\mathbb F_2^n\), its predicted detector pattern is \(He\), and its predicted measured logical-observable flips are \(Ae\).

Use the existing canonical undecomposed DEM conversion, selected-detector ordering, observable mapping, and instruction-to-column mapping. Preserve a correlated DEM instruction as a single mechanism, including instructions with multiple separated target groups. Do not decompose it into independent graph edges. Do not merge equal detector columns: their observable columns or provenance can differ. Retain columns with empty selected-detector support, including those with nonzero observable support.

After the existing exact removal of zero-probability mechanisms, require

\[
0<p_i\leq\tfrac12,\qquad
w_i=\log(1-p_i)-\log p_i\geq0.
\]

Compute this stably in binary64, using `log1p(-p_i) - log(p_i)`. Nonfinite values and probabilities above one half remain unsupported in this profile. In particular, do not silently clip probabilities or introduce complemented-variable offsets. A probability of one half is valid and gives zero cost.

Define the immutable physical-model objective

\[
W(e)=\sum_i w_i e_i.
\]

It ranks individual error configurations under the retained independent-mechanism decoder model. It does not sum probabilities over a logical coset. Sampling must continue to use the physical circuit; any DEM extraction approximation remains explicit in the manifest.

### 2.2 Acceptance and logical evaluation

A correction is valid exactly when

\[
He=s.
\]

Validity is an algebraic property, not evidence that the logical prediction is correct. The decoder returns \(\hat\ell=Ae\). The evaluator, outside the timed decoder and with access to sampled truth \(\ell_{\mathrm{true}}\), determines whether \(\hat\ell\ne\ell_{\mathrm{true}}\).

The decoder must never receive sampled error locations, sampled observable truth, or baseline outcomes. Those are available only to the evaluator.

For \(s=0\), return \(e=0\) immediately with `exit_stage=search` and `exit_reason=zero_syndrome`. This can still be a logical failure. Count it separately from nonzero-syndrome search successes in analysis.

For an empty model, the same rule applies when the syndrome is zero; a nonzero syndrome without supporting columns is an explicit decoding failure. More generally, a zero-degree selected row with syndrome one returns `failed / inconsistent_syndrome` before search, BP, or OSD. This is an exact structural check and does not require per-shot Gaussian elimination. Redundant rows are allowed. Check returned corrections against the original selected \(H\), not merely a reduced working matrix.

## 3. Shallow search over partial assignments

### 3.1 Node state

A node is a pair of disjoint index sets

\[
v=(F_1,F_0),\qquad F_1\cap F_0=\varnothing.
\]

Its associated pattern is \((F,b_F)\), where \(F=F_1\cup F_0\), \(b_i=1\) for \(i\in F_1\), and \(b_i=0\) for \(i\in F_0\). These assignments constrain this search branch only. They will be finite hints, not structural constraints, when passed to BP.

Define

\[
J(v)=\{0,\ldots,n-1\}\setminus(F_1\cup F_0),
\quad r(v)=s\oplus H\mathbf1_{F_1},
\quad g(v)=\sum_{i\in F_1}w_i,
\quad d(v)=|F_1|.
\]

The root is \((\varnothing,\varnothing)\). The search depth counts selected mechanisms, not all assigned bits, detector count, or circuit rounds. The depth limit \(D\) is global for the shot; it is not reset between search slices.

Use the lexicographically ordered flattened sequence of sorted `(column_index, assigned_bit)` pairs as the canonical pattern key. A separately assigned monotone `node_id` is for storage and diagnostics. Heap ordering must not depend on addresses, hash-table iteration order, or allocation order.

### 3.2 The branching set U is completely specified

Write \(N(a)=\{i:H_{ai}=1\}\) and \(N(i)=\{a:H_{ai}=1\}\). For a nonterminal node, choose

\[
a(v)=\min\{a:r_a(v)=1\},
\qquad U(v)=N(a(v))\cap J(v).
\]

Order \(U(v)=(j_1,\ldots,j_t)\) lexicographically by \((w_i,i)\): increasing immutable physical cost, then canonical column index. This fixed order can be precomputed for each detector. It reduces arbitrary cost choices when returning a goal during child generation; it still does not guarantee a globally minimum-cost correction. There is no global low-LLR pool, top-M restriction, randomized detector order, or enumeration of all fixed-size decimation subsets in this profile.

For every \(k=1,\ldots,t\), generate the child

\[
F'_1=F_1\cup\{j_k\},\qquad
F'_0=F_0\cup\{j_1,\ldots,j_{k-1}\}.
\]

Thus child \(k\) says that \(j_k\) is the first selected free mechanism incident on the chosen active detector. Later elements of \(U\) remain free; do not force them to zero. In particular, this does not impose an at-most-one-error constraint on the detector.

Any completion of the parent's assignments must select an odd, hence nonzero, number of mechanisms in \(U\). Its first selected element assigns it to exactly one child. This establishes the branch partition. It does not assert that the bounded, first-valid decoder enumerates all corrections or all logical classes.

Search nodes with \(d=D\) can be used as BP hints but are not expanded. A goal found at depth \(D\) is accepted.

### 3.3 Residual cost bound

Let \(R(v)=\{a:r_a(v)=1\}\) and

\[
k_i(v)=|N(i)\cap R(v)|.
\]

For each active detector define

\[
c_a(v)=\min_{i\in N(a)\cap J(v)}\frac{w_i}{k_i(v)},
\qquad h(v)=\sum_{a\in R(v)}c_a(v),
\qquad f(v)=g(v)+h(v).
\]

The denominators in an active detector's candidate set are at least one. If an active detector has no free incident mechanism, its minimum is infinite and the node is locally inconsistent. Reject it before insertion into either heap. A zero residual has \(h=0\).

**Lower-bound argument.** A feasible completion \(x\), supported on \(J(v)\), must cover each active detector with at least one selected mechanism. Therefore

\[
c_a(v)\leq\sum_{i\in N(a)\cap J(v)}x_i\frac{w_i}{k_i(v)}.
\]

Summing over active detectors counts a selected mechanism with \(k_i>0\) exactly \(k_i\) times, yielding

\[
h(v)\leq\sum_{i\in J(v):k_i>0}w_i x_i
\leq\sum_{i\in J(v)}w_i x_i.
\]

This bound ignores some parity constraints and is not an estimate of logical-coset probability. It is not required to be consistent between parent and child. Local consistency does not prove that a completion exists. BP failure does not prove that a branch is impossible.

### 3.4 Ranking, goals, and persistent frontier

Use a min-heap ordered by

\[
\operatorname{rank}(v)=\bigl(f(v),\ |R(v)|,\ \operatorname{pattern\_key}(v)\bigr).
\]

Only locally consistent nonterminal nodes with \(d<D\) enter the expansion heap. Generated locally consistent nonroot nodes also enter the guidance pool, including nodes at depth \(D\) and nodes already expanded. Guidance eligibility is independent of expansion status.

The root is checked before any BP work. Children are processed in increasing \(k\). **Check a child's residual immediately after constructing the child and before heuristic evaluation or heap insertion. Return the first generated child with zero residual.** Its full correction is \(\mathbf1_{F'_1}\), with every other mechanism zero. This explicitly allows early exit in the middle of a parent's expansion.

This goal-on-generation rule is chosen to minimize prefix work. Even an admissible \(h\) does not make this rule minimum-cost decoding. A goal-on-pop or cost-certified policy would be a different profile. Do not silently replace the specified policy during optimization.

Between cycles, resume the existing expansion heap. Do not restart at the root. Do not mutate search weights, heuristic keys, residuals, or frontier membership using BP posteriors. In this first version, information flows from search into BP; BP success terminates decoding, but unsuccessful BP does not reweight the search.

The canonical branch construction avoids permutation duplicates. Residual equality alone is not sufficient for merging states: two nodes may have different forbidden sets and different possible completions. A diagnostic hash may index nodes, but a collision must be resolved with full state equality. No residual-only visited-set pruning is allowed.

### 3.5 Work and resource limits

Configuration resolves to a global depth limit \(D\), cycle count \(C\), and per-cycle expansion budgets \(B_1,\ldots,B_C\). An expansion is one pop of an expandable node followed by generation of its children. Count attempted children separately. A cycle normally ends after its \(B_c\)-th expansion finishes, or when the expansion heap becomes empty.

The total expanded-node count is at most \(\sum_c B_c\). A nonterminal expansion generates at most the degree of its selected detector. This is a work bound, not a claim of constant cost per node: state materialization and heuristic evaluation also cost time.

Define `max_generated_nodes` as a global cap on constructed nodes including the root. Check capacity before constructing the next child. Reaching this cap while further construction is required triggers immediate OSD fallback with `fallback_reason=node_cap`; do not continue by dropping selected heap elements. Already constructed valid children would have terminated earlier.

An optional prefix process-CPU budget is checked before each expansion, before each child, before a hint transition, and before each full BP iteration. If reached, transition to OSD with `fallback_reason=prefix_cpu_cap`. It is not a hard deadline for the whole decoder: one atomic operation can overrun it, and OSD itself is uncapped by this timer. Default this option to `null` for deterministic work-budget replay.

Use finite memory caps and checked allocation sizes. Allocation failures become explicit resource failures, not corrupted state. Do not introduce an arbitrary beam truncation under the name of a memory optimization.

## 4. Selecting and applying soft-decimation patterns

### 4.1 Pattern selection after a search slice

Let \(\mathcal G_c\) contain all generated, locally consistent, nonroot, nonterminal nodes whose patterns have not previously been used for a BP attempt. Select

\[
v_c=\arg\min_{v\in\mathcal G_c}\operatorname{rank}(v).
\]

Take **all** assignments in that node: \(F_c=F_1(v_c)\cup F_0(v_c)\), with the associated bits. Mark this exact pattern used when starting its BP attempt. Do not sample an independent pattern, reselect a previously used ancestor, run BP for every generated node, or run all K candidates as in the old decoder.

A node is never removed from the search frontier merely because its pattern was used for BP. Conversely, expansion does not remove it from guidance eligibility. Used flags and two separate heaps are a possible efficient implementation.

If the guidance pool is empty but expansion work remains and cycles remain, continue to the next search slice without BP. If both pools are exhausted, invoke OSD immediately. If the expansion heap is empty but unused hints remain, subsequent cycles may use one hint each without search work. Stop after at most \(C\) cycles.

This fixes the meaning of \(U\): it is the local branching set in Section 3.2, not an independently chosen decimation pool. The pattern is selected by the search rank, not by a second unimplemented scoring stage.

### 4.2 Finite hint strength

Retain the original channel LLR vector \(w\) immutably. Let \(\kappa>0\) be the configured `hint_margin_llr`. Define the effective channel field for the current pattern as

\[
\lambda_i^{(c)}=
\begin{cases}
(1-2b_i)(w_i+\kappa),&i\in F_c,\\
w_i,&i\notin F_c,
\end{cases}
\qquad
\eta_i^{(c)}=\lambda_i^{(c)}-w_i.
\]

The `margin` convention is deliberate: the hint is finite and points toward its assigned bit even when the physical channel strongly favors zero. A zero hint increases the channel field by \(\kappa\); a one hint changes it to \(-w_i-\kappa\). This is more precise than saying only “give a large LLR.” Strengths and clipping limits remain experimental parameters, not tuned recommendations.

One equivalent auxiliary distribution is

\[
\pi_c(e\mid s)\propto
\mathbf1\{He=s\}\exp\left[-W(e)
-\sum_{i\in F_c}\gamma_i\mathbf1\{e_i\ne b_i\}\right],
\qquad \gamma_i=\kappa+2b_iw_i>0.
\]

This describes finite mismatch penalties. The loopy min-sum iterates are not exact marginals of this distribution, and this auxiliary distribution is not a replacement for the physical likelihood used in reported correction costs.

Replace the entire previous hint vector at a cycle boundary. Do not accumulate \(\eta^{(1)}+\cdots+\eta^{(c)}\), retain constraints from an obsolete pattern, or convert a posterior LLR into a new channel prior. All original variables and checks remain in BP. A returned BP or OSD correction may disagree with any hint and is accepted if it satisfies the original syndrome.

## 5. Stateful parallel min-sum BP

### 5.1 Stored state

Use one immutable Tanner graph per prepared model and mutable arrays per decoder instance:

- \(q_{i\to a}\): variable-to-check messages;
- \(z_{a\to i}\): check-to-variable messages;
- \(L_i\): clipped posterior decision LLRs;
- \(S_i\): the unclipped accumulator \(\lambda_i+\sum_{a\in N(i)}z_{a\to i}\);
- current finite fields \(\lambda\), current syndrome, and iteration counters.

Preserving only \(L_i\) is insufficient: individual extrinsic messages cannot be reconstructed from a marginal. The implementation must retain the edge state. It may expose snapshot/restore for tests, but production must not serialize all messages through Python between cycles.

Define

\[
\operatorname{clip}(x)=\min(L_{\max},\max(-L_{\max},x)),
\quad 0<\alpha\leq1,
\quad \operatorname{sgn}_+(0)=+1.
\]

Use finite binary64 parameters, deterministic adjacency order, no `fast-math`, and no floating-point contraction that changes the reference arithmetic. The hard-decision convention is \(\hat e_i=\mathbf1\{L_i\leq0\}\), including the zero tie. Normalize signed zero consistently.

### 5.2 Shot reset and first attempt

At the beginning of each shot, logically reset all check messages to zero and clear all search and guidance state. Initialization may be deferred until the first BP attempt so that search successes avoid touching all BP buffers, provided epoch/reset logic guarantees no cross-shot reuse.

On the first attempt, apply the selected field vector and set

\[
z_{a\to i}=0,\quad S_i=\lambda_i,\quad
L_i=\operatorname{clip}(S_i),\quad
q_{i\to a}=\operatorname{clip}(\lambda_i).
\]

There is **no initial unbiased BP run** in this profile. A conventional unbiased BP+OSD-0 baseline is implemented and measured separately.

### 5.3 Warm transition between different hints

Retain every \(z_{a\to i}\) from the previous attempt. With the newly selected \(\lambda^{\mathrm{new}}\), recompute

\[
S_i^{\mathrm{new}}=\lambda_i^{\mathrm{new}}
+\sum_{a\in N(i)}z_{a\to i},
\]

\[
L_i^{\mathrm{new}}=\operatorname{clip}(S_i^{\mathrm{new}}),
\qquad
q_{i\to a}^{\mathrm{new}}
=\operatorname{clip}(S_i^{\mathrm{new}}-z_{a\to i}).
\]

This is a continuation of the iterative solver after changing finite external fields. Check messages retain old evidence and need subsequent iterations to adapt; there is no claim that this transition instantly produces the new fixed point.

Do not compute an extrinsic message by subtracting from clipped \(L_i\). Clipping destroys information needed by that subtraction. Recomputing only the changed variables is an allowed optimization if it reproduces this equation exactly.

After this transition, form the hard decision and check the full syndrome. A valid result is a `guided_bp` exit with zero completed iterations for that attempt. Otherwise perform the following full iterations.

### 5.4 One flooding iteration

For check degree at least two, compute every new check message from the previous variable-to-check array:

\[
z_{a\to i}^{\mathrm{new}}=
\operatorname{clip}\left[
\alpha(-1)^{s_a}
\left(\prod_{j\in N(a)\setminus\{i\}}
\operatorname{sgn}_+(q_{j\to a}^{\mathrm{old}})\right)
\min_{j\in N(a)\setminus\{i\}}|q_{j\to a}^{\mathrm{old}}|
\right].
\]

For a degree-one check, set \(z_{a\to i}^{\mathrm{new}}=(-1)^{s_a}L_{\max}\). A degree-zero row with syndrome one is inconsistent; a degree-zero row with syndrome zero has no messages.

Only after the entire check pass has completed, update all variables:

\[
S_i^{\mathrm{new}}=\lambda_i+\sum_{a\in N(i)}z_{a\to i}^{\mathrm{new}},
\]

\[
L_i^{\mathrm{new}}=\operatorname{clip}(S_i^{\mathrm{new}}),\qquad
q_{i\to a}^{\mathrm{new}}
=\operatorname{clip}(S_i^{\mathrm{new}}-z_{a\to i}^{\mathrm{new}}).
\]

Then form the hard decision and test \(H\hat e=s\). Stop immediately on validity. The reference has no damping, layered scheduling, serial row updates, adaptive scaling, or posterior averaging. Each would require a separately identified extension.

Use a two-minimum check kernel with correct handling of repeated minima, zero messages, and signs, so a full iteration costs \(O(\operatorname{nnz}(H)+n+m)\), including validity checking. A double buffer is a simple way to enforce flooding; an in-place implementation is acceptable only if it preserves the same dependency barrier.

### 5.5 Iteration budget and continuation

The resolved configuration contains per-cycle budgets \(T_1,\ldots,T_C\). A BP attempt uses at most \(T_c\) full iterations. If it fails, retain its messages for the next selected pattern; do not roll back to an earlier “best posterior.” BP failure only records nonconvergence. It does not delete the corresponding search branch.

For a cold-start ablation, reset messages before each hint while keeping every other policy unchanged. Give this ablation a distinct decoder identity. It is not the main profile.

## 6. OSD-CS with order zero

### 6.1 Required backend behavior

Use the existing pinned `ldpc` dependency, upstream commit `d3429964cd4ffe1abfc041c6ec8b8425cb174f40`, plus the repository's explicit, audited opt-in patch.

At that commit, [`OsdDecoder::decode`](https://github.com/quantumgizmos/ldpc/blob/d3429964cd4ffe1abfc041c6ec8b8425cb174f40/src_cpp/osd.hpp) takes the order-zero path when `osd_order == 0`: it orders columns using the supplied LLR vector and calls `fast_solve`. The order-zero case does not enumerate combination-sweep candidates. Configure `osd_method="OSD_CS"`, `osd_order=0`; record `effective_osd_order=0`.

The standard [`BpOsdDecoder.decode`](https://github.com/quantumgizmos/ldpc/blob/d3429964cd4ffe1abfc041c6ec8b8425cb174f40/src_python/ldpc/bposd_decoder/_bposd_decoder.pyx) starts a BP run before potentially calling OSD. It is therefore not the OSD-only fallback interface required here.

Add an opt-in native bridge that invokes the pinned `ldpc::osd::OsdDecoder::decode(s, L_for_osd)` directly. Keep graph and probability-vector lifetimes valid, prepare reusable objects once per worker model, and include per-shot ordering and elimination in the timed fallback. Do not silently perform a fresh BP run.

### 6.2 Input LLRs and exact ordering convention

If any BP attempt ran, pass the final stored clipped \(L\) from the most recent attempt. Retain the effect of its last soft field; do not automatically remove that field or run an extra “polishing” iteration. If no attempt ran, pass \(\operatorname{clip}(w)\). Store `osd_llr_source` accordingly.

The pinned [`soft_decision_col_sort`](https://github.com/quantumgizmos/ldpc/blob/d3429964cd4ffe1abfc041c6ec8b8425cb174f40/src_cpp/sort.hpp) sorts **signed supplied LLR values in ascending order**, not their absolute values. Its comparator does not explicitly break equal-value ties. The reference bridge preserves that upstream behavior. Do not substitute an absolute-reliability sort, perturb tied LLRs, or impose a new tie policy under the same identity. Record the upstream implementation, libc, compiler, and build identity; cross-platform tie-equivalence is not guaranteed. An explicit stable-tie variant can be a later separate profile.

Conceptually, the pinned [`fast_solve`](https://github.com/quantumgizmos/ldpc/blob/d3429964cd4ffe1abfc041c6ec8b8425cb174f40/src_cpp/gf2sparse_linalg.hpp) performs GF(2) elimination in the supplied column ordering and stops when the syndrome is in the span of selected pivots. Nonpivot bits are zero and pivot bits solve the syndrome. The pinned implementation, including row-pivot choices, is authoritative for exact behavior.

OSD operates on the original \(H,s\) with all columns available. It does not inherit hard restrictions from search. Validate its output against \(H\). Return `exit_stage=osd` if valid, otherwise `exit_stage=failed` with a precise failure reason. A valid OSD output can still be logically incorrect.

### 6.3 Baselines

The primary new baseline is the actual upstream BP-OSD adapter with parallel min-sum, its configured iteration budget, `OSD_CS`, and order zero. Its normal BP-before-OSD behavior remains unchanged. Label it explicitly, for example `bposd_ms30_cs0` when the budget is 30; resolve the full configuration into its identity.

Preserve the previous CS10 baseline and its exact label for historical comparison. Comparing only against CS0 does not establish that the new decoder has solved the previously observed gap to CS10. Preserve the published beam-search adapter and its pinned settings as another comparison.

The hybrid's fallback can differ in both runtime and logical outcome from standalone BP-OSD-0 because it receives different LLRs and performs no new BP run. The experiment specification accounts for this difference explicitly.

## 7. Complete state machine

```text
decode(s):
    begin service accounting; validate input and check zero-degree row consistency
    clear per-shot search state and logically reset the BP session
    if s is zero: accept zero correction as search / zero_syndrome
    create root and initialize expansion heap; initialize empty guidance pool

    for cycle c in 1..C:
        run up to B[c] expansions from the persistent heap
            process children in their specified order
            accept the first generated zero-residual child
            enforce global node and optional prefix-CPU caps
        if a hard prefix cap fired: break to OSD

        if guided_bp_enabled and there is an unused eligible pattern:
            select the minimum-ranked unused pattern and mark it used
            replace the soft fields
            initialize or warm-transition the BP message state
            accept if the transition's hard decision is valid
            run at most T[c] flooding min-sum iterations, accepting if valid
        if a hard prefix cap fired: break to OSD
        if no expansion work and no usable BP hints remain: break to OSD

    invoke OSD-CS(order=0) directly with final BP LLRs, or clipped channel LLRs
    validate correction; predict observables; return a terminal result
```

All acceptance paths use the same final result validation and observable mapping. No truth-based acceptance gate is permitted. The externally checked `syndrome_valid` is authoritative; an internal success flag without a valid correction is an implementation error.

`guided_bp_enabled=false` defines the search-plus-OSD ablation: execute the search slices with the same budgets, skip guidance, and use clipped physical channel LLRs at fallback. It must have a distinct identity. `C=0` means direct OSD-0, not the standalone BP-OSD baseline. Neither should be mislabeled.

## 8. Illustrative small example

Consider

\[
H=\begin{pmatrix}1&1&0\\0&1&1\end{pmatrix},
\quad s=(1,1)^T,\quad w=(2,3,2).
\]

At the root, the first active detector is row 0 and \(U=(0,1)\). Its two children, in order, are:

| Child | \(F_1\) | \(F_0\) | Residual |
|---|---|---|---|
| First | `{0}` | empty | `(0,1)` |
| Second | `{1}` | `{0}` | `(0,0)` |

The second child returns correction `(0,1,0)` immediately; no BP is run. This example also illustrates that zero assignments are created by canonical precedence, not by posterior ranking.

For a different syndrome or a larger model where no generated child is valid, the best eligible node becomes a hint. If that hint assigns column 1 to one and column 0 to zero with \(\kappa=8\), its effective fields are \((10,-11,2)\). Another hint replaces these fields at the next cycle while retaining BP check messages. These numbers illustrate the field convention only and are not benchmark tuning results.

## 9. C++ implementation and safe optimization

### 9.1 Module boundaries

Use C++17 throughout the search and hybrid control path. Keep Python for configuration, experiment orchestration, sampling integration, result conversion, and analysis. Suggested native components are `SearchSession`, `StatefulMinSumSession` in the opt-in `ldpc` fork, `Osd0Bridge`, `HybridDecoder`, and compact telemetry records. Names may follow existing project conventions, but responsibilities must remain separable and unit-testable.

The application should reuse the `ldpc` fork for BP kernels and OSD, with explicit APIs for resetting, replacing fields, continuing iterations, and retrieving final beliefs. Do not reimplement production BP in Python or hide a new production BP implementation in an unrelated application module. Keep the old `ldpc.reference_bp` API compatible.

Prepared graphs, sorted adjacency lists, canonical edge IDs, and static weights belong to a worker-owned model object. A mutable decoder session is not reentrant. Parallelism is across shots in separate worker processes; native threads default to one. Release the Python GIL for the complete native decode call. Reset all state between shots, including after exceptions and warmup shots.

### 9.2 Engineering ideas informed by Tesseract

[Tesseract](https://arxiv.org/abs/2503.10988) motivates residual-guided correction search. Its [optimization study](https://arxiv.org/abs/2602.02985) examines byte-addressable flags, colocating frequently accessed fields, early termination of cost scans, and efficient packed-syndrome hashing. These are engineering precedents; their reported speedups do not predict this hybrid's performance.

The following table specifies proposed adaptations for this implementation. It is not a transcription of the Tesseract algorithm.

| Area | Proposed implementation | Condition for equivalence |
|---|---|---|
| Graph | Immutable flat CSR/CSC adjacency and canonical edge IDs | Identical row/column mappings and iteration order |
| Working flags | Byte or integer arrays for hot random accesses; avoid `vector<bool>` proxy access | Exact same assignments and active counts |
| Residuals | Packed machine-word arrays for XOR/popcount, or byte working arrays if measured faster | Exact bits, zeroed padding, safe tail handling |
| Node storage | Reserved arena, parent index, compact assignment deltas; materialize into reusable buffers | Parent lifetime and reconstruction preserve full `(F1,F0)` |
| Hot metadata | Colocate free/blocked state, active-detector count, and static weight where accesses coincide | Layout changes do not change numerical policy |
| Queue | Binary heap of compact node IDs and cached exact ranking fields | The specified total order is preserved |
| Guidance | Second heap and used flags referencing the same immutable nodes | Eligibility independent of expansion status |
| Heuristic | Cache only values valid for the particular node; update affected contributions | All effects of changed residuals and forbidden columns included |
| BP | Two-minimum check updates, reusable buffers, sparse hint-field changes | Same flooding equations, ties, signs, clipping, and reduction order |
| Telemetry | Preallocated fixed-size records and integer counters | No Python callbacks or Parquet writes in the native loop |

Do not add a residual-only visited set merely to reuse efficient syndrome hashing. This search's branch state contains more information than a residual. The inspected [Tesseract source](https://github.com/quantumlib/tesseract-decoder/blob/e7c762eef24161e304ba6fccb856a05b41f88c39/src/tesseract.cc) is an engineering reference, not an additional runtime dependency requirement. Preserve attribution and license notices if source is reused.

### 9.3 Incremental heuristic correctness

Adding a selected column flips all of its incident residual bits. This changes \(k_i\) for **every column incident on any flipped detector**, and therefore can change contributions on other active detectors sharing those columns. Newly forbidden columns can change minima at any incident active detector. Updating only the chosen detector or the flipped detectors is insufficient.

Begin with a canonical full recomputation oracle. For an optimized implementation, compute an affected-detector closure including:

1. detectors whose residual bit changed;
2. all detectors incident on columns whose active-detector count changed;
3. all detectors incident on columns newly removed from the free set.

Recompute the relevant minima and update the reduction structure. Extra recomputation is safe. Missing a dependency is not.

For reproducible heap priorities, define `g` as a left-to-right sum over sorted \(F_1\). Define `h` by a fixed balanced binary summation tree over a length-\(m\) vector of detector contributions, with zero for inactive detectors and zero-padding to the next power of two. The full oracle and incremental version must use that same tree. This permits cached leaf updates without changing addition order. Empty sums are zero. Treat nonfinite computed priorities as explicit numerical failures; do not place NaNs into heaps.

Do not use epsilon-based heap comparators: approximate equality can violate strict weak ordering. Floating-point bounds guide this bounded heuristic decoder; they are not used to claim a formal optimum certificate. SIMD may accelerate integer bit operations, but reordered floating-point reductions define a different numerical policy and require explicit identification.

For optional early termination of a per-detector minimum scan, a valid static lower bound for a candidate is \(w_i/|N(i)|\), since \(k_i\leq|N(i)|\). A preordered scan may stop only when a conservative bound for every remaining eligible candidate cannot improve the current minimum. Validate the floating-point bound and disabled-column handling against a complete scan. This optimization affects only heuristic evaluation order; the branching order remains \((w_i,i)\), which is generally a different ordering.

### 9.4 Excluded semantic changes

Do not silently import detector penalties, at-most-two-errors-per-detector restrictions, syndrome-only pruning, beam clipping, error sparsification, graphlike decomposition, posterior-dependent physical costs, or multi-component prior reweighting. Each can alter which correction is returned and requires an explicitly named separate experiment. Prefer measured optimizations that preserve the finite-budget reference decisions.

## 10. Configuration contract

The following is a **decoder fragment**, not a complete runnable experiment. Values are bounded smoke-test starting points, not evidence-based optimal settings. Resolve scalar-or-list budget syntax into explicit lists in the manifest.

```yaml
kind: hybrid_search_soft_bp_osd0
profile: hybrid_search_soft_ms_osd0_v1
algorithm_version: HSBP-ALG-1.0
search:
  max_depth: 2
  max_cycles: 3
  expansions_per_cycle: [8, 8, 8]
  max_generated_nodes: 4096
  detector_order: canonical_index
  branch_order: physical_weight_then_index
  heuristic: residual_fractional_cover
  goal_test: on_generation
  guidance_selection: best_unused_generated_pattern
  prefix_cpu_budget_ns: null
bp:
  enabled: true
  method: minimum_sum
  schedule: parallel
  iterations_per_cycle: [6, 6, 6]
  scaling_factor: 1.0
  llr_clip: 25.0
  hard_decision_zero: one
  warm_start: true
  hint_policy: signed_channel_magnitude_plus_margin
  hint_margin_llr: 8.0
  replace_previous_hint: true
fallback:
  backend: ldpc_osd_only
  osd_method: OSD_CS
  osd_order: 0
  llr_source: last_bp_else_clipped_channel
  ordering: pinned_ldpc_signed_llr
numerics:
  dtype: float64
  heuristic_reduction: fixed_binary_tree
  fast_math: false
native_threads: 1
```

Reject unknown keys, negative counts, mismatched budget-list lengths, invalid finite parameters, unsupported schedule/method combinations, and a nonzero OSD order for this kind. Require `max_generated_nodes >= 1`; expansion budgets may be zero. Positive-cycle BP attempts require positive iteration budgets; `C=0` resolves to empty lists. `D=0` is permitted and means no nonroot search nodes or guidance patterns: do not enqueue the root for expansion in that case. Experimental ablations must be explicitly identified by their resolved configuration and profile; do not silently coerce them into the main profile's literals.

## 11. Required correctness tests

1. **Search mathematics:** enumerate small binary models and partial assignments; verify residuals, child partition, local rejection, and \(h\)'s lower-bound property against exhaustive feasible completions. Include zero weights, duplicated detector columns with different observables, disconnected components, and depth-boundary goals. Do not incorrectly assert that first-generated goals are globally minimum cost.
2. **Search control:** finite budgets, persistent frontier, empty pools, unique hint use, guidance eligibility after expansion, goal timing, node-cap behavior, and no state leakage between shots. Optimized and full-oracle search must have identical decisions and deterministic counters under deterministic budgets.
3. **BP equations:** a small independent Python oracle for flooding min-sum, degree-zero/one cases, repeated minima, zero signs, clipping, and the hard-decision tie. Test a warm transition with changed and removed hints, including a case where subtracting from clipped posterior would be wrong.
4. **BP continuation:** two consecutive iteration calls with unchanged fields equal one concatenated call when no earlier valid exit intervenes. A different shot always starts cold. A finite hint can be violated by a valid correction. No extra unbiased BP pass is hidden in the hybrid.
5. **OSD bridge:** compare direct results against the pinned native OSD kernel for the same syndrome and supplied LLRs; cover signed ordering and equal-LLR ties on the pinned platform. Verify CS/order-zero and OSD-0 equivalence at the same input, no candidate enumeration, and no additional BP call. Handle rank deficiency and inconsistent inputs safely; always validate output.
6. **Integration:** every exit stage, repeated decoder reuse, exception cleanup, worker spawning, concurrent instances, selected-sector mapping, all BB observables, telemetry sums, and full physical-cost calculation using unchanged \(w\).
7. **Native safety and provenance:** Debug, release, AddressSanitizer/UndefinedBehaviorSanitizer where supported, clean dependency restoration from pins and patches, GIL release, source/build hash verification, and unchanged upstream baseline APIs.

These are implementation acceptance requirements. This document does not claim that the proposed implementation or its tests have already been executed.

## 12. What this design can and cannot establish

The design can avoid running BP and OSD on some shots and can limit the number of BP continuations on unresolved shots. It removes the old requirement to complete many hard-decimated BP branches. It remains an empirical question whether those savings exceed state construction, heuristic scoring, hint transitions, and fallback costs.

Early valid search results can select a worse logical class. Warm messages can preserve an unhelpful attractor. Strong finite fields can harm fallback ordering. OSD-0 gives an algebraic completion, not a likelihood or logical guarantee. These are measured failure modes, not reasons to declare the idea either successful or fundamentally unsound in advance.

Use the paired, stage-resolved experiment in the companion specification to test both runtime and accuracy. A lower OSD reach rate alone is insufficient evidence of an advantage.
