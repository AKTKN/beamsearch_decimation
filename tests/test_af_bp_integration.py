"""Active AF-BP adapter and native configuration mapping."""
import numpy as np
import pytest
import stim

from qec_bp_benchmark.af_bp_service import AFBPConfig, AFBPDecoder, FailureOptions
from qec_bp_benchmark.config import AFBP
from qec_bp_benchmark.decoders import DecoderAdapter, implementation_identity
from qec_bp_benchmark.dem.model import convert_dem


def _problem():
    return convert_dem(stim.DetectorErrorModel(
        'error(0.1) D0 D1 L0\nerror(0.2) D0\nerror(0.15) D1'))


def test_af_bp_active_mapping_and_truth_free_decision():
    problem = _problem()
    config = AFBP(initial_parallel=False, initial_iteration_budget=2,
                  transformed_iteration_budget=2, bp_variant='serial',
                  serial_order='natural', ms_scaling_factor=.8,
                  history_window=3, graph_rounds=1, n_fact=1,
                  factorization_policy='shen_cycle_count',
                  residual_radius=1, distance_decay=.3,
                  uncertainty_weight=2, oscillation_weight=1,
                  U_selection='threshold', U_top_k=2, U_threshold=.1,
                  seed=9, seed_policy='fixed')
    adapter = DecoderAdapter(problem, config)
    mapped = adapter._native.config
    assert mapped == AFBPConfig(
        initial_parallel=False, initial_iteration_budget=2,
        transformed_iteration_budget=2, bp_variant='serial',
        serial_order='natural', scaling_factor=.8,
        history_window=3, graph_rounds=1, n_fact=1,
        factorization_policy='shen_cycle_count',
        failure=FailureOptions(residual_radius=1, distance_decay=.3,
                               uncertainty_weight=2, oscillation_weight=1,
                               selection='threshold', top_k=2, threshold=.1),
        seed=9, seed_policy='fixed')
    syndrome = np.array([1, 0], dtype=np.uint8)
    direct = AFBPDecoder(problem.H, problem.A, problem.probabilities, mapped)
    expected = direct.decode(syndrome)
    result = adapter.decode(syndrome)
    assert result.total_iterations == expected.total_iterations
    assert result.declared_failure == (not expected.valid)
    assert result.native_status == expected.status
    assert result.status == ('SUCCESS' if expected.valid else 'DECLARED_FAILURE')
    if expected.valid:
        np.testing.assert_array_equal(result.correction, expected.correction)
        np.testing.assert_array_equal(problem.H @ result.correction % 2, syndrome)
        np.testing.assert_array_equal(result.prediction, problem.A @ result.correction % 2)
    with pytest.raises(TypeError):
        adapter.decode(syndrome, truth=np.zeros(1, dtype=np.uint8))
    assert implementation_identity('af_bp')['algorithm_version'] == 'AF-BP-1.0'


def test_af_bp_declared_failure_keeps_exact_spent_iterations():
    problem = convert_dem(stim.DetectorErrorModel('error(0.1) D0 D1 L0'))
    adapter = DecoderAdapter(problem, AFBP(initial_iteration_budget=2,
        transformed_iteration_budget=0, graph_rounds=0, n_fact=0))
    result = adapter.decode(np.array([1, 0], dtype=np.uint8))
    assert result.declared_failure and result.correction is None
    assert result.total_iterations == 2


def test_af_bp_qdither_fields_reach_native_service():
    problem = _problem()
    config = AFBP(bp_variant='qdither', initial_parallel=False,
                  initial_iteration_budget=2, transformed_iteration_budget=2,
                  graph_rounds=1, n_fact=1, qdither_phase1_iterations=1,
                  qdither_chains=1, qdither_iterations_per_chain=1,
                  qdither_alpha=.1, qdither_beta=.4, qdither_rho=.2,
                  qdither_handoff='graph_warm', atanh_epsilon=1e-10)
    adapter = DecoderAdapter(problem, config)
    mapped = adapter._native.config
    assert (mapped.phase1_iterations, mapped.num_chains, mapped.chain_iterations,
            mapped.alpha, mapped.beta, mapped.rho, mapped.qdither_handoff,
            mapped.atanh_epsilon) == (1, 1, 1, .1, .4, .2, 'graph_warm', 1e-10)
    result = adapter.decode(np.array([1, 0], dtype=np.uint8))
    assert 0 <= result.total_iterations <= 4
