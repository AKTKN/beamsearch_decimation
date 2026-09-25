from concurrent.futures import ThreadPoolExecutor
import itertools
import math
from pathlib import Path
import numpy as np
import pytest
from scipy import sparse
from ldpc import reference_bp
from qec_bp_benchmark.bp import FloodingBP, verified_backend
from bp_oracle import scalar_bp


def compare(H,p,s,*,T=5,limit=25,window=3,fixed=None):
    native=FloodingBP(H,p).decode(s,max_iterations=T,llr_max=limit,history_window=window,fixed=fixed,diagnostics=True)
    oracle=scalar_bp(H,p,s,T=T,limit=limit,window=window,fixed=fixed)
    assert native.status==oracle['status']
    assert native.iterations==oracle['iterations']
    assert np.array_equal(native.last_decision,oracle['last_decision'])
    assert np.array_equal(native.free_ids,oracle['free_ids'])
    np.testing.assert_allclose(native.beliefs,oracle['beliefs'],rtol=1e-12,atol=1e-12)
    np.testing.assert_allclose(native.history,np.asarray(oracle['history']).reshape(native.history.shape),rtol=1e-12,atol=1e-12)
    assert len(native.trace)==len(oracle['trace'])
    for got,expected in zip(native.trace,oracle['trace']):
        for value,target in zip((got.beliefs,got.variable_to_check,got.check_to_variable,got.decision),expected):
            np.testing.assert_allclose(value,target,rtol=1e-12,atol=1e-12)
    if native.correction is not None:
        assert np.array_equal(np.asarray(H)@native.correction%2,s)
    if len(native.history):
        np.testing.assert_allclose(native.mean_llr,native.history.mean(axis=0),atol=1e-12)
        np.testing.assert_allclose(native.reliability,np.abs(native.history.mean(axis=0)),atol=1e-12)
        assert np.array_equal(native.flips,np.count_nonzero(np.diff(native.history<0,axis=0),axis=0))
    return native


def test_iteration_zero_and_degree_one():
    prior=1/(1+math.exp(1))
    zero=compare([[1]],[prior],[0])
    assert zero.iterations==0 and zero.history.shape==(0,1)
    odd=compare([[1]],[prior],[1])
    assert odd.iterations==1 and odd.beliefs.tolist()==[-24]
    assert odd.trace[1].check_to_variable==[-25]


def test_degree_zero_isolated_zero_messages_saturation():
    assert compare([[0,0]],[.1,.5],[1]).status=='LOCAL_CONTRADICTION'
    compare([[1,1,0],[0,1,0]],[.5,.5,.1],[1,0])
    saturated=compare([[1]],[1e-100],[1],limit=25)
    assert saturated.status=='NONCONVERGENCE' and saturated.beliefs.tolist()==[0]
    assert saturated.last_decision.tolist()==[0]
    # Opposite degree-one constraints yield clipped posteriors; trace checks
    # explicit extrinsic accumulation rather than subtracting a clipped posterior.
    compare([[1,0],[1,0],[1,1]],[1e-90,.1],[0,0,1],limit=2)


@pytest.mark.parametrize('window',[0,1,2,5,12])
def test_history_endpoints(window):
    result=compare([[1,1],[1,1]],[.5,.5],[1,0],T=5,window=window)
    assert result.iterations==5 and result.history.shape==(min(window,5),2)
    if window:
        assert result.flips.tolist()==[0,0]


def test_fixed_bits_structural_and_cold_starts():
    H=np.array([[1,1],[1,0]],dtype=np.uint8)
    decoder=FloodingBP(H,[.1,.2])
    results=[]
    for fixed in ([0,-1],[1,-1],[-1,0],[-1,1],[0,0],[1,1]):
        r=compare(H,[.1,.2],[1,0],fixed=fixed)
        results.append(decoder.decode([1,0],fixed=fixed,diagnostics=True))
        assert r.history.shape[1]==sum(x<0 for x in fixed)
    for index in reversed(range(len(results))):
        fixed=([0,-1],[1,-1],[-1,0],[-1,1],[0,0],[1,1])[index]
        r=decoder.decode([1,0],fixed=fixed,diagnostics=True)
        assert r.status==results[index].status
        assert np.array_equal(r.last_decision,results[index].last_decision)
    assert results[0].correction.tolist()==[0,1]
    assert results[1].status=='LOCAL_CONTRADICTION'


