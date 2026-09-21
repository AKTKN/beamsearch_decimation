# config

Strict YAML examples: smoke, isolated latency, decoder sweep, and intentionally non-runnable production template. Fields and constraints are defined in qec_bp_benchmark.config. Relative paths use the YAML directory. Tests: test_config.py.

stage5_validation.yaml is the finite four-shot/all-four-code/all-three-decoder
integration case, with two workers and a final short batch. smoke.yaml and
latency_smoke.yaml are now executable; their output.root controls run location.
Replay uses any validated YAML for decoder/execution/output settings and the saved
source batches for its physical dataset, regardless of that YAML's physical grid.
The stage5_validation_serial.yaml and stage5_validation_latency.yaml files preserve
that exact physical plan while changing execution/timing mode for equality checks.

smoke_serial.yaml and smoke_two_workers.yaml preserve the full smoke.yaml 32-shot
plan with one and two throughput workers. latency_smoke.yaml uses that same plan
with one isolated worker. All use explicitly labeled implementation p=0.001.
analysis controls confidence, additional quantiles, selected ECDF/survival/failure
plots, optional path strata, tail-count threshold and input/output directories.
See docs/configuration.md for every field and docs/configuration_audit.md for its
consumer, recorded evidence and tests. Production rates remain user-supplied.

Editable *.yaml/*.yml files are ignored. Versioned *.yaml.example files preserve
the validation configurations. Run scripts/setup_local_files.sh after cloning; it
creates only missing working copies. config/main.yaml is a local experiment and
is not distributed. Change templates explicitly to publish new defaults.
