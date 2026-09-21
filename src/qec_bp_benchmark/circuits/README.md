# Physical circuits

make_template returns owned CircuitTemplate circuits and provider bookkeeping;
algebra.validate_bb72 checks independent binary algebra. apply_noise applies the
five qLDPC channels once on an explicit allocated-qubit set. select_z_detectors
returns an owned DetectorView with absolute parity provenance and both index maps.
Inputs are not modified; template arrays/dicts are immutable by caller convention.

See docs/circuits.md for actual schedule, moment and boundary assumptions. Both
physical extraction sectors remain present. Tests: test_circuits.py and BB API audit.
