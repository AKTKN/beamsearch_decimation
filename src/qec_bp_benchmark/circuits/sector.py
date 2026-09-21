"""Detector sector selection from absolute measurement-record provenance."""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
import stim
from .providers import CircuitTemplate


@dataclass(frozen=True)
class DetectorView:
    """Selected circuit, full-to-selected map (-1 excludes), and parity provenance."""
    circuit: stim.Circuit
    full_to_selected: tuple[int, ...]
    selected_to_full: tuple[int, ...]
    detectors: tuple[dict, ...]
    observables: tuple[dict, ...]


def select_z_detectors(circuit: stim.Circuit, template: CircuitTemplate) -> DetectorView:
    """Preserve physical operations and logical annotations; select verified Z checks.

    Args:
        circuit: Full physical circuit, noisy or noiseless, with template record order.
        template: Provider check sectors/supports and round count.
    Returns:
        Owned flattened circuit and maps. Neither argument is mutated.
    Raises:
        ValueError: Unrecognized measurements, mixed check sectors or bad boundary parity.
    """
    records, detectors, obs = [], [], {}
    seen = Counter()
    out = stim.Circuit()
    full_to_selected, selected_to_full = [], []
    for op in circuit.flattened():
        if op.name in ("M", "MX", "MY", "MR", "MRX", "MRY"):
            for target in op.targets_copy():
                q = target.value
                seen[q] += 1
                sector = template.check_sectors.get(q, "data")
                if sector == "data" and (q not in template.data_qubits or op.name != "M"):
                    raise ValueError("unrecognized physical measurement")
                records.append({"qubit": q, "sector": sector, "round": seen[q]})
        elif stim.gate_data(op.name).produces_measurements:
            raise ValueError("unsupported measurement operation in provider")
        if op.name in ("DETECTOR", "OBSERVABLE_INCLUDE"):
            parity = set()
            for target in op.targets_copy():
                if not target.is_measurement_record_target:
                    raise ValueError("annotations must use measurement records")
                index = len(records) + target.value
                if index < 0 or index >= len(records):
                    raise ValueError("record offset out of bounds")
                parity.symmetric_difference_update((index,))
            if op.name == "OBSERVABLE_INCLUDE":
                label = int(op.gate_args_copy()[0])
                obs.setdefault(label, set()).symmetric_difference_update(parity)
            else:
                rs = [records[i] for i in sorted(parity)]
                checks = [r for r in rs if r["sector"] != "data"]
                sectors = {r["sector"] for r in checks}
                if len(sectors) != 1 or len({r["qubit"] for r in checks}) != 1:
                    raise ValueError("detector is not a parity of one verified check")
                sector = next(iter(sectors))
                q = checks[0]["qubit"]
                data_support = {r["qubit"] for r in rs if r["sector"] == "data"}
                if data_support:
                    if sector != "Z" or len(checks) != 1 or data_support != set(template.check_supports[q]):
                        raise ValueError("invalid destructive-readout detector support")
                    role = "final"
                    if checks[0]["round"] != template.metadata["rounds"]:
                        raise ValueError("final detector does not close the requested last round")
                elif len(checks) == 1 and checks[0]["round"] == 1:
                    role = "initial"
                elif len(checks) == 2 and abs(checks[0]["round"] - checks[1]["round"]) == 1:
                    role = "bulk"
                else:
                    raise ValueError("invalid extraction detector time relation")
                full_id = len(detectors)
                selected_id = len(selected_to_full) if sector == "Z" else -1
                full_to_selected.append(selected_id)
                if selected_id >= 0:
                    selected_to_full.append(full_id)
                detectors.append({"full_id": full_id, "selected_id": selected_id, "sector": sector,
                                  "role": role, "check_qubit": q, "round": max(r["round"] for r in checks),
                                  "measurement_indices": sorted(parity)})
                if sector != "Z":
                    continue
        out.append(op)
    for q in template.check_sectors:
        if seen[q] != template.metadata["rounds"]:
            raise ValueError("physical extraction count does not equal requested rounds")
    if set(obs) != set(range(template.metadata["k_Z"])):
        raise ValueError("logical observable labels missing")
    observables = []
    for label, parity in sorted(obs.items()):
        if any(records[i]["sector"] != "data" for i in parity):
            raise ValueError("logical Z must refer to final data readout")
        support = sorted(records[i]["qubit"] for i in parity)
        if template.algebra:
            expected = [template.data_qubits[i] for i, bit in enumerate(template.algebra["Lz"][label]) if bit]
            if support != expected:
                raise ValueError("observable annotation differs from validated logical basis")
        observables.append({"id": label, "basis": "Z", "data_support": support,
                            "measurement_indices": sorted(parity)})
    return DetectorView(out, tuple(full_to_selected), tuple(selected_to_full), tuple(detectors), tuple(observables))
