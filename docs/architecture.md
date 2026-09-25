# Active architecture after Stage 6

The simulation package is organized around a fixed physical experiment and a
replaceable truth-free decoder service. AF-BP, Relay-BP, Beam8, and BP-OSD
share the same physical samples and the same complete-service timer.

1. `config.py` validates physical conditions and the four active decoder
   profiles. AF-BP settings map into the Stage-4 native service.
2. `circuits/`, `dem/model.py` and `artifacts.py` create and cache the verified
   physical circuit, selected Z-check model, original H/A and mechanism priors.
3. `runner/plan.py`, `runner/worker.py` and `runner/pipeline.py` keep physical
   sampling, paired shots, cyclic decoder order and single/spawn-worker behavior.
4. `decoders/__init__.py` prepares AF-BP and pinned upstream baselines, invokes one complete
   service per syndrome, validates against original H and predicts A. It sees no
   logical truth. The worker times the entire service with `perf_counter_ns`.
5. `storage/minimal.py` writes five-field `benchmark_results/2` rows.
   `analysis/simple_results.py` summarizes active data; `analysis/benchmark_plots.py`
   draws logical-error, latency, and total-iteration figures. Historical
   plotting lives under `analysis/legacy/`.

Beam8's fork-local change adds an observation counter for all initial and masked
BP iterations. Its branching, messages, correction decisions and existing `iter`
field are unchanged. BP-OSD reports upstream BP iterations, with zero on its
zero-syndrome shortcut; OSD adds no BP steps. Relay uses upstream
`RelayDecoderF64.decode_detailed` and returns exact initial-plus-relay-leg BP
iterations. It never invokes upstream batch parallelism. The active CMake build
has one separately callable AF-BP service target, registered through the
truth-free Python adapter.

Historical project-native C++ files remain in `src/qec_bp_benchmark/native/` for
source provenance but are excluded from CMake. Fork reference/hybrid sources
remain in `external_lib/ldpc` but are not built by the active dependency script.
Historical maps and source contracts are indexed in
[legacy decimation](legacy/decimation/README.md).

Stage 2's opt-in `ldpc.af_bp` BP engines, Stage 3's standalone
`src/af_bp_core/graph.hpp` graph core, and Stage 4's
`src/af_bp_core/decoder.hpp` state machine are integrated without changing
the native scientific implementation. The C++ service owns physical H/A/probabilities, creates
shot-local graphs, calls BP directly, validates returned corrections against
original H, and computes A predictions without truth input. The Python module
`qec_bp_benchmark.af_bp_service` marshals one syndrome per native call. See
[AF-BP core](../src/af_bp_core/README.md).
