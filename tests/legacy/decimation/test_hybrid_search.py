"""Stage 3 mathematical and end-to-end native decision tests, not performance claims."""
from concurrent.futures import ThreadPoolExecutor
import itertools
import math
import numpy as np
import pytest
import stim
from qec_bp_benchmark.config import Hybrid
from qec_bp_benchmark.decoders import DecoderAdapter, native_hybrid
from qec_bp_benchmark.dem.model import convert_dem
from hybrid_oracle import decode as oracle


def settings(**kwargs):
    s=native_hybrid().HybridSettings()
    for k,v in kwargs.items(): setattr(s,k,v)
    return s


def decoder(rows, p, s=None, reference=False, a=None):
    return native_hybrid().HybridDecoder(rows,len(p),p,a or [],s or settings(),reference)


def scientific(summary):
    return {k:v for k,v in summary.items() if not k.endswith('_ns')}


def test_exhaustive_heuristic_and_local_rejection():
    native=native_hybrid()
    p=[.1,.2,.5];w=[math.log1p(-x)-math.log(x) for x in p]
    for matrix in itertools.product((0,1),repeat=6):
        rows=[[i for i in range(3) if matrix[a*3+i]] for a in range(2)]
        for s in itertools.product((0,1),repeat=2):
            for assigned in itertools.product((-1,0,1),repeat=3):
                key=[(i,x) for i,x in enumerate(assigned) if x>=0]
                got=native.hybrid_score(rows,3,p,s,key)
                ref=native.hybrid_score(rows,3,p,s,key,True)
                assert got==ref
                residual=[b ^ (sum(assigned[i]==1 for i in row)%2) for row,b in zip(rows,s)]
                impossible=any(b and not any(assigned[i]==-1 for i in row) for row,b in zip(rows,residual))
                assert math.isinf(got['h']) == impossible
                assert got['rho']==sum(residual)
                feasible=[]
                for completion in itertools.product((0,1),repeat=3):
                    if any(x!=-1 and x!=y for x,y in zip(assigned,completion)): continue
                    if any(sum(completion[i] for i in row)%2!=b for row,b in zip(rows,s)): continue
                    feasible.append(sum(w[i]*completion[i] for i in range(3) if assigned[i]==-1))
                if feasible: assert got['h'] <= min(feasible)+1e-14


def test_independent_full_oracle_and_native_reference_equality():
    rng=np.random.default_rng(128)
    for trial in range(350):
        n=int(rng.integers(1,8));m=int(rng.integers(1,6))
        rows=[np.flatnonzero(row).tolist() for row in rng.integers(0,2,(m,n))]
        p=rng.choice([.03,.1,.2,.5],n).tolist();syndrome=rng.integers(0,2,m).tolist()
        bp=trial%3!=0
        cfg=settings(max_depth=trial%4,expansions=[trial%3]*3,iterations=[2 if bp else 0]*3,
                     bp_enabled=bp,warm=bp and trial%3==1,max_generated_nodes=1+trial%19)
        a=[list(range(n))]
        fast,slow=decoder(rows,p,cfg,a=a),decoder(rows,p,cfg,True,a)
        x,y=fast.decode(syndrome,True),slow.decode(syndrome,True)
        assert x.valid==y.valid and x.correction==y.correction
        assert scientific(x.summary)==scientific(y.summary)
        e,reason,hints=oracle(rows,p,syndrome,cfg)
        assert x.summary['exit_reason']==reason
        assert (x.correction if x.valid else None)==e
        assert len(hints)==x.summary['bp_attempts']
        events=fast.export_telemetry()
        hint_ids=[r['hint_node_id'] for r in events['rounds'] if r['bp_entered']]
        assert len(hint_ids)==len(set(hint_ids))
        assert x.summary['search_expanded_nodes']<=sum(cfg.expansions)
        assert x.summary['search_generated_nodes']<=cfg.max_generated_nodes
        if x.valid:
            assert x.prediction==[sum(e)%2]
            assert x.cost==pytest.approx(sum(math.log1p(-p[i])-math.log(p[i]) for i,v in enumerate(e) if v))
        # Every event is owned and measured; no cross-shot state after reuse.
        snapshot=scientific(x.summary);fast.decode([0]*m)
        z=fast.decode(syndrome)
        assert snapshot==scientific(z.summary) and z.correction==x.correction
        assert fast.export_telemetry()=={'rounds':[],'phases':[]}


