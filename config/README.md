# Configuration templates

Top-level templates cover the active hybrid workflow:

- analysis.yaml.example: saved-data-only settings; no simulation parameters required.

- hybrid_smoke.yaml.example: bounded surface d=3/BB72 checks with hybrid, CS0 and beam.
- hybrid_latency.yaml.example: separate one-worker isolated latency checks.
- hybrid_ablations.yaml.example: warm/cold/no-BP comparisons.
- hybrid_production_template.yaml.example: surface d=5,7,9 and BB72; supply rates
  explicitly before use. It intentionally rejects the empty physical rate list.
- bposd_cs0_smoke.yaml.example: current upstream CS0/CS10/beam baseline comparison.

Historical screened-reference/CS10 experiment templates and local copies are in
legacy/. The local main.yaml also moved there with all rates, seeds, budgets and
comments preserved. Relative paths were rebased to keep the same circuit cache,
run and analysis destinations. See legacy/README.md for the old configuration matrix.

Simulation/replay entry scripts are shared: choose a decoder workflow through YAML.
Current analysis accepts its own analysis-only YAML or a validated benchmark YAML;
legacy analysis entry points remain under scripts/legacy/.
For example, scripts/run_benchmark.sh config/hybrid_smoke.yaml.example runs the
hybrid, while scripts/run_benchmark.sh config/legacy/smoke.yaml.example runs the
historical comparison. Both create new run directories and use current v2 storage.

Editable .yaml/.yml files are ignored at both levels. scripts/setup_local_files.sh
creates missing working copies beside templates in config/, config/legacy/ and
notebook/, preserving existing files and symlinks. Templates can also be run directly.
Relative paths always resolve from the YAML's directory; config.py has no special
legacy-path handling. Archived run configurations remain unchanged.

Analysis controls bootstrap_seed, bootstrap_count, bootstrap_unit (shot or batch),
accuracy_margin_absolute (null by default), confidence, quantiles, plot selections,
stratification and tail-support thresholds. See docs/configuration.md and
the configuration audit in docs/configuration_audit.md for validation/consumers.
The complete resolved smoke example is docs/examples/hybrid_manifest.json; its
rates/counts are software checks, not production recommendations.
