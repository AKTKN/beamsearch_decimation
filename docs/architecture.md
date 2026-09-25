# Active architecture after Stage 1

The simulation package is organized around a fixed physical experiment and a
replaceable truth-free decoder service. AF-BP and Relay-BP are reserved future
profiles and cannot be instantiated in an active config.

1. `config.py` validates physical conditions and only `beam8` or `bposd` decoder
   profiles. `bposd.osd_order` is a nonnegative option (default 10).
2. `circuits/`, `dem/model.py` and `artifacts.py` create and cache the verified
   physical circuit, selected Z-check model, original H/A and mechanism priors.
3. `runner/plan.py`, `runner/worker.py` and `runner/pipeline.py` keep physical
   sampling, paired shots, cyclic decoder order and single/spawn-worker behavior.
4. `decoders/__init__.py` prepares pinned upstream baselines, invokes one complete
   service per syndrome, validates against original H and predicts A. It sees no
   logical truth. The worker times the entire service with `perf_counter_ns`.
5. `storage/minimal.py` writes `baseline_results/1` rows. `analysis/simple_results.py`
   summarizes the active data; `analysis/benchmark_plots.py` draws baseline
   latency and logical-error figures.

Beam8's fork-local change adds an observation counter for all initial and masked
BP iterations. Its branching, messages, correction decisions and existing `iter`
field are unchanged. BP-OSD reports upstream BP iterations, with zero on its
zero-syndrome shortcut; OSD adds no BP steps. The active CMake build has no
project-native decoder target.

Historical project-native C++ files remain in `src/qec_bp_benchmark/native/` for
source provenance but are excluded from CMake. Fork reference/hybrid sources
remain in `external_lib/ldpc` but are not built by the active dependency script.
Historical maps and source contracts are indexed in
[legacy decimation](legacy/decimation/README.md).
