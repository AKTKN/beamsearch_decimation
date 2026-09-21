# Screening Decimation Patterns Before Parallel Belief Propagation
## A deterministic algorithm specification for quantum LDPC decoding

**Document version:** 1.0  
**Date:** 20 September 2026  
**Status:** Proposed method and implementation specification; no decoding-performance claim is established.

## Abstract

We specify a decoder that uses a preliminary belief-propagation (BP) run to identify a small set of candidate variables, searches over partial assignments to those variables using an inexpensive syndrome-based score, and reruns BP only for a selected list of assignments. A partial assignment consists of both a set of fixed variables and their assigned binary values. The proposed separation between candidate screening and BP completion is intended to reduce the number of BP executions relative to a search that invokes BP at every node. The reference implementation uses synchronous flooding sum-product BP, deterministic candidate selection from posterior-LLR histories, exhaustive enumeration at a prescribed decimation depth, a lower bound on completion cost for candidate ranking, and independent cold-start BP runs on exactly decimated graphs. We distinguish this fully specified reference algorithm from optional variants involving bounded best-first search, unit propagation, and alternative BP kernels. Algebraic consistency and the screening lower bound are established below; improvements in logical error rate or runtime remain empirical questions.

## 1. Scope and design objective

The proposed method addresses binary syndrome decoding on a sparse factor graph. It applies to one binary component of CSS decoding or to a binary detector-error model, provided that the adopted decoder model consists of independent binary error mechanisms.

The processing sequence is:

1. Run ordinary BP with a fixed iteration budget.
2. If BP does not return a syndrome-consistent estimate, construct a candidate variable pool from its recorded beliefs.
3. Enumerate and score partial assignments without executing BP for those assignments.
4. Select a prescribed number of partial assignments.
5. Run decimated BP independently for each selected assignment.
6. Return the lowest-cost syndrome-consistent estimate found.

The search allocates a limited BP-completion budget. It is not assumed to identify the globally optimal partial assignment, to maximize the probability of BP convergence, or to implement maximum-likelihood logical-class decoding.

The name **screened-decimation BP** is used descriptively in this document. It is not a claim that the general combination of search, conditioning, and BP is new. Related mechanisms and the narrower proposed distinction are discussed in Section 13.

### 1.1 Reference profile versus extensions

The normative reference profile in Sections 2–10 has the following choices:

- binary variables and independent Bernoulli priors;
- flooding sum-product BP;
- no damping, memory term, or asynchronous update;
- posterior histories from the initial BP run only;
- a static candidate pool during screening;
- a fixed number of explicitly decimated variables;
- exact enumeration of the prescribed finite candidate space;
- a zero-degree parity-consistency check before scoring;
- no degree-one propagation during screening;
- exact graph decimation, not a finite-LLR approximation to fixation;
- cold-start BP for every selected pattern;
- evaluation of all selected patterns before final selection;
- no automatically invoked OSD, LSD, or search-decoder fallback.

These choices resolve implementation decisions that were previously left open. Degree-one propagation and bounded search are specified separately as extensions, rather than being silently included in the reference profile.

## 2. Decoding model and notation

All vectors are column vectors. All parity equations and matrix products involving binary variables are over \(\mathbb F_2\). Costs and log-likelihood ratios are real-valued.

Let

\[
H\in\mathbb F_2^{m\times n},\qquad
s\in\mathbb F_2^m,\qquad
e\in\mathbb F_2^n,
\]

where \(H\) is the parity-check or detector matrix, \(s\) is the observed syndrome, and \(e\) is an error-mechanism vector. A syndrome-consistent estimate satisfies

\[
H\hat e=s. \tag{1}
\]

Use zero-based variable indices \(V=\{0,\ldots,n-1\}\) and check indices \(C=\{0,\ldots,m-1\}\) throughout the implementation and the pseudocode.

Define the neighborhoods

\[
\mathcal N(a)=\{i:H_{ai}=1\},\qquad
\mathcal N(i)=\{a:H_{ai}=1\}.
\]

The number of Tanner-graph edges is \(E=\operatorname{nnz}(H)\).

### 2.1 Priors and physical cost

The core algorithm accepts

\[
0<p_i\le \frac12,\qquad
P(e)=\prod_{i=0}^{n-1}p_i^{e_i}(1-p_i)^{1-e_i}.
\]

Define the physical log-likelihood weight

\[
w_i=\log\frac{1-p_i}{p_i}\ge0,\qquad
W(e)=\sum_i w_i e_i. \tag{2}
\]

Because

\[
-\log P(e)=-\sum_i\log(1-p_i)+W(e),
\]

minimizing \(W(e)\) is equivalent to selecting a most-likely individual error under this independent-error model. Use natural logarithms.

Physical weights \(w_i\) are never replaced by posterior LLRs and are never clipped for candidate scoring or final solution selection. The BP kernel uses a clipped copy, defined in Section 3.

The independent-error model must be stated when constructing \(H\) and \(p\). Mutually exclusive Pauli events or correlated circuit faults are not automatically represented exactly by independent Bernoulli variables. This document does not prescribe how such correlations should be approximated.

### 2.2 Logical correctness

If an observable matrix

\[
A\in\mathbb F_2^{k_{\mathrm{obs}}\times n}
\]

is supplied, a returned estimate succeeds on a simulated physical error \(e_{\mathrm{true}}\) when

\[
H\hat e=s,\qquad
A(\hat e\oplus e_{\mathrm{true}})=0. \tag{3}
\]

The true error is used only for evaluation. Neither \(e_{\mathrm{true}}\) nor the unknown true observable outcome is used to construct the candidate pool, rank patterns, or choose the output.

For CSS code-capacity decoding, the analogous condition is that the residual error lies in the relevant stabilizer subgroup. Syndrome consistency alone is not sufficient for quantum decoding success.

### 2.3 Candidate pool, fixation, and budgets

