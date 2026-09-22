# Thin entry points

prepare_circuits.py CONFIG.yaml parses validated YAML, sets thread limits, calls
artifact preparation and records the resolved configuration. It runs no decoders.
audit_dependencies.py records current exact Git/build/import identities and patches.
build_dependencies.py restores/builds pinned local sources; --check verifies installs.
Numerical/configuration behavior lives in src/, with tests under tests/. No scientific
experiment parameters belong in these command wrappers.

run_benchmark.py CONFIG.yaml executes the current minimal-output runner. It accepts
-v/--verbose for flushed parent progress on stderr; stdout remains the completed
run path. The flag changes no decoder/sampling configuration. Manifest-based replay
belongs to the historical workflow and is not accepted by the current runner.

benchmark_simulation.py CONFIG measures startup, sampling, simulation-side row
handling, Arrow conversion and Parquet I/O while keeping each decoder invocation
opaque. It forces one worker, writes production-format output only under a temporary
root, removes it after each repeat, and can save a standalone JSON engineering
report with `--output`. See `docs/simulation_timing_benchmark.md`.

analyze_benchmark.py CONFIG --run RUN and execute_notebook.py CONFIG --run RUN
belong to the older report workflow. The current lightweight consumer is
`analysis.simple_search_bp`. clean_build.py OUTPUT_ROOT creates
independent source checkouts and a fresh conda prefix, then invokes the existing
pinned build helper and audits imports; it runs no scientific sweep.

Hybrid builds are integrated into build_dependencies.py and audit_dependencies.py.
Missing opt-in files are restored independently without overwriting local edits;
setup_hybrid.py compiles the new binding, --check verifies its aggregate digest,
and audit exports ignored binding/stub files plus transitive header hashes. The
clean_build.py workflow inherits these steps through build_dependencies.py.

Use config/hybrid_smoke.yaml.example or hybrid_latency.yaml.example for bounded
checks; the run CLI prints only the final output path on stdout.

`validate_config.py CONFIG` is the side-effect-free search_bp dry run: it validates
strict YAML, resolves paths and cycle arrays, checks enabled registry profiles and
prints JSON. Execution uses the current run CLI and direct named-Parquet reader.

The historical acceptance, replay, and manifest-verification entry points were
removed from the active CLI set during the minimal-output migration. Their evidence
and legacy analysis implementation remain preserved in docs and `analysis.legacy`.

Simulation/build CLIs remain shared. The pre-migration analysis and notebook entry
points are preserved under python_scripts/legacy/ and route to analysis.legacy.

SEARCH-BP-2.0 validation is contract-only: validate_config.py intentionally does
not call the execution availability guard. run_benchmark rejects this decoder
before side effects. See docs/search_bp_v2_design.md.