@pytest.mark.parametrize('rows,p,s,reason',[
    ([[0]], [.1], [0], 'zero_syndrome'),
    ([[]], [], [1], 'inconsistent_syndrome'),
    ([[0,1],[1,2]], [.1,.05,.1], [1,1], 'search_goal_generated'),
    ([[1,2,3],[1,2],[0,3]], [.1,.1,.5,.5,.5], [0,1,1], 'bp_transition_valid'),
    ([[0,3,4],[1,2,3,4,5],[5],[0,4,5]], [.05,.2,.05,.05,.05,.5], [0,0,1,1], 'bp_iteration_valid'),
    ([[0,1,2,3],[1,2,4,5],[3,4],[1,2,3]], [.2,.1,.05,.2,.2,.2], [0,1,1,1], 'osd_valid'),
    ([[2],[0,1],[1,3,4],[0,1,2]], [.1,.05,.2,.2,.2,.2], [0,0,1,1], 'osd_invalid'),
])
def test_terminal_paths_and_telemetry(rows,p,s,reason):
    d=decoder(rows,p,settings(expansions=[1]*3,iterations=[1]*3))
    result=d.decode(s,True);summary=result.summary;events=d.export_telemetry()
    assert summary['exit_reason']==reason
    assert summary['cycles_started']==len(events['rounds'])
    assert summary['bp_iterations']==sum(p['work'] for p in events['phases'] if p['phase']=='bp_iterations')
    for clock in ('cpu','wall'):
        for phase in ('search','bp_transition','bp_iterations','osd'):
            assert summary[f'{phase}_{clock}_ns']==sum(p[f'{clock}_ns'] for p in events['phases'] if p['phase']==phase)
        assert summary[f'prefix_other_{clock}_ns']>=0
    if reason=='bp_transition_valid': assert summary['bp_iterations']==0
    if reason=='zero_syndrome': assert summary['search_generated_nodes']==0 and not events['phases']
    if result.valid: assert summary['exit_stage']!='failed'
    else: assert summary['exit_stage']=='failed'
    assert summary['osd_entered']==reason.startswith('osd')
    assert all(p['native_wall_end_ns']>=p['native_wall_start_ns'] for p in events['phases'])


def test_depth_goals_duplicate_columns_caps_and_no_hidden_bp():
    # Goal-on-generation accepts column 1, although a cheaper two-column goal exists.
    p=[1/(1+math.exp(x)) for x in (2.,5.,2.)]
    r=decoder([[0,1],[1,2]],p,settings(max_depth=2)).decode([1,1])
    assert r.correction==[0,1,0] and r.summary['bp_attempts']==0
    d=decoder([[0],[1]],[.1,.2],settings(max_depth=2,bp_enabled=False,warm=False,iterations=[0]*3,expansions=[1]*3))
    r=d.decode([1,1]); assert r.correction==[1,1] and r.summary['search_max_depth_reached']==2
    duplicate=decoder([[0,1]],[.1,.1],a=[[0],[1]]).decode([1])
    assert duplicate.correction==[1,0] and duplicate.prediction==[1,0]
    for config,reason in [(settings(max_generated_nodes=1),'node_cap'),
                          (settings(prefix_cpu_budget_ns=1),'prefix_cpu_cap'),
                          (settings(max_depth=0),'frontier_and_hints_exhausted'),
                          (settings(expansions=[],iterations=[]),'cycle_budget'),
                          (settings(expansions=[0],iterations=[1]),'cycle_budget')]:
        r=decoder([[0,1],[1,2]],[.1]*3,config).decode([1,1],True)
        assert r.summary['fallback_reason']==reason and r.summary['osd_llr_source']=='clipped_channel'
        assert r.summary['bp_attempts']==0 and r.summary['osd_calls']==1
        assert r.valid


def test_warm_persistence_ablation_and_exceptions():
    rows=[[0,1,2,4],[4,5],[1,3,4,5],[0,1,2,3,4,5]]
    p=[.2,.05,.5,.2,.5,.5];s=[0,1,1,0]
    cfg=settings(expansions=[1]*3,iterations=[1]*3)
    d=decoder(rows,p,cfg);r=d.decode(s,True);events=d.export_telemetry()
    assert r.summary['bp_warm_transitions']>0
    for before,after in zip(events['rounds'],events['rounds'][1:]):
        assert before['frontier_after']==after['frontier_before']
        assert before['guidance_after']==after['guidance_before']
    old=events.copy()
    with pytest.raises(ValueError): d.decode([9]*4)
    assert d.export_telemetry()=={'rounds':[],'phases':[]}
    assert d.decode(s).correction==r.correction and events==old
    cold=decoder(rows,p,settings(expansions=[1]*3,iterations=[1]*3,warm=False)).decode(s)
    assert cold.summary['bp_warm_transitions']==0
    def run(_): return decoder(rows,p,cfg).decode(s).correction
    with ThreadPoolExecutor(max_workers=4) as pool: assert all(e==r.correction for e in pool.map(run,range(16)))


