# Circuit, noise and DEM conventions

Rotated surface code uses Stim's noiseless rotated_memory_z generator; d=5,7,9
and R=d by default. BB72 uses qLDPC
`BBCode({x:6,y:6},x^3+y+y^2,y^3+x+x^2)`; BB144 uses the same polynomials with
orders `{x:12,y:6}`, matching qLDPC's `[[144,12,12]]` example. Independent binary
elimination verifies the expected 12 logical pairs, `Hx Hz^T=0`, logical/check
commutation, full augmented ranks and `Lx Lz^T=I12` for both codes. Matrices agree
exactly with qLDPC's cyclic-shift convention without transposing the polynomials.
Published distances six and twelve are metadata, not proofs of circuit distance or
schedule fault tolerance.

qLDPC EdgeColoring(smallest_last) acts on X and then Z Tanner subgraphs. All check
ancillas are reset/read in X; CX gates extract X checks and CZ gates extract Z
checks. This general library schedule is not the original optimized seven-layer
CNOT schedule. Both sectors are executed every round. There are exactly 72 check
measurements per BB72 round, six rounds, then 72 destructive data measurements:
504 total records and 252 Z detectors (36 at each of seven time boundaries). BB144
has 72 checks in each sector and 144 data qubits; its default is twelve rounds.
Preparation is product Z reset; readout is destructive data Z. There are no extra
ideal cycles. qLDPC initialization/extraction can share a moment where qubits are
disjoint, as allowed by its provider. Noise applies to the entire concatenated
noiseless circuit, not independently to disconnected pieces.

All templates are flattened before noise injection. The pinned qLDPC noise utility
inserts TICKs where operations reuse a qubit within a moment. Existing TICK
boundaries are respected. An explicit system_qubits set includes all and only
physically addressed data/check qubits for the entire experiment, including before
first use and after final use. Surface index holes are excluded. No qubit is immune.
The exact emitted schedule and inventory are persisted. Empty annotation-only
moments, if emitted by a provider, follow qLDPC's moment semantics and are visible
in the circuit; there is no second noise pass.

NoiseModel uses the five separately scaled probabilities. It appends depolarizing
Clifford errors after the moment (disjoint simultaneous gates commute with this
placement). Measurements get an outcome-flip probability; reset errors follow the
reset, X_ERROR for Z reset and Z_ERROR for X reset. Combined MR has independent
readout flip and post-reset wrong-state error. Idle noise occurs once per moment
on eligible qubits absent from all physical operations in that moment. No additional
waiting-for-measurement/reset noise is added. Unequal multipliers, sparse allocation,
conflict splitting, MR and both reset bases have exact operation tests.

Surface check classification uses actual MR ancillas, H support and validated CX
control/target orientation, never coordinate parity. BB uses provider QubitIDs,
independently checked against controlled-Pauli gates and CSS matrix supports.
Detector parity records are expanded to absolute measurement indices; each must
refer to one check sector/qubit with the appropriate adjacent-round or final-readout
support. Every physical check is measured R times. Observable parity is matched
against the independent Lz basis. Full-to-selected maps use -1 for excluded rows.
The selected circuit changes only DETECTOR annotations. Tests apply both m2d
converters to exactly the same physical measurement record.

DEM extraction disables decomposition, retains hyperedges, and forbids gauge
approximation. Disjoint-error approximation is false by default and explicit in
YAML/metadata if requested. DEM flattening resolves repeat/offset semantics, then
XOR support is accumulated across separator components into one Bernoulli column.
No project merging occurs. Same detector support with different observables remains
distinct; logical-only and even empty-support instructions remain distinct. Zero
priors are removed with reconstruction maps. Above-half/deterministic probabilities
are rejected; all preprocessing offsets are therefore exactly zero. H and A are
canonical CSC binary matrices; probabilities are mechanism priors. Empty stochastic
models work at p=0. Native search's positive-depth constraints will not be relaxed.

Artifacts are content-addressed under the YAML circuit.cache. Every artifact retains
noiseless/noisy/selected circuits, DEM, CSC arrays, priors, maps, BB algebra, noise
inventory and complete checksums. Preparation can be repeated without overwriting
existing bytes and detects corruption. Cross-process tests with different Python
hash seeds verify the pinned BB schedule. No statistical agreement substitutes for
exact converter parity: tests include a controlled two-fault physical circuit and
all its outcomes, plus explicit repeat/separator/logical-only fixtures.