def test_random_complete_traces_and_simultaneous_updates():
    rng=np.random.default_rng(100)
    for _ in range(100):
        H=(rng.random((4,6))<.4).astype(np.uint8)
        p=rng.choice([.5,.25,.1,1e-15],size=6)
        s=rng.integers(0,2,size=4)
        fixed=rng.choice([-1,-1,-1,0,1],size=6)
        compare(H,p,s,limit=float(rng.choice([1,5,25,30])),fixed=fixed)
    # A cycle with asymmetric priors exercises propagation beyond one half-step.
    r=compare([[1,1,0],[0,1,1],[1,0,1]],[.12,.2,.3],[1,1,1],T=6)
    assert r.iterations==6


def test_ownership_reuse_concurrency_and_empty_graph():
    H=np.array([[1,1,0],[0,1,1]],dtype=np.uint8)
    p=np.array([.1,.2,.3]); decoder=FloodingBP(H,p)
    H[:]=0; p[:]=.5
    syndromes=[np.array(x) for x in itertools.product([0,1],repeat=2)]*3
    serial=[decoder.decode(s) for s in syndromes]
    with ThreadPoolExecutor(2) as pool:
        parallel=list(pool.map(decoder.decode,syndromes))
    for a,b in zip(serial,parallel):
        assert a.status==b.status and np.array_equal(a.last_decision,b.last_decision)
    empty=FloodingBP(np.zeros((2,0),dtype=np.uint8),[])
    assert empty.decode([0,0]).status=='CONVERGED'
    assert empty.decode([0,1]).status=='LOCAL_CONTRADICTION'


@pytest.mark.parametrize('H,p', [([[2]],[.1]),([[.5]],[.1]),([[1]],[0]),([[1]],[.51]),([[1]],[float('nan')]),([[1]],[]),([[1]],[[.1]])])
def test_bad_constructor(H,p):
    with pytest.raises(ValueError): FloodingBP(H,p)


def test_bad_native_and_decode_boundaries():
    with pytest.raises(ValueError): reference_bp.ReferenceBp([[1,1]],2,[.1,.1])
    with pytest.raises(ValueError): reference_bp.ReferenceBp([[2]],2,[.1,.1])
    with pytest.raises(ValueError): reference_bp.ReferenceBp([[1,0]],2,[.1,.1])
    duplicate=sparse.csr_matrix(([1,1],[0,0],[0,2]),shape=(1,1))
    with pytest.raises(ValueError): FloodingBP(duplicate,[.1])
    decoder=FloodingBP([[1]],[.1])
    for s,kwargs in [([2],{}),([] ,{}),([1],{'fixed':[.5]}),([1],{'fixed':[]}),
                     ([1],{'llr_max':31}),([1],{'llr_max':float('nan')}),([1],{'max_iterations':0}),
                     ([1],{'max_iterations':1.5}),([1],{'history_window':-1})]:
        with pytest.raises(ValueError): decoder.decode(s,**kwargs)


def test_build_identity():
    assert verified_backend().build_identity()['profile']=='screened_reference_flooding_v1'
    assert 'external_lib/ldpc' in str(Path(reference_bp.__file__).resolve())


def test_specification_worked_residual_completions():
    H=np.array([[1,1,1,0,0],[0,1,1,1,0],[1,0,0,1,1]],dtype=np.uint8)
    p=[1/(1+math.exp(1))]*5
    for b1,expected in [(0,[1,0,0,0,1]),(1,[1,1,1,0,1])]:
        result=compare(H,p,[1,0,0],T=30,fixed=[-1,b1,-1,0,-1])
        assert result.correction.tolist()==expected


def test_clipped_posterior_is_not_used_for_extrinsic():
    r=FloodingBP([[1,0],[1,0],[1,1]],[1e-90,.1]).decode([0,0,1],llr_max=2,diagnostics=True)
    first=r.trace[1]
    assert first.beliefs[0]==2
    assert first.check_to_variable[0]==2
    assert first.variable_to_check[0] > 1.99
    assert first.variable_to_check[0] != first.beliefs[0]-first.check_to_variable[0]


def test_stale_native_identity_is_rejected(monkeypatch):
    original=reference_bp.build_identity()
    monkeypatch.setattr(reference_bp,'build_identity',lambda:{**original,'source_sha256':'stale'})
    verified_backend.cache_clear()
    try:
        with pytest.raises(RuntimeError,match='identity mismatch'):
            verified_backend()
    finally:
        verified_backend.cache_clear()