def test_callable_adapter_export_and_empty_model():
    p=convert_dem(stim.DetectorErrorModel('error(0.1) D0 L0\nerror(0.2) D1 L11'))
    with pytest.raises(ValueError,match="per-node traces"):
        DecoderAdapter(p,Hybrid(),diagnostics=True)
    d=DecoderAdapter(p,Hybrid(),profiling=True)
    r=d.decode(np.array([1,1]));assert r.syndrome_valid and len(r.prediction)==12
    assert r.hybrid_summary['algorithm_version']=='HSBP-ALG-1.0'
    assert d.export_telemetry()['rounds']
    empty=convert_dem(stim.DetectorErrorModel('detector D0\nlogical_observable L11'))
    a=DecoderAdapter(empty,Hybrid())
    assert a.decode(np.array([0])).prediction.tolist()==[0]*12
    assert a.decode(np.array([1])).hybrid_summary['exit_reason']=='inconsistent_syndrome'


def test_numerical_failure_is_explicit_measured_and_resettable():
    rows=[[0,1,3,4,6,7],[0,2,3,4,6],[0,3,4,5,7],[2,3,4,6],[0,2,4],[3,4,5,6]]
    d=decoder(rows,[.1]*8,settings(expansions=[1]*3,iterations=[2]*3,max_depth=3,clip=1e308,margin=1e308))
    s=[1,1,0,1,1,1];out=d.decode(s,True)
    assert not out.valid and out.summary['exit_reason']=='numerical_failure'
    assert not out.summary['osd_entered']
    events=d.export_telemetry()
    assert len(events['rounds'])==out.summary['cycles_started']
    assert events['rounds'][-1]['result']=='failed'
    assert events['phases'][-1]['result']=='exception'
    assert out.summary['bp_iterations']==sum(r['iterations'] for r in events['rounds'])
    assert d.decode([0]*6).valid
    assert d.decode(s).summary['exit_reason']=='numerical_failure'


def test_source_inventory_and_runtime_rejection(tmp_path,monkeypatch):
    from pathlib import Path
    from ldpc import hybrid_bp
    from qec_bp_benchmark import bp,native_sources
    from qec_bp_benchmark.decoders import ROOT
    for relative in hybrid_bp.SOURCE_FILES:
        target=tmp_path/relative;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((ROOT/'external_lib/ldpc'/relative).read_bytes())
    baseline=hybrid_bp.source_digest(tmp_path)
    for relative in hybrid_bp.SOURCE_FILES:
        target=tmp_path/relative;original=target.read_bytes();target.write_bytes(original+b'\n')
        assert hybrid_bp.source_digest(tmp_path)!=baseline
        target.write_bytes(original)
    bp.verified_hybrid_backend.cache_clear()
    with monkeypatch.context() as patch:
        patch.setattr(hybrid_bp,'source_digest',lambda root:'modified')
        with pytest.raises(RuntimeError,match='build/source'): bp.verified_hybrid_backend()
    bp.verified_hybrid_backend.cache_clear()
    native_hybrid.cache_clear()
    with monkeypatch.context() as patch:
        patch.setattr(native_sources,'hybrid_project_digest',lambda root:'modified')
        with pytest.raises(RuntimeError,match='source/build'): native_hybrid()
    native_hybrid.cache_clear()
    assert native_hybrid()


def test_depth_counter_and_transition_residual_scope():
    result=decoder([[0],[0]],[.1],settings(max_depth=1)).decode([1,0])
    assert result.summary['search_depth_limited']==1
    assert result.summary['search_rejected_local']==1
    zero=decoder([[0]],[.1],settings(max_depth=0)).decode([1])
    assert zero.summary['search_depth_limited']==1  # The nonterminal depth-zero root.
    rows=[[1,2,3],[1,2],[0,3]];p=[.1,.1,.5,.5,.5];s=[0,1,1]
    d=decoder(rows,p,settings(expansions=[1]*3,iterations=[1]*3))
    result=d.decode(s,True);row=d.export_telemetry()['rounds'][0]
    prior=[int(x==.5) for x in p]
    assert row['residual_before']==sum(sum(prior[i] for i in r)%2!=b for r,b in zip(rows,s))
    assert row['residual_after']==0 and result.summary['exit_reason']=='bp_transition_valid'
