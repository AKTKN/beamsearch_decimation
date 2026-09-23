# Native reference BP checks

Standalone assert-based C++ tests check hand-computable syndrome signs, degree-one
messages, zero ties, structural fixed values, history bounds, isolated variables,
empty graphs, reuse and invalid numerical inputs. No Python runtime is involved.
Root CMake exposes QEC_BUILD_TESTS and QEC_SANITIZE; ctest runs reference_bp.
The scalar complete-message oracle and native binding tests live one directory up.

Hybrid tests: test_hybrid_bp.cpp checks 1,024 direct pinned CS0/OSD0 cases;
test_hybrid.cpp checks 768 reference/optimized decode cases, exact branch partitions
and deterministic allocation failure/recovery. Both are included in all CMake
QEC_BUILD_TESTS builds and QEC_SANITIZE configurations. benchmark_hybrid_search.cpp
is a manual fixed-fixture engineering measurement, not a ctest or physics result.

`test_lpm_dp.cpp` checks the standalone LPM-DP 1.0 candidate generator, including
region and cavity conventions, four-state marginal/top-K DP, retained mass,
64-bit fixation words, invalid inputs and 600 fixed-seed small local problems
against an independent exhaustive oracle. It does not exercise a recursive
decoder, OSD or simulator path.
