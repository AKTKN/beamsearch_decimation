import itertools
import numpy as np
import stim
import pytest
from qec_bp_benchmark.config import Bposd, Beam
from qec_bp_benchmark.dem.model import convert_dem
from qec_bp_benchmark.decoders import DecoderAdapter


def problem():
    return convert_dem(stim.DetectorErrorModel('''error(0.1) D0 D1 D2 L0
error(0.13) D0 D1 D3
error(0.2) D0 D2 D3 L1
error(0.18) D1 D2 D3
error(0.1) D0
error(0.11) D1
error(0.12) D2
error(0.13) D3'''))


@pytest.mark.parametrize('cfg', [Bposd(max_iter=2, osd_order=0),
    Bposd(max_iter=2, osd_order=2), Beam(initial_iters=2, iters_per_round=3, max_rounds=2)])
def test_upstream_baseline_decisions_and_shot_reset(cfg):
    p = problem()
    adapter = DecoderAdapter(p, cfg)
    snapshots = [x.copy() for x in (p.H.data, p.A.data, p.probabilities)]
    if isinstance(cfg, Bposd):
        from ldpc import BpOsdDecoder as Native
    else:
        from beam_search_decoder import BeamSearchDecoder as Native
    direct = Native(p.H.copy(), error_channel=p.probabilities.tolist(),
                    **cfg.model_dump(exclude={'profile', 'name', 'enabled'}))
    baseline = {}
    for value in itertools.product((0, 1), repeat=4):
        syndrome = np.array(value, dtype=np.uint8)
        result = adapter.decode(syndrome)
        fresh = DecoderAdapter(p, cfg).decode(syndrome)
        assert result.status == fresh.status and result.counters == fresh.counters
        assert np.array_equal(result.correction, fresh.correction)
        expected = direct.decode(syndrome.copy())
        valid = np.array_equal(p.H @ expected % 2, syndrome)
        success = valid and (isinstance(cfg, Bposd) or direct.converge)
        assert (result.status == 'SUCCESS') == success
        if success:
            assert np.array_equal(result.correction, expected)
            assert np.array_equal(result.prediction, p.A @ result.correction % 2)
        baseline[value] = result
    for value, result in reversed(list(baseline.items())):
        repeated = adapter.decode(np.array(value, dtype=np.uint8))
        assert repeated.status == result.status
        assert np.array_equal(repeated.correction, result.correction)
    for before, after in zip(snapshots, (p.H.data, p.A.data, p.probabilities)):
        assert np.array_equal(before, after)


@pytest.mark.parametrize('order', [0, 1, 10])
def test_osd_after_bp_failure_and_empty_model(order):
    p = convert_dem(stim.DetectorErrorModel('error(0.1) D0 L0\nerror(0.1) D0'))
    adapter = DecoderAdapter(p, Bposd(max_iter=1, osd_order=order))
    result = adapter.decode(np.array([1], dtype=np.uint8))
    assert result.status == 'SUCCESS'
    assert result.native_status == 'OSD_AFTER_BP_NONCONVERGENCE'
    assert result.osd_called is True
    assert result.total_iterations == adapter._native.iter == 1
    assert adapter.decode(np.array([0], dtype=np.uint8)).osd_called is False
    empty = convert_dem(stim.DetectorErrorModel('detector D0\nlogical_observable L11'))
    for cfg in (Bposd(osd_order=order), Beam()):
        decoder = DecoderAdapter(empty, cfg)
        assert decoder.decode(np.array([0], dtype=np.uint8)).prediction.tolist() == [0] * 12
        assert decoder.decode(np.array([1], dtype=np.uint8)).status == 'DECLARED_FAILURE'


@pytest.mark.parametrize('cfg', [Beam(), Bposd(),])
def test_no_truth_api_and_error_propagation(cfg):
    adapter = DecoderAdapter(problem(), cfg)
    with pytest.raises(TypeError):
        adapter.decode(np.zeros(4), truth=np.zeros(2))
    class Exploding:
        def decode(self, syndrome):
            raise RuntimeError('backend fault')
    adapter._native = Exploding()
    with pytest.raises(RuntimeError, match='backend fault'):
        adapter.decode(np.zeros(4))
