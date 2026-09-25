"""Native full-decoder boundary vs a small independent Python controller.

Formula/tree reference comes from the independent Stage-3 scalar tests; BP/OSD
are the unchanged fork services. No simulator or production shot sampling.
"""
import math
import random
import sys

import pytest
from ldpc.hybrid_bp import DecimatedMinSumSession, Osd0Bridge
from qec_bp_benchmark import _native as native
from test_search_bp_stage3 import reference_tree


def settings(**values):
    s = native.SearchBP2Settings()
    for key, value in values.items():
        setattr(s, key, value)
    return s


def reference_admit(pool, k):
    def tie(i):
        x = pool[i]
        return x['full'], x['parent']['id'], x['delta'], i
    solve = sorted((i for i,x in enumerate(pool) if x['solve'] is not None), key=lambda i: (pool[i]['solve'], tie(i)))
    guide = sorted(range(len(pool)), key=lambda i: (pool[i]['guide'], tie(i)))
    out, seen = [], set()
    for i in solve[:k//2] + guide[:k-k//2] + guide + solve:
        if len(out) == k:
            break
        if pool[i]['full'] not in seen:
            out.append(pool[i]); seen.add(pool[i]['full'])
    return out


def reference_decode(rows, p, syndrome, s):
    bp = DecimatedMinSumSession(rows, len(p), p, s.history_window, s.history_clip, s.scaling_factor)
    bp.reset_from_channel(syndrome)
    initial = bp.continue_iterations(s.initial_iterations)
    counts = dict(executions=[], parents=[], osd=0, source=None, exit='initial', llrs=None)

    def valid(e):
        return all(sum(e[j] for j in row)%2 == bit for row,bit in zip(rows,syndrome))

    def capture(identifier):
        means = bp.clipped_mean_llr
        free = [j for j in range(len(p)) if bp.fixed[j] < 0]
        return dict(id=identifier, saved=bp.snapshot(), mean=means,
                    full=tuple((j,b) for j,b in enumerate(bp.fixed) if b>=0),
                    r=sum(abs(math.tanh(means[j]/2)) for j in free)/len(free) if free else 0.)

    if valid(bp.decision):
        return bp.decision, False, counts
    parents = [] if initial.status.name == 'LOCAL_CONTRADICTION' else [capture(0)]
    next_id = 1
    for _ in range(s.max_cycles):
        if not parents:
            break
        counts['parents'].append(len(parents))
        pool = []
        for parent in parents:
            local, direct = reference_tree(rows,p,syndrome,parent['full'],parent['mean'],
                s.selected_checks,s.local_variables,s.max_fixations,s.beta,s.guidance_strength,s.local_variable_policy)
            if direct is not None:
                assert valid(direct)
                counts['exit'] = 'search'
                return direct, False, counts
            for delta, solve, guide in local:
                pool.append(dict(parent=parent, delta=delta, full=tuple(sorted(parent['full']+delta)), solve=solve, guide=guide))
        admitted = reference_admit(pool, s.k_run)
        evaluated = []
        counts['executions'].append(0)
        for c in admitted:
            bp.inherit_descendant(c['parent']['saved'], c['delta'])
            # Verify all free edge messages really inherit; disabled edges are zero.
            edges = [j for row in rows for j in row]
            snapshot = bp.snapshot()
            assert snapshot.q == [0 if bp.fixed[j]>=0 else old for j,old in zip(edges,c['parent']['saved'].q)]
            assert tuple((j,b) for j,b in enumerate(bp.fixed) if b>=0) == c['full']
            advance = bp.continue_iterations(s.candidate_iterations)
            counts['executions'][-1] += 1
            if valid(bp.decision):
                counts['exit'] = 'decimated_bp'
                return bp.decision, False, counts
            if advance.status.name != 'LOCAL_CONTRADICTION':
                evaluated.append(capture(next_id)); next_id += 1
        parents = sorted(evaluated, key=lambda b: (-b['r'], b['full'], b['id']))[:s.k_keep]
    llrs = [math.log1p(-x)-math.log(x) for x in p]
    if parents:
        best = parents[0]
        counts['source'] = best['id']
        llrs = list(best['saved'].posterior_llr)
        for j,b in best['full']:
            llrs[j] = -sys.float_info.max if b else sys.float_info.max
    counts.update(osd=1, llrs=llrs, exit='osd')
    osd = Osd0Bridge(rows,len(p),p).decode(syndrome,llrs)
    return (osd.correction if valid(osd.correction) else []), True, counts


def check(rows, p, syndrome, s):
    a = [[j for j in range(len(p)) if j%2==0], list(range(len(p)))]
    decoder = native.SearchBP2Decoder(rows,len(p),p,a,s)
    result = decoder.decode(syndrome)
    expected, fallback, evidence = reference_decode(rows,p,syndrome,s)
    assert result.osd_called is fallback
    assert result.correction_by_search is (evidence['exit'] == 'search')
    assert result.valid == (all(sum(expected[j] for j in row)%2==bit for row,bit in zip(rows,syndrome)) if len(expected)==len(p) else False)
    assert result.correction == expected
    assert result.prediction == ([sum(expected[j] for j in row)%2 for row in a] if result.valid else [])
    assert result.physical_cost == pytest.approx(sum((math.log1p(-p[j])-math.log(p[j]))*x for j,x in enumerate(expected)))
    assert all(count <= s.k_run for count in evidence['executions'])
    return decoder, result, evidence


@pytest.mark.parametrize('policy',['fixed_root','refresh_descendant'])
@pytest.mark.parametrize('seed',range(16))
def test_recursive_decoder_matches_independent_controller(seed,policy):
    rng = random.Random(200+seed)
    n=6
    rows=[sorted(rng.sample(range(n),rng.randint(2,n))) for _ in range(5)]
    p=[.07,.11,.17,.23,.29,.37]
    syndrome=[rng.randrange(2) for _ in rows]
    s=settings(initial_iterations=2,candidate_iterations=3,history_window=2,
               selected_checks=2,local_variables=3,max_fixations=1,k_run=5,k_keep=3,max_cycles=3,
               local_variable_policy=policy,scaling_factor=.75)
    check(rows,p,syndrome,s)


def test_global_multiple_parent_cycles_and_retained_fallback():
    rows=[list(range(6))]*2
    p=[.1,.13,.17,.21,.27,.31]
    s=settings(initial_iterations=3,candidate_iterations=3,history_window=2,
               selected_checks=2,local_variables=2,max_fixations=1,k_run=4,k_keep=2,max_cycles=3)
    decoder,result,evidence=check(rows,p,[1,0],s)
    assert not result.valid and result.osd_called
    assert evidence['parents']==[1,2,2] and evidence['executions']==[4,4,4]
    assert evidence['source'] is not None and evidence['osd']==1
    zero=decoder.decode([0,0]); assert zero.valid and not zero.osd_called
    repeated=decoder.decode([1,0])
    assert repeated.valid==result.valid and repeated.osd_called and repeated.correction==result.correction
    assert not hasattr(result,'cycles') and not hasattr(result,'telemetry') and not hasattr(result,'parent_state')


def test_early_decimated_bp_solution_never_falls_back():
    s=settings(initial_iterations=1,candidate_iterations=3,history_window=1,
               selected_checks=1,local_variables=1,max_fixations=1,k_run=4,k_keep=2)
    _, result, evidence=check([[0,1],[1,2]],[.1]*3,[1,1],s)
    assert result.valid and not result.osd_called
    assert evidence['exit']=='decimated_bp' and evidence['executions']==[1] and evidence['osd']==0


def test_channel_fallback_and_invalid_input_recovery():
    s=settings()
    decoder,result,evidence=check([[],[0]],[.1],[1,0],s)
    assert not result.valid and result.osd_called
    assert evidence['source'] is None and evidence['llrs']==[math.log1p(-.1)-math.log(.1)]
    for syndrome in ([2,0],[1],[]):
        with pytest.raises(ValueError): decoder.decode(syndrome)
        assert decoder.decode([0,0]).valid
    empty=native.SearchBP2Decoder([],0,[],[],s).decode([])
    assert empty.valid and not empty.osd_called and empty.correction==[]


def test_checked_settings_and_small_result():
    for values in ({'k_run':0},{'k_keep':5},{'max_cycles':0},{'candidate_iterations':1}):
        with pytest.raises(ValueError): native.SearchBP2Decoder([[0]],1,[.1],[],settings(**values))
    result=native.SearchBP2Decoder([[0]],1,[.1],[[0]],settings()).decode([1])
    assert result.valid and result.prediction==[1] and not result.osd_called
    assert {x for x in dir(result) if not x.startswith('_')} == {
        'valid','correction','prediction','physical_cost','osd_called','correction_by_search'}


def test_successful_osd_once_after_budget_and_no_surviving_state_fallback():
    rows=[[0,2,3,4,6],[1,2,3,4,7],[0,1,2,3,6,7],[0,1,2,5,6,7],
          [1,2,3,4,6,7],[0,2,4,6,7],[0,2,3,5,6,7]]
    p=[.05,.09,.13,.17,.21,.25,.29,.33]
    syndrome=[1,1,0,1,0,0,0]
    s=settings(initial_iterations=1,candidate_iterations=1,history_window=1,
               selected_checks=1,local_variables=1,max_fixations=1,k_run=1,k_keep=1,max_cycles=1)
    decoder,result,evidence=check(rows,p,syndrome,s)
    assert result.valid and result.osd_called and evidence['osd']==1
    assert evidence['executions']==[1] and evidence['source'] is not None
    assert decoder.decode([0]*7).osd_called is False
    assert decoder.decode(syndrome).correction==result.correction
    _,failed,exhausted=check([[0],[0]],[.1],[1,0],s)
    assert not failed.valid and failed.osd_called
    assert exhausted['source'] is None and exhausted['executions']==[1]


def test_disabled_osd_fallback_returns_failure_without_calling_osd():
    s=settings(initial_iterations=1,candidate_iterations=1,history_window=1,
               selected_checks=1,local_variables=1,max_fixations=1,
               k_run=1,k_keep=1,max_cycles=1,osd_fallback=False)
    result=native.SearchBP2Decoder([[0],[0]],1,[.1],[],s).decode([1,0])
    assert not result.valid
    assert not result.osd_called
    assert not result.correction_by_search
    assert result.correction==[] and result.prediction==[]
