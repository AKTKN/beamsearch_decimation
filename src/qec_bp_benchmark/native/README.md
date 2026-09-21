# Native screened decoder

`search.hpp` implements static history-based pool ranking, increasing-index subset
and lexicographic bit enumeration, structural residual checks, weighted lower
bounds, exact bounded-heap top K, every cold-start completion, and physical-cost /
full-vector lexicographic selection. All pattern and BP iteration loops are C++.
The kernel is the same `ldpc/src_cpp/reference_bp.hpp` used by Stage 3. The extension
embeds source hashes for its kernel, search, binding and CMake definition; Python
verifies these plus the installed fork identity before use. Rebuild after edits.

The heap stores only K patterns. Per-pattern masks/residuals/degrees are allocated;
BP builds a residual adjacency for each call. This implementation makes no allocation
or latency advantage claim. Physical weights are never clipped. Only odd empty
checks reject screening patterns; no propagation, warm starts or fallback is used.
Every score is compared exactly as binary64 (f,rho,canonical ID). Equal full-vector
winners retain the first pattern in screening order for diagnostics.

`ScreenedDecoder` copies graph and priors; decode is const with owned per-call
buffers and releases the GIL. Results own their vectors. Production methods validate
syndromes and settings. pool/score/screen are exposed for independent small tests.
Diagnostics retain history, top K and completion decisions only when requested;
required native history statistics are always computed. Optional phase clocks use
steady_clock and are separately labeled; normal decoding has no phase clock calls.
Pattern counts exceeding uint64 are rejected before enumeration, without changing
requested budgets. Compile with C++17, no fast-math and no FP contraction.


The above contracts describe historical `screened_reference` only. The authorized
hybrid uses persistent bounded correction search and stateful finite-hint min-sum
with direct OSD0. Stages 2-3 now implement this kernel in hybrid_model.hpp, hybrid_search.hpp,
hybrid_telemetry.hpp and hybrid.hpp, sharing the fork sessions directly. The
reference path uses full recomputation/linear queue scans; production uses cached
active-column counts, reusable reduction buffers and two exact heaps. Packed
residuals, parent deltas and canonical keys preserve decisions. hybrid_bindings.hpp
formats summaries and exported records natively. The complete decode releases the
GIL and rejects concurrent calls on one session. CMake watches source inputs and
embeds aggregate project/fork hashes verified at runtime. See docs/hybrid_native.md
for interfaces, counter definitions, clocks, limitations and validation.

Final hybrid acceptance builds all four standalone native tests in Release, Debug
and ASan/UBSan configurations. The isolated restoration check additionally builds
a fresh project extension against the patched source-only ldpc tree and verifies
its embedded project/fork digests before executing the service. See
docs/hybrid_acceptance.md (from the repository root) for scope and reproducible commands.
