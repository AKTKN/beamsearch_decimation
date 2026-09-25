"""Truth-free Relay adapter checks against the pinned upstream F64 API."""
import numpy as np
import pytest
import stim

from qec_bp_benchmark.circuits import apply_noise, make_template, select_z_detectors
from qec_bp_benchmark.config import Bposd, Beam, Multipliers, RelayBP
from qec_bp_benchmark.decoders import DecoderAdapter
from qec_bp_benchmark.dem.model import convert_dem


def tiny_problem():
    return convert_dem(stim.DetectorErrorModel(
        'error(0.1) D0 D1 L0\nerror(0.2) D0\nerror(0.15) D1'))


def test_relay_receives_same_h_and_probabilities_and_validates_correction():
    from relay_bp import RelayDecoderF64

    problem = tiny_problem()
    settings = RelayBP(pre_iter=2, num_sets=2, set_max_iter=2,
                       stop_nconv=3, seed=4)
    adapter = DecoderAdapter(problem, settings)
    direct = RelayDecoderF64(problem.H.copy(), problem.probabilities.copy(),
                             **settings.model_dump(exclude={'profile', 'kind', 'name', 'enabled'}),
                             stopping_criterion='nconv', logging=False)
    for syndrome in (np.array([0, 0], dtype=np.uint8),
                     np.array([1, 0], dtype=np.uint8),
                     np.array([1, 1], dtype=np.uint8)):
        result = adapter.decode(syndrome)
        expected = direct.decode_detailed(syndrome)
        assert result.total_iterations == expected.iterations
        assert result.declared_failure == (not expected.success)
        assert result.status == 'SUCCESS'
        assert np.array_equal(result.correction, expected.decoding)
        assert np.array_equal(problem.H @ result.correction % 2, syndrome)
        assert np.array_equal(result.prediction, problem.A @ result.correction % 2)
        assert result.osd_called is False


def test_relay_counts_initial_and_every_executed_leg():
    problem = convert_dem(stim.DetectorErrorModel('error(0.1) D0 D1 L0'))
    settings = RelayBP(pre_iter=2, num_sets=3, set_max_iter=4, seed=7)
    adapter = DecoderAdapter(problem, settings)
    syndrome = np.array([1, 0], dtype=np.uint8)  # Outside column space: no leg can converge.
    detailed = adapter._native.decode_detailed(syndrome)
    assert detailed.success is False
    assert detailed.max_iter == 2  # Retained initial leg, not the total work.
    assert detailed.iterations == 2 + 3 * 4 == 14
    result = adapter.decode(syndrome)
    assert result.declared_failure and result.correction is None
    assert result.total_iterations == detailed.iterations


def test_relay_adapter_rejects_upstream_success_without_original_h_match():
    adapter = DecoderAdapter(tiny_problem(), RelayBP(pre_iter=1, num_sets=0))

    class Incorrect:
        def decode_detailed(self, syndrome):
            class Result:
                success = True
                iterations = 1
                decoding = np.zeros(3, dtype=np.uint8)
            return Result()

    adapter._native = Incorrect()
    result = adapter.decode(np.array([1, 0], dtype=np.uint8))
    assert result.status == 'INVALID_OUTPUT'
    assert not result.syndrome_valid and result.correction is None
    assert result.total_iterations == 1


def test_relay_seed_repeats_complete_shot_sequence_without_truth():
    problem = tiny_problem()
    settings = RelayBP(pre_iter=1, num_sets=3, set_max_iter=2,
                       stop_nconv=3, seed=321)
    sequence = (np.array([1, 0], dtype=np.uint8), np.array([0, 1], dtype=np.uint8))
    first = DecoderAdapter(problem, settings)
    second = DecoderAdapter(problem, settings)
    for syndrome in sequence:
        one, two = first.decode(syndrome), second.decode(syndrome)
        assert one.status == two.status
        assert one.total_iterations == two.total_iterations
        assert np.array_equal(one.correction, two.correction)
    with pytest.raises(TypeError):
        first.decode(sequence[0], truth=np.zeros(1, dtype=np.uint8))


def test_relay_bb144_construction_and_one_syndrome_smoke():
    template = make_template('bb144', 12, rounds=1)
    eligible = tuple(sorted((*template.data_qubits, *template.check_sectors)))
    circuit = apply_noise(template.circuit, .001, Multipliers(), eligible)
    view = select_z_detectors(circuit, template)
    problem = convert_dem(view.circuit.detector_error_model(decompose_errors=False,
                                                            approximate_disjoint_errors=False))
    settings = RelayBP(pre_iter=1, num_sets=1, set_max_iter=1, seed=9)
    relay = DecoderAdapter(problem, settings)
    assert problem.A.shape[0] == 12 and problem.H.shape[0] == 144
    syndrome = np.asarray(problem.H[:, 0].toarray().ravel(), dtype=np.uint8)
    result = relay.decode(syndrome)
    assert 1 <= result.total_iterations <= 2
    assert result.status in ('SUCCESS', 'DECLARED_FAILURE')
    if result.correction is not None:
        assert np.array_equal(problem.H @ result.correction % 2, syndrome)
        assert result.prediction.shape == (12,)


def test_bposd_count_is_bp_stage_only_and_beam_result_has_total():
    problem = tiny_problem()
    syndrome = np.array([1, 0], dtype=np.uint8)
    bposd = DecoderAdapter(problem, Bposd(max_iter=30, osd_order=0))
    result = bposd.decode(syndrome)
    assert result.total_iterations == bposd._native.iter == 1 < 30
    assert bposd.decode(np.zeros(2, dtype=np.uint8)).total_iterations == 0
    beam = DecoderAdapter(problem, Beam(initial_iters=2, iters_per_round=2,
                                       max_rounds=2))
    assert beam.decode(syndrome).total_iterations == beam._native.total_iterations