| Symbol | Meaning |
|---|---|
| \(T_0\) | Maximum number of flooding iterations in the initial BP run |
| \(T_{\mathrm{post}}\) | Maximum flooding iterations in each candidate-completion run |
| \(W_{\mathrm{hist}}\) | Requested length of the initial posterior-history window |
| \(M\) | Maximum number of variables in the candidate pool |
| \(U\subseteq V\) | Candidate pool; membership does not itself fix a variable |
| \(q\) | Number of explicitly fixed variables in one pattern |
| \(F\subseteq U\) | Fixed-variable set for one pattern, with \(|F|=q\) |
| \(b_F\) | Binary values assigned to variables in \(F\) |
| \(D=(F,b_F)\) | A decimation pattern |
| \(K\) | Maximum number of selected patterns passed to BP |
| \(L_{\max}\) | Magnitude limit for BP messages and stored posterior LLRs |

For a pattern \(D\), variables in \(U\setminus F\) and in \(V\setminus U\) remain free. In particular, a small \(U\) does not restrict the final error support to \(U\).

## 3. Synchronous flooding BP

This section defines the BP algorithm itself. The initial run and all candidate-completion runs use exactly the same kernel and numerical conventions, with different graphs and syndromes.

Consider a generic BP problem

\[
Bx=\sigma
\]

on a set of free variables \(J\subseteq V\), retaining their original variable identifiers. Initially \(B=H\), \(J=V\), and \(\sigma=s\). After decimation, \(B=H_{\bar F}\), \(J=\bar F\), and \(\sigma=s_D\).

Let

\[
\operatorname{clip}_L(z)=\max(-L_{\max},\min(L_{\max},z)),
\qquad
\lambda_i=\operatorname{clip}_L(w_i). \tag{4}
\]

Messages use the log ratio for value zero versus value one:

- \(v_{i\to a}^{(t)}\): variable-to-check message;
- \(c_{a\to i}^{(t)}\): check-to-variable message;
- \(L_i^{(t)}\): stored posterior LLR.

### 3.1 Initialization and the iteration-zero check

Every BP run starts from

\[
v_{i\to a}^{(0)}=\lambda_i,\qquad
c_{a\to i}^{(0)}=0,\qquad
L_i^{(0)}=\lambda_i. \tag{5}
\]

The hard-decision rule is

\[
\hat x_i^{(t)}=
\begin{cases}
1,&L_i^{(t)}<0,\\
0,&L_i^{(t)}\ge0.
\end{cases} \tag{6}
\]

Thus an exactly zero LLR produces value zero. This rule also applies to history-based sign-change counts.

Before the first message-passing iteration, evaluate \(B\hat x^{(0)}=\sigma\). If it holds, return immediately with iteration count zero. The reference decoder therefore returns the all-zero estimate immediately for a zero syndrome under the allowed nonnegative priors.

Iteration-zero beliefs are not included in the history statistics used to form \(U\).

### 3.2 Check-to-variable half-step

At flooding iteration \(t\ge1\), every check-to-variable message is computed using only the previous variable-to-check buffer:

\[
c_{a\to i}^{(t)}
=
\operatorname{clip}_L
\left[
2\,\operatorname{atanh}
\left(
(-1)^{\sigma_a}
\prod_{j\in\mathcal N_B(a)\setminus\{i\}}
\tanh\frac{v_{j\to a}^{(t-1)}}2
\right)
\right]. \tag{7}
\]

The syndrome sign \((-1)^{\sigma_a}\) is required. It enforces even parity for \(\sigma_a=0\) and odd parity for \(\sigma_a=1\).

For numerical evaluation in the reference implementation:

1. Use binary64 floating point.
2. Compute the product in ascending original variable-index order.
3. For a check of degree at least two, clamp the signed product to
   \[
   [-z_{\max},z_{\max}],\qquad
   z_{\max}=\tanh(L_{\max}/2),
   \]
   before evaluating \(\operatorname{atanh}\).
4. Clip the resulting message once more using Equation (4).
5. For a check with exactly one free neighbor, set its message directly to
   \[
   c_{a\to i}^{(t)}=(-1)^{\sigma_a}L_{\max}.
   \]
6. Handle checks of degree zero before message passing: syndrome zero imposes no restriction; syndrome one is a contradiction.

The reference profile restricts \(0<L_{\max}\le30\), ensuring that \(z_{\max}<1\) in binary64 under ordinary implementations. Reject invalid numerical values rather than propagating NaNs.

A zero input message in a product gives a zero outgoing message unless it is the excluded input. Implementations using product shortcuts must handle zero factors explicitly; division by a zero factor is invalid.

### 3.3 Variable half-step

After all new check messages have been computed, calculate

\[
\widetilde L_i^{(t)}
=
\lambda_i+
\sum_{a\in\mathcal N_B(i)}c_{a\to i}^{(t)},
\qquad
L_i^{(t)}=\operatorname{clip}_L(\widetilde L_i^{(t)}). \tag{8}
\]

The new outgoing messages are

