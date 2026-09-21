# Canonical detector problems

convert_dem accepts Stim DEM and optional ordered detector selection, returning
DetectorProblem with CSC H/A, read-only priors/CSC buffers, normalization maps and
hashes. Dataclass dictionaries remain immutable by caller convention. Sparse rows
are detectors/observables and columns are DEM mechanisms, never data-qubit IDs.
Repeat/offset expansion, separator correlations and XOR semantics are mandatory;
no project merging or implicit approximation occurs. reconstruct restores exactly
removed zero mechanisms. Tests: test_dem.py; physical integration: test_circuits.py.
