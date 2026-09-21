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


Hybrid migration templates: `hybrid_smoke.yaml.example`,
`hybrid_ablations.yaml.example`, and `hybrid_production_template.yaml.example`.
They resolve and validate the new contract and execute through run/replay with v2
tables. Production intentionally has no physical rates. `bposd_cs0_smoke` runs
actual upstream BP-CS0, CS10 and beam with v2 output. Its small
numbers are software checks only. Existing local YAML files remain untouched by
setup. The migration map documents every new field and ablation/default constraint.

## Hybrid hypothesis settings

hybrid_smoke.yaml.example is a bounded surface/BB throughput check;
hybrid_latency.yaml.example is a separate one-worker isolated-latency check;
hybrid_ablations.yaml.example enables warm, cold and no-BP profiles. All use four
shots per code at an explicitly labeled software-check rate. Run templates directly
or materialize missing local files with scripts/setup_local_files.sh.

Analysis adds bootstrap_seed (20260921), bootstrap_count (2000), bootstrap_unit
(shot or batch), and accuracy_margin_absolute (null by default, otherwise [0,1]).
The existing confidence applies to Wilson/paired percentile intervals and the
one-sided noninferiority criterion. Every effective setting is saved. No margin
means no equivalence claim. Production rates remain user supplied.

The production template also explicitly lists the paired-bootstrap/accuracy and
plot controls; its physical rate list remains empty. The final resolved manifest
example is docs/examples/hybrid_manifest.json. Its numeric rate is a software-check
example, not a production recommendation.
