"""Single application of the pinned qLDPC circuit noise rule set."""
from collections import Counter
import stim
from qldpc.circuits import NoiseModel
from qec_bp_benchmark.config import Multipliers


def apply_noise(circuit: stim.Circuit, p: float, multipliers: Multipliers,
                eligible_qubits: tuple[int, ...]) -> stim.Circuit:
    """Return new noisy circuit, with errors on every defined idle moment.

    Args:
        circuit: Noiseless physical template. Repeat blocks are flattened first.
        p: Physical sweep probability in [0,0.5], distinct from DEM mechanism priors.
        multipliers: Five validated nonnegative dimensionless factors.
        eligible_qubits: Exactly the physically allocated data and check IDs.
    Returns:
        Owned Stim circuit. qLDPC inserts conflict-separating ticks and applies
        gate/reset noise after the moment, readout flips at measurement, idle
        depolarization once on the complement of occupied eligible qubits.
    Raises:
        ValueError: Already noisy input, invalid rates or allocation.
    """
    import math
    if not math.isfinite(p) or not 0 <= p <= .5:
        raise ValueError("physical rate must be in [0,0.5]")
    probabilities = {k: p * v for k, v in multipliers.model_dump().items()}
    if any(v > 1 for v in probabilities.values()):
        raise ValueError("multiplied noise probabilities must be <=1")
    allocated = set()
    for op in circuit.flattened():
        gate = stim.gate_data(op.name)
        if gate.is_noisy_gate and not gate.produces_measurements:
            raise ValueError("input already contains noise")
        if gate.produces_measurements and any(op.gate_args_copy()):
            raise ValueError("input already contains measurement noise")
        if gate.is_unitary or gate.is_reset or gate.produces_measurements:
            allocated.update(t.value for t in op.targets_copy() if t.is_qubit_target)
    if set(eligible_qubits) != allocated or len(set(eligible_qubits)) != len(eligible_qubits):
        raise ValueError("idle qubit set must equal the actual provider allocation")
    model = NoiseModel(clifford_1q_error=probabilities["one_qubit"],
                       clifford_2q_error=probabilities["two_qubit"], idle_error=probabilities["idle"],
                       reset_error=probabilities["reset"], readout_error=probabilities["measurement"])
    return model.noisy_circuit(circuit.flattened(), system_qubits=eligible_qubits, insert_ticks=True)


def operation_inventory(circuit: stim.Circuit) -> dict:
    """Count flattened instruction occurrences and target applications by name; no mutation."""
    instructions, targets = Counter(), Counter()
    for op in circuit.flattened():
        instructions[op.name] += 1
        targets[op.name] += len(op.targets_copy())
    return {"instructions": dict(sorted(instructions.items())), "targets": dict(sorted(targets.items())),
            "num_measurements": circuit.num_measurements, "num_ticks": circuit.num_ticks,
            "num_detectors": circuit.num_detectors, "num_observables": circuit.num_observables}
