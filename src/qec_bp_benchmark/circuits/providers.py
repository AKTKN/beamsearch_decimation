"""Noiseless pinned physical circuit providers with explicit qubit provenance."""
from __future__ import annotations
from dataclasses import dataclass
import stim
import numpy as np
from .algebra import validate_bb72


@dataclass(frozen=True)
class CircuitTemplate:
    """Owned noiseless circuit and metadata; callers must not mutate shared fields."""
    circuit: stim.Circuit
    data_qubits: tuple[int, ...]
    check_sectors: dict[int, str]
    check_supports: dict[int, tuple[int, ...]]
    metadata: dict
    algebra: dict[str, np.ndarray]


def make_template(family: str, distance: int, rounds: int | None = None) -> CircuitTemplate:
    """Create full extraction circuit for surface or BB72 Z memory.

    Args:
        family: 'surface' or 'bb72'.
        distance: Odd surface distance >=3, or published BB72 distance 6.
        rounds: Positive extraction count; None resolves to distance.
    Returns:
        New circuit and provider-derived check/physical-qubit bookkeeping.
    Raises:
        ValueError: Unsupported family, dimensions, schedule or check provenance.
    """
    if type(distance) is not int or (rounds is not None and (type(rounds) is not int or rounds < 1)):
        raise ValueError("distance/rounds must be valid integers")
    resolved_rounds = distance if rounds is None else rounds
    algebra = {}
    if family == "surface":
        if distance < 3 or distance % 2 == 0:
            raise ValueError("surface distance must be odd and at least three")
        c = stim.Circuit.generated("surface_code:rotated_memory_z", distance=distance, rounds=resolved_rounds).flattened()
        anc = {t.value for op in c if op.name == "MR" for t in op.targets_copy()}
        data = tuple(sorted({t.value for op in c if op.name == "M" for t in op.targets_copy()}))
        h_targets = {t.value for op in c if op.name == "H" for t in op.targets_copy()}
        if h_targets - anc:
            raise ValueError("unexpected surface Hadamard support")
        sectors = {q: "X" if q in h_targets else "Z" for q in sorted(anc)}
        supports = {q: set() for q in anc}
        for op in c:
            if op.name == "CX":
                ts = op.targets_copy()
                for control, target in zip(ts[::2], ts[1::2]):
                    u, v = control.value, target.value
                    if u in anc and v in data and sectors[u] == "X":
                        supports[u].add(v)
                    elif v in anc and u in data and sectors[v] == "Z":
                        supports[v].add(u)
                    else:
                        raise ValueError("surface extraction orientation does not match inferred check sector")
        schedule = "Stim rotated_memory_z CNOT schedule"
        n, k = distance**2, 1
    elif family == "bb72":
        if distance != 6:
            raise ValueError("bb72 has published distance label 6")
        from qldpc import codes, circuits
        from qldpc.objects import Pauli
        from sympy.abc import x, y
        code = codes.BBCode({x: 6, y: 6}, x**3 + y + y**2, y**3 + x + x**2)
        algebra = validate_bb72(code)
        parts = circuits.get_memory_experiment_parts(code, basis=Pauli.Z, num_rounds=resolved_rounds,
                                                     syndrome_measurement_strategy=circuits.EdgeColoring(strategy="smallest_last"))
        c = (parts.initialization + parts.qec_cycle + parts.readout).flattened()
        data = tuple(parts.qubit_ids.data)
        sectors = {q: sector for sector, qs in (("X", parts.qubit_ids.checks_x), ("Z", parts.qubit_ids.checks_z)) for q in qs}
        supports = {q: {data[i] for i in np.flatnonzero(algebra["H" + sector.lower()][row])}
                    for sector, qs in (("X", parts.qubit_ids.checks_x), ("Z", parts.qubit_ids.checks_z)) for row, q in enumerate(qs)}
        # Check provider bookkeeping against the actual controlled-Pauli gates.
        observed = {q: set() for q in sectors}
        for op in c:
            if op.name in ("CX", "CZ"):
                ts = op.targets_copy()
                for control, target in zip(ts[::2], ts[1::2]):
                    u, v = control.value, target.value
                    if u not in sectors or v not in data or sectors[u] != op.name[-1]:
                        raise ValueError("BB provider bookkeeping and gate sector disagree")
                    observed[u].add(v)
        if observed != supports:
            raise ValueError("BB circuit check supports differ from CSS matrices")
        schedule = "qLDPC EdgeColoring(smallest_last); X subgraph then Z subgraph"
        n, k = 72, 12
    else:
        raise ValueError(f"unsupported family: {family}")
    if c.num_observables != k or len(data) != n or not all(supports.values()):
        raise ValueError("provider dimensions or check supports invalid")
    metadata = {"family": family, "distance": distance, "published_distance": distance,
                "circuit_distance_certified": False, "n": n, "k_Z": k,
                "rounds": resolved_rounds, "round_override": rounds is not None,
                "schedule": schedule, "preparation": "product Z reset",
                "readout": "destructive data Z measurement", "extra_ideal_cycles": 0,
                "physical_extraction_sectors": ["X", "Z"]}
    return CircuitTemplate(c, data, sectors, {q: tuple(sorted(v)) for q, v in supports.items()}, metadata, algebra)
