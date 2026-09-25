"""Small physical-circuit-to-native-BP integration, without a benchmark runner."""
import numpy as np
import pytest
from qec_bp_benchmark.bp import FloodingBP
from qec_bp_benchmark.circuits import make_template, apply_noise, select_z_detectors
from qec_bp_benchmark.config import Multipliers
from qec_bp_benchmark.dem import convert_dem


@pytest.mark.parametrize('family,distance',[('surface',5),('bb72',6)])
def test_canonical_mechanism_priors_and_native_boundary(family,distance):
    template=make_template(family,distance)
    circuit=apply_noise(template.circuit,.001,Multipliers(),tuple(sorted((*template.data_qubits,*template.check_sectors))))
    view=select_z_detectors(circuit,template)
    problem=convert_dem(view.circuit.detector_error_model(decompose_errors=False,approximate_disjoint_errors=False))
    full,truth=circuit.compile_detector_sampler(seed=404).sample(shots=4,separate_observables=True)
    assert truth.shape==(4,template.metadata['k_Z'])
    decoder=FloodingBP(problem.H,problem.probabilities)
    for syndrome in full[:,view.selected_to_full]:
        result=decoder.decode(syndrome,max_iterations=3)
        assert result.last_decision.shape==(problem.H.shape[1],)
        if result.correction is not None:
            assert np.array_equal(problem.H@result.correction%2,syndrome)
            assert (problem.A@result.correction%2).shape==(template.metadata['k_Z'],)
        else:
            assert result.status=='NONCONVERGENCE'
