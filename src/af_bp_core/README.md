# AF-BP graph factorization core

`graph.hpp` is a standalone C++17 module implementing the graph operations in
`adaptive_graph_refactorization_bp_spec.tex`. It depends only on the standard
library. It does not call BP, sample circuits, read truth, or use the simulator,
Parquet, plotting, or experiment configuration. The standalone test can be run with
`python -m pytest -q tests/test_af_bp_graph_core.py`.

`decoder.hpp` implements the AF-BP-1.0 state machine in C++ by composing this
graph core with the opt-in fork header `external_lib/ldpc/src_cpp/af_bp.hpp`.
It accepts only physical H/A rows, channel probabilities, syndrome and
`DecoderSettings`. It owns H/A/probabilities and creates a fresh graph and BP
engine state per shot. The result has `valid`, correction, A prediction,
`total_iterations`, graph/factorization counts and status. Failure returns no
accepted correction. There is no OSD fallback or logical-truth input. The
Python `AFBPDecoder` in `qec_bp_benchmark.af_bp_service` only marshals arrays
and calls this native service once per shot. Stage 6 registers that boundary
through the active `DecoderAdapter`; the native source remains independent
of simulator sampling, Parquet, and plotting.

The first BP call uses `initial_iteration_budget`; later graph instances use
`transformed_iteration_budget`. `initial_parallel=true` forces ordinary
parallel Min-Sum only on the first graph. Otherwise the configured parallel,
serial or qDither variant applies from the start. Both budgets are hard caps
on actual Min-Sum iterations, including all qDither chains. Physical failure
weights and U stay fixed within each `n_fact` pass; each accepted transform
immediately appends its parity-LLR handoff for any subsequent nested transform.
`atanh_epsilon` clips the parity product before `atanh`. Existing variables
receive previous final marginals only as edge-message initialization; base
physical priors and zero auxiliary priors remain unchanged. qDither graph
relay requires `graph_warm`; `paper` is allowed only without graph relay.

The native `seed_policy` is `fixed` (same configured seed on each graph) or
`syndrome_derived` (deterministically mixes the configured seed, binary
syndrome and graph index). Repeating a shot on one decoder resets state and
replays the same result. Diagnostics are optional; a normal Python call returns
only compact result fields. The CMake target hashes its graph/service/binding,
fork BP header and build inputs to reject stale binaries in the source checkout.
Build with `python -m pip install --no-build-isolation --no-deps -e .` in
`search_decimation`; the native service integration assertions are
`tests/test_af_bp_decoder_native.py` and `tests/test_af_bp_service.py`.

`Graph(rows, base_llrs, syndrome)` owns copies of the immutable physical rows,
syndrome, base unary LLRs, and mutable current adjacency. IDs remain stable as
auxiliary variables and checks are appended. Each adjacency list stays sorted;
`add_edge` and `remove_edge` reject duplicate or missing edges. Physical
support is implicit for original variables. Only auxiliary variables own
sorted sparse physical-support IDs, combined with symmetric difference.
`physical_support` returns a copy; `variable` and `check` return const views
valid until the graph is mutated or destroyed.

`failure_weights` uses the immutable original graph for residual syndrome and
Tanner distance. It consumes the supplied trailing physical marginal rows;
with one row, oscillation is zero. The caller must pass the final failed BP
call's history, and keep the resulting physical `omega` and suspicious set `U`
fixed throughout `factorize_graph`. `discover` returns deduplicated closed
pair-seeded bicliques in lexicographic order. The production factorization
loop visits the same pair seeds without retaining all candidate lists: repeated
closed bicliques can be scored again but cannot change the selected optimum.

`net_cycle_reduction` computes exact weighted `Phi(before)-Phi(after)` from
affected check pairs and the new defining check. It does not create a trial
graph. Candidate A uses this net score and stops when the best is nonpositive.
Candidate B maximizes only the internal 4-cycle count; it is a Shen-style
selection baseline without Shen's further cleanup. Ties use the sorted `S`
then `C` IDs. Every accepted operation mutates the graph once, discards old
pair seeds, and starts a new discovery/scoring pass. Candidate diagnostics
record edge counts, maximum degrees, and auxiliary counts without penalties.

Let `V,C,E` be current variables, checks and edges, `E0` immutable physical
edges, `L` the sum of sparse auxiliary-support lengths, and `P` the number of
check pairs sharing at least one relevant variable. Graph storage is
`O(V+C+E+E0+L)`. One production factorization pass uses `O(V+C+P+|S|+|C_B|)`
additional working space, including weights, activity flags, pair IDs, and
one candidate at a time; the returned chosen-step diagnostics add at most
`O(n_fact*(|S|+|C_B|))`. There is no `O(candidates*E)` or
`O(candidates*V)` graph-copy allocation. Pair accumulation takes
`O(sum_v degree_rel(v)^2)` time before intersection and closure checks.
Candidate scoring visits affected check pairs rather than all graph cycles;
its cost depends on `|C_B|`, check degrees, and intersections with `S`.

The native tests include an intentionally full-copy oracle on tiny graphs,
exhaustive physical assignments and auxiliary lifts, random small graph
discovery/delta comparisons, policy/rediscovery cases, and a 20,000-variable
sparse-support check. No dense physical-support vector is stored per variable.
