"""Bounded physical sampling through the Stage 3 service, without Stage 4 storage."""
import numpy as np
import pytest
from qec_bp_benchmark.circuits import make_template, apply_noise, select_z_detectors
from qec_bp_benchmark.config import Hybrid, Multipliers, HYBRID_PROFILES
from qec_bp_benchmark.decoders import DecoderAdapter
from qec_bp_benchmark.dem import convert_dem


@pytest.mark.parametrize('family,distance',[('surface',3),('bb72',6)])
def test_physical_shots_and_all_observables(family,distance):
    template=make_template(family,distance)
    circuit=apply_noise(template.circuit,.001,Multipliers(),tuple(sorted((*template.data_qubits,*template.check_sectors))))
    view=select_z_detectors(circuit,template)
    problem=convert_dem(view.circuit.detector_error_model(decompose_errors=False,approximate_disjoint_errors=False))
    full,truth=circuit.compile_detector_sampler(seed=430).sample(shots=4,separate_observables=True)
    assert truth.shape==(4,12 if family=='bb72' else 1)
    for profile in HYBRID_PROFILES:
        decoder=DecoderAdapter(problem,Hybrid(profile=profile),profiling=True)
        for syndrome in full[:,view.selected_to_full]:
            result=decoder.decode(syndrome)
            assert result.status=='SUCCESS' and result.syndrome_valid
            assert np.array_equal(problem.H@result.correction%2,syndrome)
            assert np.array_equal(result.prediction,problem.A@result.correction%2)
            assert len(result.prediction)==truth.shape[1]
            events=decoder.export_telemetry()
            assert len(events['rounds'])==result.hybrid_summary['cycles_started']