\[
v_{i\to a}^{(t)}
=
\operatorname{clip}_L
\left[
\lambda_i+
\sum_{a'\in\mathcal N_B(i)\setminus\{a\}}
c_{a'\to i}^{(t)}
\right]. \tag{9}
\]

Compute the exclusion sum before clipping. In particular,

\[
v_{i\to a}^{(t)}
\ne
\operatorname{clip}_L\bigl(L_i^{(t)}-c_{a\to i}^{(t)}\bigr)
\]

in general, because \(L_i^{(t)}\) has already been clipped. An optimized implementation may use the unclipped total \(\widetilde L_i^{(t)}\) before subtraction.

Sum check messages in ascending check-index order in the deterministic reference implementation.

### 3.4 Parallel-update semantics

A complete flooding iteration has two synchronization barriers:

1. All check messages for iteration \(t\) use \(v^{(t-1)}\).
2. All posterior and outgoing variable messages use the completed \(c^{(t)}\) buffer.

No check may consume a variable message from iteration \(t\) while other checks are still using iteration \(t-1\). A sequential software loop is acceptable if it preserves these buffers and dependencies; an in-place layered update is not the same algorithm.

Candidate-level parallelism is separate: different selected patterns can also be decoded concurrently, but they never exchange messages or beliefs.

### 3.5 Stopping and recorded history

After completing the variable half-step:

1. Form \(\hat x^{(t)}\) using Equation (6).
2. Record the posterior vector \(L^{(t)}\) if history is requested.
3. Test the exact binary equality \(B\hat x^{(t)}=\sigma\).
4. Return the first syndrome-consistent hard decision, or continue until the iteration cap.

“Converged” in this document means syndrome-consistent within the iteration budget. Message stabilization is neither required nor used as the stopping condition.

If no estimate satisfies the syndrome by the iteration cap, return a non-convergence status together with the last beliefs and the requested history. Do not present the last hard decision as a valid correction.

An isolated free variable has no messages and retains \(L_i^{(t)}=\lambda_i\).

### 3.6 Why hard decimation is structural

Selected variables are removed from the BP graph and their contributions are moved into the syndrome. They are not implemented merely by assigning a large finite prior LLR. Finite clipping affects free-variable inference, but cannot unfix a structurally removed variable.

## 4. Deterministic construction of the candidate pool

Construct \(U\) only if the initial BP run fails after \(T_0\) iterations. Its available history therefore contains \(T_0\) completed posterior vectors.

Set

\[
W_{\mathrm{eff}}=\min(W_{\mathrm{hist}},T_0),
\qquad
t_{\mathrm{first}}=T_0-W_{\mathrm{eff}}+1.
\]

For every original variable \(i\), calculate

\[
\bar L_i=
\frac{1}{W_{\mathrm{eff}}}
\sum_{t=t_{\mathrm{first}}}^{T_0}L_i^{(t)},
\qquad
r_i=|\bar L_i|, \tag{10}
\]

and

\[
o_i=
\sum_{t=t_{\mathrm{first}}+1}^{T_0}
\mathbf1\!\left[
\mathbf1[L_i^{(t)}<0]\ne
\mathbf1[L_i^{(t-1)}<0]
\right]. \tag{11}
\]

If \(W_{\mathrm{eff}}=1\), the empty sum in Equation (11) is zero.

Order all variables by the lexicographic key

\[
\kappa_i=(r_i,-o_i,i), \tag{12}
\]

in ascending order. Define

\[
M_{\mathrm{eff}}=\min(M,n),\qquad
U=\{\text{first }M_{\mathrm{eff}}\text{ variables in this ordering}\}. \tag{13}
\]

This definition is complete:

- smaller absolute mean LLR is preferred;
- for exactly equal \(r_i\), more sign changes are preferred;
- any remaining tie is resolved by original variable index;
- no randomness is used;
- no degree threshold or unsatisfied-check-neighborhood restriction is applied;
- \(U\), \(r_i\), and \(o_i\) remain unchanged during screening.

The absolute value is taken after summing LLRs. It is not the average absolute LLR. Consequently, a symmetric sequence such as \(+5,-5,+5,-5\) has \(r_i=0\), while its average absolute magnitude is five.

This metric detects cancellation in the history, not every possible form of oscillation. The use of a terminal history window and the tie-break in Equation (12) are proposed design choices. They have not been established as superior to oscillation-count or final-LLR selection.

Only the last \(W_{\mathrm{eff}}\) posterior vectors need to be retained, requiring \(O(nW_{\mathrm{eff}})\) storage in a direct implementation.

## 5. The decimation-pattern space

Choose an integer \(q\) satisfying

\[
1\le q\le M_{\mathrm{eff}}.
\]

The reference search space is

\[
\mathcal D_q(U)=
\left\{
(F,b_F):
F\subseteq U,\ |F|=q,\ b_F\in\{0,1\}^{q}
\right\}. \tag{14}
\]

Its size is

\[
N_{\mathrm{pat}}=\binom{M_{\mathrm{eff}}}{q}2^q. \tag{15}
\]

The search includes both fixation locations and fixation values. Taking \(F\) to be a predetermined set would be a restricted variant and must not be reported as the full search in Equation (14).

### 5.1 Canonical representation

Represent \(F\) as a strictly increasing tuple of original variable indices,

\[
F=(i_1,\ldots,i_q),\qquad i_1<\cdots<i_q,
\]

and associate \(b_F=(b_1,\ldots,b_q)\) in that same order. A pattern identifier is the flattened tuple

\[
\operatorname{id}(D)=(i_1,b_1,\ldots,i_q,b_q).
\]

Enumerate the \(q\)-subsets of the numerically sorted set \(U\), and for each subset enumerate binary tuples in lexicographic order, with zero preceding one. This generates each pattern exactly once.

The selection ordering of \(U\) in Equation (12) is retained for diagnostics; numerical index order is used only for canonical pattern representation.

### 5.2 Fixed depth

All candidates in one reference decoding attempt have the same explicit fixation count \(q\). This prevents the definition of “best pattern” from mixing different amounts of conditioning without a stated policy.

Separate experiments with \(q=1,2,3,\ldots\) constitute separate configurations. Automatically escalating \(q\) after failure is not part of the reference algorithm.

## 6. Screening and ranking without BP

For a pattern \(D=(F,b_F)\), write \(\bar F=V\setminus F\). Define

\[
s_D=s\oplus H_Fb_F,\qquad
B_D=H_{\bar F},\qquad
g(D)=\sum_{i\in F}w_i b_i. \tag{16}
\]

Computing the residual syndrome is an XOR of the columns corresponding to fixed ones. Fixing a variable to zero does not change the syndrome, but still removes its column from the completion problem.

### 6.1 Exact local contradiction check

For every check \(a\), compute its remaining neighborhood

\[
\mathcal N_D(a)=\mathcal N(a)\setminus F.
\]

If \(\mathcal N_D(a)=\varnothing\) and \((s_D)_a=1\), reject the pattern as infeasible.

A zero-degree check with syndrome zero is satisfied and can be ignored. The reference profile does not run Gaussian elimination or degree-one propagation during screening. Passing this local check does not establish that the entire residual linear system is consistent.

### 6.2 A completion-cost lower bound

Let

\[
R_D=\{a:(s_D)_a=1\},
\qquad
k_j(D)=|\mathcal N(j)\cap R_D|,
\quad j\in\bar F.
\]

For each \(a\in R_D\), define

\[
\eta_a(D)=
\min_{j\in\mathcal N_D(a)}
\frac{w_j}{k_j(D)}.
\]

For every variable considered in this minimum, \(k_j(D)\ge1\). Set

\[
h(D)=\sum_{a\in R_D}\eta_a(D),
\qquad
f(D)=g(D)+h(D). \tag{17}
\]

If \(R_D=\varnothing\), use \(h(D)=0\). A minimum over an empty neighborhood is \(+\infty\), which is already covered by the contradiction check.

The completion bound ranges over all free variables \(\bar F\), not only \(U\setminus F\). Restricting completion variables to the candidate pool changes the problem and can invalidate the intended bound.

Equation (17) adapts the detector-cost construction used by Tesseract [4] to a partial assignment containing both fixed zeros and fixed ones.

**Proposition 1.** Every syndrome-consistent completion of \(D\) has cost at least \(f(D)\).

This statement concerns exact real arithmetic. The reference implementation uses binary64 scores for ranking, not as a numerically certified optimality or pruning certificate.

**Proof.** Let \(x\) satisfy \(B_Dx=s_D\). For each \(a\in R_D\), at least one selected free variable touches \(a\). Since \(\eta_a(D)\le w_j/k_j(D)\) for every free neighbor \(j\),

\[
\eta_a(D)
\le
\sum_{j\in\mathcal N_D(a)}
\frac{w_j}{k_j(D)}x_j.
\]

Summing over residual checks counts the contribution of each \(j\) with \(k_j(D)>0\) exactly \(k_j(D)\) times. Thus

\[
h(D)\le
\sum_{j:k_j(D)>0}w_jx_j
\le
\sum_{j\in\bar F}w_jx_j.
\]

Adding the fixed cost \(g(D)\) proves the claim. \(\square\)

The bound may be loose. It does not establish existence of a completion, its logical class, or the likelihood that finite-iteration BP will find it.

### 6.3 The complete pattern-ranking key

Define

\[
\rho(D)=\sum_{i\in F}r_i,
\qquad
\operatorname{key}(D)=
\bigl(f(D),\,\rho(D),\,\operatorname{id}(D)\bigr), \tag{18}
\]

ordered lexicographically in ascending order.

The primary score is the completion-cost lower bound. If the primary scores are exactly equal, prefer fixing variables with smaller aggregate history reliability. Resolve any remaining tie by the canonical pattern identifier.

Let \(\mathcal D_{\mathrm{valid}}\) be the patterns that survive the local contradiction check. Select

\[
K_{\mathrm{eff}}=\min(K,|\mathcal D_{\mathrm{valid}}|),
\]

\[
\mathcal C=
\operatorname{First}_{K_{\mathrm{eff}}}
\left(
\operatorname{sort}_{\operatorname{key}}\mathcal D_{\mathrm{valid}}
\right). \tag{19}
\]

The reference algorithm evaluates all patterns in Equation (14), so Equation (19) is exact within that finite space and the specified numerical ordering. “Top \(K\)” refers to this score, not to actual BP success probability or final error cost.

Use raw binary64 comparisons without an approximate-equality tolerance. An epsilon comparator can violate transitivity in sorting. Fix summation order: ascending check index for \(h\), and ascending variable index for \(g\) and \(\rho\). Cross-platform roundoff can still change nearly tied rankings; retain selected pattern identifiers in benchmark records.

If \(s_D=0\), the all-zero free completion is valid. The reference implementation still applies Equation (19); a selected such pattern will terminate at BP iteration zero. Automatically accepting an unselected complete pattern would define a different policy.

## 7. Decimation and BP completion

For each selected pattern \(D\in\mathcal C\):

1. Mask every variable in \(F\), including those fixed to zero.
2. Use residual syndrome \(s_D\).
3. Retain the original channel priors for every variable in \(\bar F\).
4. Initialize all BP messages from scratch using Equation (5).
5. Run flooding BP for at most \(T_{\mathrm{post}}\) iterations on \(B_D\).
6. If BP returns a consistent free estimate \(x\), reconstruct
   \[
   \hat e_i=
   \begin{cases}
   b_i,&i\in F,\\
   x_i,&i\in\bar F.
   \end{cases}
   \]
7. Verify the original equality \(H\hat e=s\).

The original matrix can remain immutable. A fixed-variable mask and reduced neighbor iteration implement the same mathematics; a physical copy of \(H_{\bar F}\) is unnecessary.

Cold starts are mandatory for the reference profile. Do not reuse failed-run messages, initial posterior beliefs as replacement priors, or messages from other candidates. Warm starts are a separate experimental factor.

**Proposition 2.** A residual estimate satisfying \(B_Dx=s_D\) reconstructs to an estimate satisfying the original syndrome.

**Proof.**

\[
H\hat e=H_Fb_F\oplus H_{\bar F}x
=H_Fb_F\oplus(s\oplus H_Fb_F)=s.
\]

\(\square\)

This statement concerns syndrome consistency only.

### 7.1 Final selection and failure

Execute all \(K_{\mathrm{eff}}\) selected completion runs, even if one returns early. Individual BP runs may stop at their own first consistent estimate, but the outer decoder waits for all selected candidates.

Let \(\mathcal S\) be the set of distinct returned full estimates satisfying \(H\hat e=s\). If \(\mathcal S\ne\varnothing\), return

\[
\hat e^\star=
\operatorname*{argmin}_{\hat e\in\mathcal S}
\bigl(W(\hat e),\,\operatorname{bits}(\hat e)\bigr), \tag{20}
\]

using ascending lexicographic bit order for exact cost ties. Physical cost is computed from unclipped weights in ascending variable-index order.

If \(\mathcal S=\varnothing\), return non-convergence. Do not relax the fixed variables, replenish the list from unselected candidates, increase the history window, enlarge \(U\), or increase \(q\) automatically.

If the initial BP run succeeds, return its estimate without invoking the screening stage. Therefore the reference profile is a non-convergence post-processor; it does not attempt to improve a syndrome-consistent but logically incorrect initial BP result.

## 8. Complete pseudocode

The pseudocode uses zero-based original variable identifiers and column-vector syndromes. “Parallel” below specifies data dependencies, not a requirement for a particular device.

### Algorithm 1: Flooding sum-product BP

~~~text
FLOODING_BP(B, sigma, physical_weights, T, Lmax, history_length):
    reject numerical or shape errors
    for each zero-degree check a:
        if sigma[a] == 1:
            return LOCAL_CONTRADICTION

    lambda[i] = clip(physical_weights[i], -Lmax, Lmax)
    c[a,i] = 0
    v_old[i,a] = lambda[i]
    L[i] = lambda[i]
    x[i] = 1 if L[i] < 0 else 0

    if B*x == sigma over GF(2):
        return CONVERGED(x, iterations=0)

    history = empty ring buffer of capacity history_length

    for t = 1, ..., T:
        # Phase 1: all reads come from v_old.
        parallel for every active edge (a,i):
            if degree_B(a) == 1:
                c_new[a,i] = (+Lmax if sigma[a] == 0 else -Lmax)
            else:
                z = (-1)^sigma[a]
                for j in sorted(N_B(a) excluding i):
                    z *= tanh(v_old[j,a] / 2)
                z = clip(z, -tanh(Lmax/2), +tanh(Lmax/2))
                c_new[a,i] = clip(2*atanh(z), -Lmax, Lmax)
        barrier

        # Phase 2: all reads come from the completed c_new.
        parallel for every free variable i:
            raw_L = lambda[i] + ordered_sum(c_new[a,i] for a in N_B(i))
            L[i] = clip(raw_L, -Lmax, Lmax)
            x[i] = 1 if L[i] < 0 else 0
            for a in N_B(i):
                raw_extrinsic = lambda[i] + ordered_sum(
                    c_new[a2,i] for a2 in N_B(i) excluding a
                )
                v_new[i,a] = clip(raw_extrinsic, -Lmax, Lmax)
        barrier

        append a copy of L to history if history_length > 0
        if B*x == sigma over GF(2):
            return CONVERGED(x, iterations=t, history=history)
        swap(v_old, v_new)

    return NONCONVERGENCE(last_x=x, last_L=L, history=history,
                          iterations=T)
~~~

### Algorithm 2: Candidate-pool construction

~~~text
SELECT_POOL(history, M):
    # Only called after the initial BP run has exhausted T0 iterations.
    W_eff = number of posterior vectors retained in history

    for i = 0, ..., n-1:
        mean_L[i] = ordered_sum(history[t][i] for t oldest to newest) / W_eff
        reliability[i] = abs(mean_L[i])
        flips[i] = number of consecutive hard-decision changes in history
                   using hard_decision(L) = 1 iff L < 0

    ranked_ids = sort all variable IDs by
                 (reliability[i], -flips[i], i)

    U = first min(M, n) IDs in ranked_ids
    return U, reliability, flips
~~~

### Algorithm 3: Exact finite-space screening

~~~text
SCREEN_PATTERNS(H, s, w, U, reliability, q, K):
    records = empty list

    for F in all q-subsets of numerically sorted U:
        for b in all binary q-tuples in lexicographic order:
            fixed = map the entries of F to the corresponding entries of b
            residual = copy(s)
            for i in F with fixed[i] == 1:
                residual ^= column(H, i)

            if any row a has no neighbor outside F and residual[a] == 1:
                continue

            R = indices a for which residual[a] == 1
            k[j] = number of checks in R adjacent to j, for j outside F

            h = 0
            for a in R in increasing order:
                eta = min(w[j] / k[j] for j in N(a) outside F)
                h += eta

            g = ordered_sum(w[i]*fixed[i] for i in F)
            rho = ordered_sum(reliability[i] for i in F)
            pattern_id = flattened tuple (i1,b1,...,iq,bq)
            key = (g+h, rho, pattern_id)

            append (key, F, b, residual) to records

    sort records by key
    return first min(K, len(records)) records
~~~

A bounded heap can replace the full records list without changing the selected set, provided the same key and exact enumeration are used.

### Algorithm 4: Full reference decoder

~~~text
SCREENED_DECIMATION_BP(H, s, p, config):
    validate inputs and config
    w[i] = log1p(-p[i]) - log(p[i])

    initial = FLOODING_BP(
        H, s, w, config.T0, config.Lmax, config.history_window
    )

    if initial.status == LOCAL_CONTRADICTION:
        return INPUT_INCONSISTENT
    if initial.status == CONVERGED:
        return INITIAL_CONVERGED(initial.x)

    U, reliability, flips = SELECT_POOL(initial.history, config.M)

    selected = SCREEN_PATTERNS(
        H, s, w, U, reliability, config.q, config.K
    )

    results = fixed-size array indexed by selected-pattern rank

    parallel for each selected record D at rank k:
        free_ids = all original variable IDs not in D.F
        reduced = H with columns in D.F masked out
        completion = FLOODING_BP(
            reduced, D.residual, w restricted to free_ids,
            config.Tpost, config.Lmax, history_length=0
        )

        if completion.status == CONVERGED:
            full = reconstruct completion with D.F fixed to D.b
            assert H*full == s over GF(2)
            results[k] = full
        else:
            results[k] = no solution

    solutions = distinct valid full estimates in results
    if solutions is empty:
        return NONCONVERGENCE

    best = minimum solutions by (physical_cost, lexicographic_bit_vector)
    return POST_CONVERGED(best)
~~~

A failed candidate is not reused to update \(U\) or to generate a new branch. Such feedback would require a separately defined adaptive algorithm.

## 9. Reference configuration and interface contract

The following parameters are proposed starting values, not values optimized by experiments.

| Parameter | Reference value | Interpretation |
|---|---:|---|
| BP kernel | sum-product | Equations (7)–(9) |
| Scheduling | flooding | Two synchronized half-steps |
| \(T_0\) | 30 | Initial BP iteration cap |
| \(T_{\mathrm{post}}\) | 30 | Per-pattern BP iteration cap |
| \(W_{\mathrm{hist}}\) | 8 | Terminal history window |
| \(M\) | 16 | Candidate-pool cap |
| \(q\) | 2 | Explicit fixed-variable count |
| \(K\) | 8 | BP-completion budget |
| \(L_{\max}\) | 25 | Message and posterior magnitude limit |
| Numeric type | binary64 | No quantized or reduced-precision messages |
| Screening | Equation (17) | Weighted residual-cost lower bound |
| Pattern generation | exhaustive | Equation (14) |
| Screening propagation | zero-degree checks only | No degree-one closure |
| Completion initialization | cold | Original channel priors |
| Outer stopping | all selected patterns | Then minimum physical cost |
| Randomness | none | Deterministic tie-breaks |

For \(n\ge16\), this profile scores 480 patterns and launches at most eight post-processing BP runs.

Require integer \(T_0,T_{\mathrm{post}},W_{\mathrm{hist}},M,q,K\ge1\), \(q\le\min(M,n)\), and \(0<L_{\max}\le30\). If \(W_{\mathrm{hist}}>T_0\), use \(W_{\mathrm{eff}}=T_0\). Do not silently reduce \(q\) when \(n\) or \(M\) is too small.

Validate that \(H\) is binary with canonical sparse entries, \(s\) is a binary vector of the proper length, and every \(p_i\) is finite and in \((0,1/2]\). Duplicate sparse entries must already have been combined over \(\mathbb F_2\), not by ordinary integer addition.

### 9.1 Return values

Return a structured object containing:

- status: INITIAL_CONVERGED, POST_CONVERGED, NONCONVERGENCE, or INPUT_INCONSISTENT;
- full error estimate, or no estimate on failure;
- predicted observables \(A\hat e\), if \(A\) is supplied and an estimate exists;
- iteration counts and selected-pattern metadata;
- optional diagnostics described in Section 12.

Invalid inputs or configurations produce an explicit validation error. INPUT_INCONSISTENT is used only for an established input contradiction, such as an all-zero row of \(H\) with syndrome one. The absence of a BP solution is reported as NONCONVERGENCE, not as a proof that \(He=s\) is unsatisfiable.

### 9.2 Unsupported priors and optional external preprocessing

The core rejects \(p_i=0\), \(p_i=1\), or \(p_i>1/2\). A wrapper may normalize a more general independent binary model as follows:

- For deterministic probabilities zero or one, substitute the corresponding known value, update the syndrome, and retain the reconstruction map.
- For \(1/2<p_i<1\), write \(e_i=1\oplus x_i\), use \(p_i'=1-p_i\), and update the syndrome by column \(H_i\).
- More generally, for a complement vector \(a\), use \(e=a\oplus x\), syndrome \(s'=s\oplus Ha\), and predicted observables \(Ae=Aa\oplus Ax\).

Such a wrapper must preserve original variable identifiers and the observable offset. If all variables are eliminated, it checks the remaining constant parity equations directly rather than calling BP. The wrapper is outside the reference profile and must be documented in a benchmark.

## 10. Worked example and implementation checks

Consider

\[
H=
\begin{pmatrix}
1&1&1&0&0\\
0&1&1&1&0\\
1&0&0&1&1
\end{pmatrix},
\qquad
s=
\begin{pmatrix}
1\\0\\0
\end{pmatrix}.
\]

Equivalently,

\[
e_0\oplus e_1\oplus e_2=1,\qquad
e_1\oplus e_2\oplus e_3=0,\qquad
e_0\oplus e_3\oplus e_4=0. \tag{21}
\]

Take equal physical weights \(w_i=1\), corresponding to \(p_i=1/(1+\exp(1))\).

### 10.1 A synthetic history for testing pool selection

The following trace is a synthetic input to the pool-selection routine. It is not claimed to have been produced by BP on Equation (21), and it is not evidence that the initial BP run fails on this example.

| Variable | Four stored posterior LLRs | \(r_i\) | \(o_i\) |
|---|---|---:|---:|
| 0 | \(2,2,2,2\) | 2 | 0 |
| 1 | \(1,-1,1,-1\) | 0 | 3 |
| 2 | \(3,3,3,3\) | 3 | 0 |
| 3 | \(-1,1,-1,1\) | 0 | 3 |
| 4 | \(4,4,4,4\) | 4 | 0 |

For \(M=2\), Equation (12) gives \(U=\{1,3\}\), with variable 1 preceding variable 3. Set \(q=2\), \(K=2\), and \(T_{\mathrm{post}}=30\) for this example.

### 10.2 Pattern scores

For \(F=(1,3)\), the residual problem is

\[
e_0\oplus e_2=1\oplus b_1,\qquad
e_2=b_1\oplus b_3,\qquad
e_0\oplus e_4=b_3.
\]

The weighted bound in Equation (17) yields:

| \((b_1,b_3)\) | \(s_D\) | \(g(D)\) | \(h(D)\) | \(f(D)\) |
|---|---|---:|---:|---:|
| \((0,0)\) | \((1,0,0)\) | 0 | 1 | 1 |
| \((0,1)\) | \((1,1,1)\) | 1 | \(3/2\) | \(5/2\) |
| \((1,0)\) | \((0,1,0)\) | 1 | 1 | 2 |
| \((1,1)\) | \((0,0,1)\) | 2 | 1 | 3 |

Thus the selected patterns are \((0,0)\) and \((1,0)\).

The earlier illustrative bound \(\lceil |s_D|/2\rceil\) is a different valid bound for this unit-weight example. It assigns score 3 rather than \(5/2\) to \((0,1)\), but selects the same two patterns. The normative specification uses Equation (17).

### 10.3 BP completion

For \((b_1,b_3)=(0,0)\),

\[
e_2=0,\quad e_0=1,\quad e_4=1,
\]

so the completed estimate is

\[
\hat e^{(0,0)}=(1,0,0,0,1)^T,\qquad W=2.
\]

For \((b_1,b_3)=(1,0)\),

\[
e_2=1,\quad e_0=1,\quad e_4=1,
\]

so

\[
\hat e^{(1,0)}=(1,1,1,0,1)^T,\qquad W=4.
\]

The remaining factor graph is a chain, and the needed information propagates from a degree-one check. These outputs also follow directly by solving the three residual equations. They are not a statistical decoder benchmark.

The algorithm selects the weight-two estimate. The unselected pattern \((0,1)\) has a completion of weight three, showing that the screening order need not equal the order of completed costs.

### 10.4 Required implementation checks

The following checks target distinct correctness risks:

1. **Syndrome sign:** with \(H=(1)\), \(s=1\), \(w_0=1\), and \(L_{\max}=25\), the first check message is negative and the BP estimate is one.
2. **Zero-LLR tie:** for \(L_i=0\), the hard decision is zero in both decoding and history analysis.
3. **Iteration-zero success:** a zero syndrome with the allowed nonnegative priors returns the all-zero estimate at iteration zero.
4. **Fixed zero versus fixed one:** both remove a column; only a fixed one flips the syndrome.
5. **Contradiction:** fixing the only neighbor of an odd check to zero rejects the pattern.
6. **Reconstruction:** every successful residual solution satisfies the original syndrome after restoring fixed entries.
7. **History selection:** the synthetic trace above produces exactly \(U=\{1,3\}\).
8. **Candidate ranking:** the worked example gives scores \(1,5/2,2,3\) in binary-tuple order.
9. **Lower-bound validity:** for small matrices, enumerate residual completions and verify \(f(D)\le\min W(e)\) for every feasible pattern.
10. **Flooding semantics:** compare a buffered scalar implementation with a parallel implementation; neither may consume same-iteration variable messages during the check phase.
11. **Cold-start isolation:** a candidate result cannot depend on the execution order of other candidates.
12. **Outer selection:** permuting candidate completion order does not change the final output.

Approximate numerical agreement is appropriate for BP-message comparisons across implementations; syndrome equality and hard-fixation invariants are exact binary tests.

## 11. Computational cost and limitations

With prefix/suffix products or equivalent linear-time check updates, one flooding iteration costs \(O(E+n+m)\). A literal implementation that recomputes the product separately for every outgoing edge can instead incur a sum of squared check degrees. This distinction matters when claiming complexity.

Let \(C_{\mathrm{BP}}(D)\) denote the actual cost of one completion, including its iteration count. The total work has the form

\[
C_{\mathrm{total}}
=
C_{\mathrm{initial}}
+
C_U
+
C_{\mathrm{screen}}
+
\sum_{D\in\mathcal C}C_{\mathrm{BP}}(D). \tag{22}
\]

Direct pool sorting costs \(O(n\log n)\). With \(N_{\mathrm{pat}}\) patterns and full graph scans per pattern, screening can cost

\[
O\!\left(N_{\mathrm{pat}}(E+m+n)\right),
\]

plus sorting or heap maintenance. This cost must not be omitted. Local updates, adjacency-based residual computations, and shared evaluation across related patterns may reduce it, but those optimizations require measurement.

The crude post-processing BP-work upper bound is

\[
O\!\left(KT_{\mathrm{post}}(E+n+m)\right).
\]

The number of candidate patterns is exponential in \(q\) and combinatorial in \(M\). If \(M,q,K,T_0,T_{\mathrm{post}}\) are fixed constants and graph degrees are bounded, the message-passing and direct-screening terms grow linearly with graph size, while full pool sorting adds \(O(n\log n)\). This fixed-parameter statement is not a guarantee of scalable performance when budgets must increase with code size.

Candidate-level parallel execution changes wall-clock latency, not total work. With enough workers, completion latency is approximately the slowest selected BP run plus scheduling and memory overhead. A comparison must report both resource use and elapsed time.

The method has four principal failure mechanisms:

- the selected pool misses useful variables;
- the chosen depth \(q\) does not provide a useful amount of conditioning;
- the inexpensive score ranks useful patterns below the selected list;
- BP fails, or returns a logically incorrect estimate, on the selected residual problems.

A low completion-cost bound is not a model of BP convergence. Reducing BP calls is useful only if the resulting loss in candidate quality is sufficiently small at the same total resource budget.

## 12. Evaluation protocol and diagnostic records

The first comparison should isolate the proposed screening stage. Hold the BP kernel, candidate-pool size, fixation depth, clipping, and completion budget fixed while comparing:

1. random selection of \(K\) patterns from the same candidate space;
2. history-based ordering without the syndrome lower bound;
3. Equation (18), the proposed screening key;
4. BP evaluation of every candidate in a sufficiently small candidate space.

For alternative pool constructions, compare final-LLR magnitude, sign-change count, absolute mean LLR, and signed mean LLR while keeping the subsequent pattern space and screening rule unchanged. These alternatives must be separate configurations; they are not automatic fallbacks.

For each shot, record at least:

- initial BP status and iterations;
- selected pool IDs and history statistics;
- total number of generated and locally rejected patterns;
- selected pattern IDs, fixed costs, lower bounds, and tie-break values;
- per-candidate BP iterations and success status;
- final estimate cost and output status;
- initial, pool-selection, screening, completion, and total runtimes;
- total active-edge message updates;
- maximum candidate concurrency and peak working memory.

In simulation, additionally record logical success using Equation (3). Report separately

\[
P_{\mathrm{nonconv}},
\qquad
P(\text{syndrome-consistent output and logical failure}),
\]

and their sum. Report unconditional decoder performance as well as post-processing success conditioned on initial BP failure.

Use common input shots for paired comparisons. Parameter tuning and final evaluation should use separate samples. Report uncertainty for logical error rates and tail-latency estimates. A failure-free finite sample does not establish zero logical error rate.

A useful diagnostic on small candidate spaces is the fraction of shots for which the selected list contains at least one logically successful BP completion, compared with evaluating the entire space. This tests screening quality directly. Ground-truth error-support overlap with \(U\) is insufficient by itself because a stabilizer-equivalent correction can have a different support.

## 13. Relation to previous work

The individual ingredients have substantial precedent. The table distinguishes published mechanisms from the particular composition specified here.

| Work | Relevant mechanism | Relationship to this specification |
|---|---|---|
| Yao et al., BPGD [1] | Repeated BP followed by fixing a currently most reliable variable | Our reference pool is selected once, and candidate screening does not rerun BP |
| Gong et al., GDG [2] | History-based selection favoring likely faults, with restricted alternative guesses | Motivates the importance of selection history and multiple partial assignments |
| Ye et al., beam search [3] | Branch on a low-reliability variable, rerun masked BP, and prune paths using BP results | We screen patterns before paying for their BP completion |
| Beni et al., Tesseract [4] | Search over error sets using residual-syndrome cost bounds | Supplies the detector-cost idea adapted in Equation (17); our search stops at partial fixation |
| Ott et al., BP-DTD [5] | Decimated BP guides exploration of a fault decision tree | A direct comparison for the cost of calling BP within search |
| Wang et al., BP-SF [6] | Oscillation-based candidate pools and multiple syndrome-modified BP attempts | A precedent for one initial analysis followed by independent BP attempts; syndrome flipping is not hard graph decimation |
| Bhatnagar et al., impulse decoding [7] | Independent BP attempts with selected variables fixed | A relevant single-variable baseline for testing whether joint-pattern screening adds value |

The proposed contribution to investigate is whether static candidate-pool construction and inexpensive joint-pattern screening can reduce the number of BP executions at a competitive logical error rate and total cost. This document establishes neither priority for that idea nor empirical superiority.

## 14. Explicitly separate extensions

### 14.1 Alternative normalized min-sum kernel

For an experiment using normalized min-sum, replace Equation (7), for checks of degree at least two, by

\[
c_{a\to i}^{(t)}
=
\operatorname{clip}_L
\left[
\alpha(-1)^{\sigma_a}
\left(
\prod_{j\in\mathcal N_B(a)\setminus\{i\}}
\operatorname{sgn}_+(v_{j\to a}^{(t-1)})
\right)
\min_{j\in\mathcal N_B(a)\setminus\{i\}}
|v_{j\to a}^{(t-1)}|
\right],
\]

where \(0<\alpha\le1\), and \(\operatorname{sgn}_+(0)=+1\). The zero magnitude makes any product-sign ambiguity irrelevant. Retain the exact degree-one convention, clipping, stopping rules, and flooding schedule from Section 3.

Report \(\alpha\) and use the same kernel in the initial and completion runs. Setting \(\alpha=1\) gives ordinary min-sum. The reference configuration remains sum-product.

### 14.2 Degree-one propagation during screening

An optional exact screening extension maintains a partial-assignment map initialized by \(D\), then repeatedly:

1. rejects a degree-zero odd residual check;
2. selects the smallest-index check with one free neighbor;
3. fixes that neighbor to the check's residual parity;
4. updates every adjacent check and repeats.

Assignments forced this way can lie outside \(U\). The original choice count \(q\) still counts only explicitly guessed variables. The score must then include all forced-one costs and must evaluate the bound on the graph after propagation.

If this extension is used, candidates can collapse to the same closure. Define a canonical closure map, deduplicate equal closures before selecting \(K\), and use the smallest original pattern key as the representative when all closure-based scores agree. Reuse the closure in the completion run.

This extension can solve the worked example entirely during screening. That is why it is excluded from the reference example intended to demonstrate BP completion.

### 14.3 Budget-limited best-first search

For larger \(M\) or \(q\), exhaustive enumeration can be replaced by a separately configured search:

- start from the empty assignment;
- append a new variable index larger than every index already in the pattern;
- branch on both values zero and one;
- retain only states that can still reach depth \(q\);
- reject established local contradictions;
- prioritize intermediate states using a stated key, such as the analogue of Equation (18);
- stop at a fixed expansion budget;
- choose the top \(K\) depth-\(q\) patterns actually generated and scored.

Every subset has a unique increasing-index path. A bounded implementation must define whether an expansion means popping a state or generating a child; the recommended convention is one popped, nonterminal state.

The resulting shortlist is not generally the global top \(K\) under Equation (18). Admissibility of a completion-cost bound alone does not establish top-\(K\) partial-pattern ranking or optimal BP-budget allocation.

BP failure is not an infeasibility certificate and cannot justify logically pruning all descendants. Also, two patterns with the same residual syndrome can have different free-variable masks; they must not be merged solely because their residual syndromes coincide.

## 15. Implementation deliverables

A subsequent software implementation should separate the following components:

1. sparse binary problem representation with stable variable and check IDs;
2. standalone flooding BP kernel;
3. initial-history recorder and deterministic pool selector;
4. canonical pattern enumerator;
5. decimation view and syndrome updater;
6. contradiction detector and lower-bound evaluator;
7. bounded top-\(K\) container with deterministic ordering;
8. independent BP-completion executor;
9. output reconstruction and physical-cost selection;
10. benchmark and diagnostic recorder.

This separation permits the effects of \(U\), pattern ranking, fixation depth, and BP dynamics to be varied independently. The reference implementation should reproduce the specified configuration and worked example before performance-oriented changes are introduced.

## References

[1] H. Yao, W. Abu Laban, C. Häger, A. Graell i Amat, and H. D. Pfister, “Belief Propagation Decoding of Quantum LDPC Codes with Guided Decimation,” 2023; revised 2024. [arXiv:2312.10950](https://arxiv.org/abs/2312.10950).

[2] A. Gong, S. Cammerer, and J. M. Renes, “Toward Low-latency Iterative Decoding of QLDPC Codes Under Circuit-Level Noise,” 2024. [arXiv:2403.18901](https://arxiv.org/abs/2403.18901).

[3] M. Ye, D. Wecker, and N. Delfosse, “Beam search decoder for quantum LDPC codes,” 2025. [arXiv:2512.07057](https://arxiv.org/abs/2512.07057).

[4] L. Aghababaie Beni, O. Higgott, and N. Shutty, “Tesseract: A Search-Based Decoder for Quantum Error Correction,” 2025. [arXiv:2503.10988](https://arxiv.org/abs/2503.10988).

[5] K. R. Ott, B. Hetényi, and M. E. Beverland, “Decision-tree decoders for general quantum LDPC codes,” 2025. [arXiv:2502.16408](https://arxiv.org/abs/2502.16408).

[6] M. Wang, A. Li, and F. Mueller, “Fully Parallelized BP Decoding for Quantum LDPC Codes Can Outperform BP-OSD,” 2025. [arXiv:2507.00254](https://arxiv.org/abs/2507.00254).

[7] S. Bhatnagar, M. Pacenti, N. Raveendran, D. Declercq, and B. Vasić, “Impulse Decoding of Quantum LDPC Codes: Equivalence of Degeneracy and Code-Shortening,” 2026. [arXiv:2606.18240](https://arxiv.org/abs/2606.18240).
