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
