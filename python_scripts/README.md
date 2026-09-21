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
