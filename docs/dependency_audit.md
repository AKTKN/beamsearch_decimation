# Dependency audit

All six URLs in the contract were obtained as actual Git checkouts. Exact HEAD
commits, versions and imported paths are recorded in external_lib/manifest.lock.json.
Build/package versions are locked in requirements.lock.txt. At initial acceptance, no source was published.
The local ldpc branch is screened-decimation-bp, with upstream pointing to
https://github.com/quantumgizmos/ldpc. No user hosted fork remote was supplied.

ldpc 2.4.1: inspected src_cpp/bp.hpp and src_python/ldpc/{bp_decoder,bposd_decoder}.
Accepted baseline parameters are error_channel, max_iter, bp_method='minimum_sum',
schedule='parallel', ms_scaling_factor=1.0, osd_method='OSD_CS', osd_order=10,
omp_thread_count=1. The upstream kernel uses <=0 decisions and prefix/suffix
accumulations with different saturation/degree-one conventions; it is not the
specified reference sum-product profile. Stage 3 therefore adds a separate API.
The baseline unmodified wheel is retained under external_lib/wheels/ and installed
in external_lib/pristine_ldpc/ for subprocess regression comparisons.

BeamSearchDecoder: inspected decoder/beam_search_decoder/_beam_search_decoder.pyx
and decoder/src_cpp/beam_search.hpp. Constructor requires pcm and error_channel.
The five controls actually consumed are max_rounds, beam_width, num_results,
initial_iters, iters_per_round. channel_probs is read but is not used as the
required error_channel. Generic bp_method is not implemented; **kwargs silently
accepts unknown keys, so our schema rejects them. The kernel is min-sum without a
user-selectable method, with upstream ordering, ties, masking and saturation left
untouched. No generic ldpc configuration is forwarded. The wrapper's decode method
returns one length-n correction, despite some generic documentation. Inputs must
be validated independently by the implemented adapter. Upstream uses C++20/-O3. Original CC BY-NC-SA
license and MIT third-party notices are retained. Source-generated .cpp/.pyi build
changes are recorded; no baseline algorithm changes are intended.

qLDPC 0.3.3: inspected src/qldpc/codes/quantum.py BBCode and
circuits/memory/{memory,syndrome_measurement}.py plus circuits/noise_model.py.
BBCode({x:6,y:6}, x**3+y+y**2, y**3+x+x**2) has 72 data and 12 logical qubits.
Its CSS convention is Hx=[A,B], Hz=[B.T,-A.T], agreeing in GF(2) with the original
BivariateBicycleCodes/decoder_setup.py. The original file defaults to BB144;
only its commented BB72 parameter set is relevant, not its default circuit.

get_memory_experiment(..., basis=Pauli.Z, num_rounds=6, noise_model=None) performs
six full extraction rounds, Z-product preparation and destructive Z readout,
with all twelve Z logical annotations. It physically measures both sectors but
annotates only Z checks in this basis. EdgeColoring defaults to smallest_last,
measures X subgraphs before Z subgraphs with ancillas in X basis and controlled
Pauli gates. This is not the original seven-layer CNOT schedule and carries no
circuit-distance guarantee. get_memory_experiment_parts exposes qubit/measurement/
detector bookkeeping for verification.

NoiseModel accepts clifford_1q_error, clifford_2q_error, readout_error, reset_error,
idle_error. Its two-qubit float is a two-qubit channel (an upstream docstring says
one-qubit erroneously); operation-level tests verify DEPOLARIZE2. DepolarizingNoiseModel
has include_idling_error=False by default, so it cannot be used without an override.
noisy_circuit can insert TICKs for conflicts and accepts an explicit system_qubits
set; default range(num_qubits) would include surface coordinate-label holes. The
project explicitly uses only allocated, physically addressed qubits.

Stim is built from its pinned source. DEM extraction disables decomposition and
implicit disjoint/gauge approximation. flattening expands repeats/offsets; project
conversion retains XOR supports and one variable per error instruction. stimbposd
is source-only comparison material; its converter is not the production converter.

Initial qLDPC installation with uv-build 0.12.17 failed because the executable was
not in the active PATH. Re-running with the conda bin directory in PATH and the
upstream-compatible pinned uv-build 0.9.30 fixes the installation.

The initial Stim HEAD build with pybind11 3.1.0 failed in
tableau_simulator.pybind.cc (lambda return-type deduction between typed tuples).
Resolution: pin release v1.16.0 and its compatible pybind11 2.11.1, rebuild from
source without changing Stim code. All package/build versions are in the lock.
The unmodified BP-OSD binding requires error_channel as a Python list at this
revision; a NumPy vector is rejected. This was verified and corrected in the
regression workload, not patched in the baseline.

Converter source audit: stimbposd/dem_to_matrices.py keys hyperedges by detector
support alone, combines their priors and overwrites the logical-support entry.
It therefore does not satisfy this benchmark's same-detector/different-observable
requirement. A regression fixture demonstrates that divergence; the project's
independently authored converter retains both columns and both logical signatures.
qLDPC's memory_test.py and syndrome_measurement_test.py were also inspected for
round counts, qubit mapping and actual controlled-Pauli syndrome extraction.

## Git distribution source audit

The parent Git repository distributes the pinned manifest and existing patches.
Nested dependency repositories are excluded, preserving their original upstream
remotes and the local screened-decimation-bp branch. No dependency source/build
bytes changed during this maintenance; the locked audit was not regenerated.
The ldpc patch still contains reference_bp/bindings.cpp. Historical import paths
and acceptance logs describe their original environment.
