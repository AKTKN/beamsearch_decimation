# Opt-in ldpc reference flooding BP

The ordinary pinned ldpc kernel in src_cpp/bp.hpp was inspected before modification.
It uses different clipping, zero ties (<=0), degree-one and accumulation conventions.
Rather than modifying those defaults, this fork adds src_cpp/reference_bp.hpp in
namespace ldpc::reference, with bindings under src_python/ldpc/reference_bp/ and an
explicit setup_reference.py build. Ordinary setup.py, BP and BP-OSD sources remain
unchanged. The published beam source is not used by this implementation.

```bash
conda activate search_decimation
(cd external_lib/ldpc && python setup_reference.py build_ext --inplace)
python -m pytest tests/test_bp.py tests/test_upstream_regression.py -q
```

C++ ReferenceBp(rows,n,probabilities) takes sorted unique column IDs per check and
finite priors in (0,1/2]. It owns immutable copies. Physical weights are computed as
log1p(-p)-log(p) in binary64 and never clipped; the kernel clips a separate copy.
Rows/edges remain in ascending original index order. decode takes a binary syndrome,
iteration cap, Lmax, requested history window, optional -1/0/1 fixed mask and an
optional diagnostic trace flag. Both fixed values remove edges, while fixed ones
XOR the residual syndrome. Beliefs and histories contain only free variables, with
free_ids mapping them back. last_decision is full length with fixed bits restored.
There is no artificial LLR for a fixed variable.

Every call allocates independent residual adjacency, messages and output buffers
and cold-starts from original physical priors. The object is const/reentrant; no
syndrome-dependent state survives between calls. The binding releases the GIL for
one complete native decode and does not call Python during iterations or history
statistics. Concurrent const calls are safe when input objects are not concurrently
modified. Returned vectors own storage, and Python properties return copies.

Zero-degree odd checks return LOCAL_CONTRADICTION before updates. Iteration-zero
syndrome validity returns CONVERGED with zero iterations and empty history. Each
check half-step reads only v_old; the complete c_new buffer supplies the entire
variable half-step. Products use ascending original variable IDs. Degree-one
messages are signed Lmax; other products clamp to tanh(Lmax/2) before atanh and
message clipping. Posterior and extrinsic incoming-message sums accumulate from
zero in ascending check order, then add the clipped prior. Extrinsic accumulation
excludes the target edge before clipping; it never subtracts from a clipped
posterior. Decisions use L<0. Isolated variables retain their prior.

The last min(history_window, completed iterations) posterior vectors are retained
in a native deque, excluding iteration zero. Native mean_llr, abs(mean_llr) and
hard-decision flip counts are computed oldest-to-newest over exactly that window.
No history implies empty statistics. Optional full diagnostic traces include
initialization and all completed iterations, including c/v buffers in active
(check,variable) edge order. NONCONVERGENCE includes the last diagnostic decision,
which must not be treated as a valid correction. The typed project wrapper returns
correction=None on failure and explicit status/iteration/free-ID fields.

The literal ordered exclusion products/sums are deliberate: complexity includes
sums of squared row/column degrees, not a claimed O(E) optimized iteration.
Stage 4 can optimize only while preserving the specified arithmetic and ordering.
No candidate pool ranking, enumeration, screening, fallback or production Python
search loop has been implemented in Stage 3.

build_identity exposes the pinned upstream commit, hash of the header/binding/
wrapper/build recipe, compiler and numerical flags. qec_bp_benchmark.bp verifies
all imported ldpc paths, the manifest commit and current source hash once per
process, rejecting stale/unrelated builds. Rebuild and restart after source edits.

Tests cover a separate scalar residual-matrix oracle with full short message traces,
hand-computable odd checks, saturation and zero messages, exact fixed-zero/one
semantics, contradictions, isolated and empty graphs, history endpoints, random
small graphs, worked-example residual completions, ownership, reuse and concurrent
calls. Standalone C++ debug and ASan/UBSan tests do not require Python. Ordinary
BP-OSD is compared with a pristine pinned wheel in independent subprocess imports,
covering 288 outputs across min-sum/sum-product, fresh/reused objects and shot orders.
