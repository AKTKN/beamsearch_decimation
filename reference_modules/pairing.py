"""Phase-2A validated measurement-parity mapping, reused without resampling."""
import stim

def _measurement_relations(circuit: stim.Circuit):
    """Canonical absolute record parities; include measurement location timing."""
    measurement_count = 0
    operations, detectors, observables = [], [], {}
    for instruction in circuit.flattened():
        if instruction.name in ('DETECTOR','OBSERVABLE_INCLUDE'):
            parity = set()
            for target in instruction.targets_copy():
                if not target.is_measurement_record_target:
                    raise ValueError('Only record-parity annotations are supported')
                index = measurement_count + target.value
                parity.symmetric_difference_update((index,))
            if instruction.name == 'DETECTOR':
                detectors.append(frozenset(parity))
            else:
                obs = int(instruction.gate_args_copy()[0])
                observables.setdefault(obs,set()).symmetric_difference_update(parity)
        else:
            operations.append(str(instruction))
            one = stim.Circuit()
            one.append(instruction)
            measurement_count += one.num_measurements
    return operations,detectors,{k:frozenset(v) for k,v in observables.items()}


def validate_pairing(ordinary: stim.Circuit, comparative: stim.Circuit) -> dict:
    """Check identical operations and the comparative observable-parity extension.

    Args:
        ordinary: Ordinary one-observable memory circuit.
        comparative: Circuit with one additional forced-class detector.
    Returns:
        Auditable mapping description.
    Raises:
        ValueError: Physical records, detector prefix, or observable parity differ.
    """
    ops_a,dets_a,obs_a = _measurement_relations(ordinary)
    ops_b,dets_b,obs_b = _measurement_relations(comparative)
    if ops_a != ops_b or obs_a != obs_b or dets_b[:len(dets_a)] != dets_a:
        raise ValueError('Circuits do not share the same physical record and detector prefix')
    if ordinary.num_observables != 1 or len(dets_b) != len(dets_a)+1 or dets_b[-1] != obs_a[0]:
        raise ValueError('Comparative extra detector is not exactly the ordinary observable parity')
    return {'physical_operations_equal':True,'detector_prefix_equal':True,
            'extra_detector':'ordinary observable 0','ordinary_detectors':len(dets_a),
            'comparative_detectors':len(dets_b)}


