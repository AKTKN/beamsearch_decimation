from itertools import product
from pathlib import Path
import numpy as np
import pytest
import stim
from qec_bp_benchmark.dem import convert_dem


def test_repeat_separator_xor_and_distinct_logicals():
    dem = stim.DetectorErrorModel.from_file(Path(__file__).parent / "fixtures/correlated.dem")
    problem = convert_dem(dem)
    expected_h = np.array([[1,1,1,0,1,0], [0,0,0,0,0,1], [1,0,0,0,0,0], [0,0,0,0,0,0], [0,0,0,0,0,0]], dtype=np.uint8)
    expected_a = np.array([[1,0,1,0,1,1],[0,1,0,1,0,0]],dtype=np.uint8)
    assert np.array_equal(problem.H.toarray(), expected_h)
    assert np.array_equal(problem.A.toarray(), expected_a)
    assert problem.original_error_to_column == (0,1,2,3,None,4,5)
    assert len(problem.instruction_to_column) == len(list(dem.flattened()))
    assert problem.probabilities.tolist() == [.1,.2,.3,.4,.125,.125]
    for bits in product((0, 1), repeat=6):
        e = np.array(bits,dtype=np.uint8)
        assert np.array_equal(problem.H @ e % 2, expected_h @ e % 2)
        assert np.array_equal(problem.A @ e % 2, expected_a @ e % 2)
        assert problem.reconstruct(e)[4] == 0
    projected = convert_dem(dem, selected_detectors=(2,))
    assert projected.H.shape == (1,6)
    assert np.array_equal(projected.H.toarray(), expected_h[[2]])
    assert np.array_equal(projected.A.toarray(), expected_a)


def test_dem_sampling_is_only_converter_validation():
    # Labeled DEM-only converter check: all samples checked by exact parity,
    # never interpreted as physical-circuit benchmark shots.
    dem = stim.DetectorErrorModel("error(.1) D0 D1 ^ D1 L0\nerror(.2) D0 L1\nerror(.3) L0")
    problem = convert_dem(dem)
    detectors, observables, errors = dem.compile_sampler(seed=8).sample(shots=64, return_errors=True)
    assert np.array_equal((problem.H @ errors.T % 2).T, detectors)
    assert np.array_equal((problem.A @ errors.T % 2).T, observables)


def test_physical_fault_exhaustion():
    circuit = stim.Circuit('R 0 1\nX_ERROR(.1) 0\nX_ERROR(.2) 1\nM 0 1\nDETECTOR rec[-2] rec[-1]\nOBSERVABLE_INCLUDE(0) rec[-2]')
    problem = convert_dem(circuit.detector_error_model(decompose_errors=False))
    # Identify mechanisms by their independently specified physical rate.
    index0 = np.flatnonzero(np.isclose(problem.probabilities,.1))[0]
    index1 = np.flatnonzero(np.isclose(problem.probabilities,.2))[0]
    for b0,b1 in product((0,1),repeat=2):
        e=np.zeros(2,dtype=np.uint8); e[index0]=b0; e[index1]=b1
        faulty=stim.Circuit(f'R 0 1\nX_ERROR({b0}) 0\nX_ERROR({b1}) 1\nM 0 1\nDETECTOR rec[-2] rec[-1]\nOBSERVABLE_INCLUDE(0) rec[-2]')
        d,o=faulty.compile_detector_sampler(seed=1).sample(shots=1,separate_observables=True)
        assert np.array_equal(problem.H@e%2,d[0])
        assert np.array_equal(problem.A@e%2,o[0])


def test_zero_columns_and_bad_priors():
    problem=convert_dem(stim.DetectorErrorModel('error(0) D0 L0\ndetector D1'))
    assert problem.H.shape == (2,0) and problem.A.shape == (1,0)
    assert problem.reconstruct(np.zeros(0,dtype=np.uint8)).tolist() == [0]
    for p in [.50001,1]:
        with pytest.raises(ValueError,match='probabilities'):
            convert_dem(stim.DetectorErrorModel(f'error({p}) D0 L0'))
    with pytest.raises(ValueError):
        convert_dem(stim.DetectorErrorModel('error(.1) D0'),selected_detectors=(0,0))


def test_pinned_converter_audit_confirms_detector_only_merge_is_unsuitable():
    import runpy
    root=Path(__file__).resolve().parents[1]
    reference=runpy.run_path(str(root/'external_lib/stimbposd/src/stimbposd/dem_to_matrices.py'))
    dem=stim.DetectorErrorModel('error(.1) D0 L0\nerror(.2) D0 L1')
    upstream=reference['detector_error_model_to_check_matrices'](dem)
    ours=convert_dem(dem)
    assert upstream.check_matrix.shape==(1,1)
    assert ours.H.shape==(1,2)
    assert np.array_equal(ours.A.toarray(),np.eye(2,dtype=np.uint8))
