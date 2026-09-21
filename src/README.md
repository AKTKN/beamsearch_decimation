# src

Importable package sources. Install the root pyproject; reference examples are excluded. Tests live in tests/.

qec_bp_benchmark owns circuits, canonical DEMs, native BP/search adapters, deterministic
paired execution, storage and provenance. The same root installation also includes
the separate top-level analysis/ package for saved-data consumers. Native implementations
and their tests are documented in qec_bp_benchmark/native/README.md; no benchmark
algorithm resides in a shell script or notebook.
