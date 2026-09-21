# Thin entry points

prepare_circuits.py CONFIG.yaml parses validated YAML, sets thread limits, calls
artifact preparation and records the resolved configuration. It runs no decoders.
audit_dependencies.py records current exact Git/build/import identities and patches.
build_dependencies.py restores/builds pinned local sources; --check verifies installs.
Numerical/configuration behavior lives in src/, with tests under tests/. No scientific
experiment parameters belong in these command wrappers.

run_benchmark.py CONFIG.yaml executes the paired runner. replay_samples.py SOURCE_RUN
CONFIG.yaml decodes the committed saved dataset with YAML decoder/execution/output
settings. Both imports stay numerical-library-free until configuration/thread setup.
Both accept -v/--verbose for flushed parent progress on stderr; stdout remains the
completed run path. The flag changes no decoder/sampling configuration.

analyze_benchmark.py CONFIG --run RUN reads verified saved data and exports reports;
execute_notebook.py CONFIG --run RUN --output NEW.ipynb runs the source notebook in
an ephemeral active-environment IPC kernel. verify_benchmark.py RUN [--compare RUN]
checks integrity and exact non-timing equality. clean_build.py OUTPUT_ROOT creates
independent source checkouts and a fresh conda prefix, then invokes the existing
pinned build helper and audits imports; it runs no scientific sweep.

Hybrid builds are integrated into build_dependencies.py and audit_dependencies.py.
Missing opt-in files are restored independently without overwriting local edits;
setup_hybrid.py compiles the new binding, --check verifies its aggregate digest,
and audit exports ignored binding/stub files plus transitive header hashes. The
clean_build.py workflow inherits these steps through build_dependencies.py.

Hybrid Stages 4–5 use the same run/replay/analyze/execute-notebook CLIs. Run/replay
now write v2 tables; analysis reads v1 and v2. For the maintained hybrid notebook,
pass `--notebook notebook/benchmark_analysis.ipynb.example` and a new output path.
Use config/hybrid_smoke.yaml.example or hybrid_latency.yaml.example for bounded
checks; the CLI still prints only the final output path on stdout.

`accept_hybrid.py --output NEW_DIRECTORY` runs final bounded hybrid acceptance:
fresh surface/BB artifacts, one/two workers, isolated timing, replay, no profiling,
ablations, report CLI and notebook. It saves exact commands/logs and verification.json,
checks all BB labels and scientific equality, and refuses existing output directories.
