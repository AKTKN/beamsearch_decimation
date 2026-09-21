import itertools
import numpy as np
import stim
import pytest
from qec_bp_benchmark.config import Bposd,Beam,Screened
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


@pytest.mark.parametrize('cfg',[Bposd(max_iter=2,osd_order=2),Beam(initial_iters=2,iters_per_round=3,max_rounds=2),Screened(T0=2,Tpost=3,M=4,q=2,K=4)])
def test_adapters_native_and_shot_reset(cfg):
    p=problem(); a=DecoderAdapter(p,cfg)
    snapshots=[x.copy() for x in (p.H.data,p.A.data,p.probabilities)]
    if isinstance(cfg,Bposd):
        from ldpc import BpOsdDecoder as Native
    elif isinstance(cfg,Beam):
        from beam_search_decoder import BeamSearchDecoder as Native
    else: Native=None
    direct=Native(p.H.copy(),error_channel=p.probabilities.tolist(),**cfg.model_dump(exclude={'profile','name','enabled'})) if Native else None
    baseline={}
    for s in itertools.product((0,1),repeat=4):
        s=np.array(s,dtype=np.uint8); original=s.copy(); r=a.decode(s)
        assert np.array_equal(s,original)
        fresh=DecoderAdapter(p,cfg).decode(s)
        assert r.status==fresh.status and r.counters==fresh.counters
        assert np.array_equal(r.correction,fresh.correction)
        if direct:
            e=direct.decode(s.copy()); valid=np.array_equal(p.H@e%2,s)
            ok=valid and (isinstance(cfg,Bposd) or direct.converge)
            assert (r.status=='SUCCESS')==ok
            if ok: assert np.array_equal(r.correction,e)
        if r.correction is not None:
            assert np.array_equal(p.H@r.correction%2,s)
            assert np.array_equal(r.prediction,p.A@r.correction%2)
        else: assert r.prediction is None and r.cost is None
        baseline[tuple(s)]=r
    for s,r in reversed(list(baseline.items())):
        reused=a.decode(np.array(s,dtype=np.uint8))
        assert reused.status==r.status and reused.counters==r.counters
        assert np.array_equal(reused.correction,r.correction)
    for original,now in zip(snapshots,(p.H.data,p.A.data,p.probabilities)): assert np.array_equal(original,now)


def test_osd_valid_despite_bp_failure_and_empty_model():
    p=convert_dem(stim.DetectorErrorModel('error(0.1) D0 L0\nerror(0.1) D0'))
    r=DecoderAdapter(p,Bposd(max_iter=1,osd_order=1)).decode(np.array([1]))
    assert r.status=='SUCCESS' and r.native_status=='OSD_AFTER_BP_NONCONVERGENCE'
    empty=convert_dem(stim.DetectorErrorModel('detector D0\nlogical_observable L11'))
    for cfg in [Screened(),Bposd(),Beam()]:
        d=DecoderAdapter(empty,cfg)
        r=d.decode(np.array([0])); assert r.prediction.tolist()==[0]*12
        r=d.decode(np.array([1])); assert r.status=='DECLARED_FAILURE' and r.cost is None


def test_no_truth_api_and_failure_handling():
    a=DecoderAdapter(problem(),Beam())
    with pytest.raises(TypeError): a.decode(np.zeros(4),truth=np.zeros(2))
    class Exhausted:
        converge=False
        def decode(self,s): return np.zeros(8,dtype=np.uint8)
    a._native=Exhausted()
    r=a.decode(np.zeros(4)); assert r.syndrome_valid and r.status=='DECLARED_FAILURE' and r.prediction is None
    class Exploding:
        def decode(self,s): raise RuntimeError('backend fault')
    a._native=Exploding()
    with pytest.raises(RuntimeError,match='backend fault'): a.decode(np.zeros(4))
