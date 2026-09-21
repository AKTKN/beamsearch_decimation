# Legacy decoder configurations

These configurations select the historical screened_reference, BP-OSD-CS10 and
published beam comparison. Their decoder and sampling settings are preserved.
Paths are relative to this directory: ../../simulation_data and ../../assets keep
the original destinations. Explicit analysis defaults prevent accidental output
under config/assets after relocation.

- smoke, smoke_serial, smoke_two_workers and latency_smoke: historical 32-shot
  all-four-code plan, with different worker/timing modes.
- stage5_validation, stage5_validation_serial and stage5_validation_latency:
  historical four-shot integration plan.
- decoder_sweep: legacy parameter comparison using saved samples.
- production_template: intentionally invalid until physical rates are supplied.
- main.yaml: an existing local experiment, moved with its settings preserved;
  it remains ignored and is not distributed.

Run these with the same shared entry points:

```bash
scripts/run_benchmark.sh config/legacy/smoke.yaml --verbose
scripts/replay_samples.sh SOURCE_RUN config/legacy/decoder_sweep.yaml --verbose
```

The .yaml.example templates are versioned; editable .yaml files remain ignored.
The setup script creates only missing copies in this directory. Historical run
snapshots/logs retain the filenames that existed when those runs were recorded.
