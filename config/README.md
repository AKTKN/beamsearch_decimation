# Configuration templates

Top-level templates cover the active workflow:

- analysis.yaml.example: saved-data-only settings; no simulation parameters required.

- bposd_cs0_smoke.yaml.example: current upstream CS0/CS10/beam baseline comparison.
- search_bp.yaml.example: SEARCH-BP-2.0 contract-only dry run; decoding is unavailable.

`python python_scripts/validate_config.py CONFIG` prints resolved JSON without
preparing circuits or executing decoders.

Historical screened-reference/CS10 templates are in `legacy/`; soft-hint hybrid
and HSBP-FB templates are in `legacy/hybrid/`. They preserve their source settings
but are intentionally not accepted as current `search_bp` configurations.

Simulation entry scripts are shared: choose a decoder workflow through YAML.
Current analysis accepts only its independent analysis YAML; simulation YAML does
not contain analysis settings. Legacy analysis entry points remain under
scripts/legacy/.
For example, scripts/run_benchmark.sh config/legacy/hybrid/hybrid_smoke.yaml.example runs the
hybrid, while scripts/run_benchmark.sh config/legacy/smoke.yaml.example runs the
historical comparison. Both create new run directories using the five-field minimal output.

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
