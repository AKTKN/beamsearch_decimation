# Native reference BP checks

Standalone assert-based C++ tests check hand-computable syndrome signs, degree-one
messages, zero ties, structural fixed values, history bounds, isolated variables,
empty graphs, reuse and invalid numerical inputs. No Python runtime is involved.
Root CMake exposes QEC_BUILD_TESTS and QEC_SANITIZE; ctest runs reference_bp.
The scalar complete-message oracle and native binding tests live one directory up.
