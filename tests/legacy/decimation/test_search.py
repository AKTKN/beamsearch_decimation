import itertools
import math
import numpy as np
import pytest
from qec_bp_benchmark.config import Screened
from qec_bp_benchmark.decoders import native_search
from qec_bp_benchmark.bp import FloodingBP
from search_oracle import patterns, search


def native(H,p,cfg):
    m=native_search(); c=m.Settings()
    for key,v in dict(T0=cfg.T0,Tpost=cfg.Tpost,window=cfg.history_window,M=cfg.M,q=cfg.q,K=cfg.K,limit=cfg.Lmax).items(): setattr(c,key,v)
    return m.ScreenedDecoder([np.flatnonzero(row).tolist() for row in H],len(p),list(p),c)


def test_worked_example():
    H=np.array([[1,1,1,0,0],[0,1,1,1,0],[1,0,0,1,1]],dtype=np.uint8)
    p=[1/(1+math.exp(1))]*5; s=[1,0,0]; r=[2,0,3,0,4]; flips=[0,3,0,3,0]
    d=native(H,p,Screened(M=2,q=2,K=2))
    out=d.screen(s,r,flips)
    assert out.pool==[1,3] and out.enumerated==4
    scores=[d.score(s,r,[1,b,3,c]).f for b,c in itertools.product((0,1),repeat=2)]
    assert scores==pytest.approx([1,2.5,2,3])
    assert [x.id for x in out.retained]==[[1,0,3,0],[1,1,3,0]]
    bp=FloodingBP(H,np.array(p))
    expected=[[1,0,0,0,1],[1,1,1,0,1]]
    for pattern,e in zip(out.retained,expected):
        fixed=np.full(5,-1); fixed[pattern.id[::2]]=pattern.id[1::2]
        result=bp.decode(np.array(s),fixed=fixed)
        assert result.correction.tolist()==e
        assert d.cost(e)==pytest.approx(sum(e))


def test_exact_screening_lower_bounds_and_ties():
    rng=np.random.default_rng(18)
    for _ in range(35):
        H=rng.integers(0,2,(3,5),dtype=np.uint8); p=rng.choice([.1,.2,.5],5).tolist()
        s=rng.integers(0,2,3).tolist(); r=rng.integers(0,3,5).astype(float).tolist(); flips=rng.integers(0,4,5).tolist()
        cfg=Screened(M=4,q=2,K=7); d=native(H,p,cfg)
        U,expected,rejected,count=patterns(H,p,s,r,flips,4,2,7)
        out=d.screen(s,r,flips)
        assert out.pool==U and out.enumerated==count==24 and out.rejected==rejected
        assert [tuple(x.id) for x in out.retained]==[x[2] for x in expected]
        assert [x.f for x in out.retained]==pytest.approx([x[0] for x in expected])
        for F in itertools.combinations(range(5),2):
            for b in itertools.product((0,1),repeat=2):
                key=[x for pair in zip(F,b) for x in pair]; score=d.score(s,r,key)
                completions=[e for e in itertools.product((0,1),repeat=5)
                    if all(e[j]==bit for j,bit in zip(F,b)) and np.array_equal(H@e%2,s)]
                if score.rejected: assert not completions
                for e in completions: assert score.f<=d.cost(e)+1e-13
    # Full lexicographic canonical ID wins exact score/reliability ties.
    d=native(np.ones((1,4),dtype=np.uint8),[.5]*4,Screened(M=4,q=1,K=3))
    assert [x.id for x in d.screen([0],[0]*4,[0]*4).retained]==[[0,0],[0,1],[1,0]]


def test_complete_against_independent_oracle_and_reuse():
    rng=np.random.default_rng(8); statuses=set(); multi=False; one=False
    for _ in range(35):
        H=rng.integers(0,2,(3,5),dtype=np.uint8); p=rng.uniform(.08,.4,5).tolist()
        cfg=Screened(T0=2,Tpost=5,M=4,q=2,K=6); d=native(H,p,cfg)
        shots=list(itertools.product((0,1),repeat=3))
        for s in shots+shots[::-1]:
            expected,key,initial,screen,success=search(H,p,s,cfg)
            out=d.decode(list(s),True)
            statuses.add(out.status)
            assert (out.correction if out.valid else None)==expected
            assert out.initial_iterations==initial['iterations']
            if screen:
                assert [tuple(x.id) for x in out.screening.retained]==[x[2] for x in screen[1]]
                assert out.completions==len(screen[1]) and out.successes==len(success)
                if expected is not None: assert tuple(out.selected_pattern)==key
                multi |= len({v[0] for v in success})>1
                one |= key is not None and 1 in key[1::2]
    assert {'INITIAL_CONVERGED','POST_CONVERGED','NONCONVERGENCE','LOCAL_CONTRADICTION'}<=statuses
    assert multi and one


def test_native_boundary_and_fixed_zero_rescue():
    H=np.array([[1,1]],dtype=np.uint8)
    d=native(H,[.1,.1],Screened(T0=1,M=2,q=1,K=4))
    out=d.decode([1],True)
    assert out.correction==[0,1] and out.completions==4
    assert out.selected_pattern==[0,0] # first pattern for same full-vector minimum
    diagnostic=out.diagnostics()
    assert diagnostic['history']==out.history
    assert [p['id'] for p in diagnostic['retained']]==[p.id for p in out.screening.retained]
    assert d.decode([0]).initial_success
    with pytest.raises(ValueError): d.decode([2])
    with pytest.raises(ValueError): d.score([1],[0,0],[1,0,0,1])
    with pytest.raises(ValueError): native(H,[.1,.1],Screened(M=3,q=3))
    with pytest.raises(OverflowError): native(np.ones((1,65)),[.1]*65,Screened(M=65,q=65))
