"""Independent small paired experiments make misleading reach/speed claims falsifiable."""
import copy
import pytest
from qec_bp_benchmark.config import Analysis
from analysis.hybrid import paired_rows,summarize_pair,paired_statistics,stage_statistics
from analysis.statistics import aggregate_failures
from test_analysis import synthetic


def pair(index,*,reached=False,hybrid_time=120,baseline_time=100,failed=False,mismatch=False):
    h=synthetic(index,k=1,failed=failed,bits=[mismatch],decoder_id='hybrid',
        decoder_profile='hybrid_search_soft_ms_osd0_v1',profiling='phases',
        algorithm_version='HSBP-ALG-1.0',exit_stage='failed' if failed else ('osd' if reached else 'search'),
        exit_reason='osd_invalid' if failed and reached else ('osd_valid' if reached else 'search_goal_generated'),
        bp_attempts=0,osd_entered=reached,cpu_ns=hybrid_time,wall_ns=hybrid_time*2,
        native_prefix_cpu_ns=20,service_other_cpu_ns=hybrid_time-20-(40 if reached else 0),osd_cpu_ns=40 if reached else 0,
        native_prefix_wall_ns=40,service_other_wall_ns=2*(hybrid_time-20-(40 if reached else 0)),osd_wall_ns=80 if reached else 0,
        timing_accounting_ok=True)
    for phase in ('search','bp_transition','bp_iterations','prefix_other'):
        h[phase+'_cpu_ns']=20 if phase=='search' else 0
        h[phase+'_wall_ns']=40 if phase=='search' else 0
    b=synthetic(index,k=1,decoder_id='baseline',decoder_profile='bposd_ms30_cs0',profiling='phases',cpu_ns=baseline_time,wall_ns=baseline_time*2)
    return h,b


def test_less_osd_but_slower_exact_conditional_cost():
    pairs=[pair(0,baseline_time=10),pair(1,baseline_time=30),pair(2,reached=True,baseline_time=200)]
    result=summarize_pair(pairs,settings=Analysis(bootstrap_count=30))
    e=result['estimates']
    assert result['osd_reach']['rate']==pytest.approx(1/3)
    assert e['cpu_difference_ns']==40
    assert e['cpu_prefix_ns']==20
    assert e['cpu_avoided_baseline_ns']==pytest.approx(40/3) # not 2/3 * mean(10,30,200)
    assert e['cpu_fallback_difference_ns']==pytest.approx(-160/3)
    assert e['cpu_difference_ns']==pytest.approx(e['cpu_prefix_ns']+e['cpu_service_other_ns']-e['cpu_avoided_baseline_ns']+e['cpu_fallback_difference_ns'])
    assert result['noninferiority'] is None


def test_faster_but_less_accurate_and_error_decomposition():
    pairs=[pair(0,hybrid_time=30,mismatch=True),pair(1,hybrid_time=60,reached=True,failed=True),pair(2,hybrid_time=30)]
    result=summarize_pair(pairs,settings=Analysis(bootstrap_count=40,accuracy_margin_absolute=.1))
    e=result['estimates']
    assert e['cpu_difference_ns']==-60 and e['failure_difference']==pytest.approx(2/3)
    assert e['early_failure_difference']==e['fallback_failure_difference']==pytest.approx(1/3)
    assert result['discordance']=={'h0_b0':1,'h0_b1':0,'h1_b0':2,'h1_b1':0}
    assert not result['noninferiority']['criterion_met']
    assert result['accuracy']['hybrid']['conditional_valid_mismatch']['denominator']==2


@pytest.mark.parametrize('unit',['shot','batch'])
def test_bootstrap_reproducibility_and_metadata(unit):
    pairs=[pair(i,hybrid_time=30+i*10,reached=i>2) for i in range(6)]
    settings=Analysis(bootstrap_count=45,bootstrap_seed=41,bootstrap_unit=unit)
    a=summarize_pair(pairs,settings=settings);b=summarize_pair(pairs,settings=settings)
    assert a==b
    assert a['bootstrap']['units']==(6 if unit=='shot' else 2)
    assert a['intervals']['cpu_difference_ns']['low']<=a['estimates']['cpu_difference_ns']<=a['intervals']['cpu_difference_ns']['high']


def test_null_unmeasured_and_zero_conditional_denominators():
    assert summarize_pair([])['shots']==0
    h,b=pair(0,failed=True)
    stages=stage_statistics([h])[0]
    assert stages['bp_rescue']['rate'] is None and stages['osd_success']['rate'] is None
    assert stages['stages']['failed']['conditional_valid_mismatch']['rate'] is None
    assert stages['stages']['failed']['failure_contribution']['rate']==1
    for row in (h,b): row['profiling']='none'
    for key in list(h):
        if key.endswith('_ns') and key not in ('cpu_ns','wall_ns'): h[key]=None
    h['timing_accounting_ok']=None
    result=summarize_pair([(h,b)],settings=Analysis(bootstrap_count=10))
    assert result['estimates']['cpu_prefix_ns'] is None
    assert result['estimates']['cpu_difference_ns']==20
    assert result['pre_osd_failures']==1


@pytest.mark.parametrize('field',['run_id','sampling_id','model_hash','execution_id','profiling','timing_mode'])
def test_incompatible_pairs_rejected(field):
    h,b=pair(0);b[field]='other'
    with pytest.raises(ValueError,match='incompatible'): paired_rows([h,b],'hybrid','baseline')


def test_replays_do_not_inflate_ler_trials():
    rows=[r for i in range(3) for r in pair(i)]
    replay=copy.deepcopy(rows)
    for row in replay: row['run_id']='replay'
    results=paired_statistics(rows+replay,settings=Analysis(bootstrap_count=10))
    assert len(results)==2 and all(r['independent_physical_shots']==3 for r in results)
    assert all(r['shots']==3 for r in aggregate_failures(rows+replay))
    with pytest.raises(ValueError,match='duplicate'): paired_statistics(rows+rows)
    with pytest.raises(ValueError,match='missing'): paired_rows(rows[:-1],'hybrid','baseline')


def test_accounting_errors_rejected():
    h,b=pair(0);h['service_other_cpu_ns']+=1
    with pytest.raises(ValueError,match='identity'): summarize_pair([(h,b)])
    h,b=pair(0);h['timing_accounting_ok']=False
    with pytest.raises(ValueError,match='flagged'): summarize_pair([(h,b)])


def test_stage_denominators_cycle_work_and_avoided_splits():
    pairs=[pair(0),pair(1),pair(2),pair(3,failed=True),pair(4,reached=True)]
    pairs[0][0]['exit_reason']='zero_syndrome'
    pairs[2][0].update(exit_stage='guided_bp',exit_reason='bp_iteration_valid',bp_attempts=1)
    h=pairs[2][0]
    event={k:h[k] for k in ('run_id','shot_id','decoder_id')}
    event.update(cycle_index=0,bp_entered=True,result='bp_exit',expanded=2,generated=4,iterations=3,
        hint_ones=1,hint_zeros=2,node_cap_hit=False,prefix_cap_hit=False)
    stages=stage_statistics([h for h,b in pairs],[event])[0]
    assert sum(v['exit']['rate'] for v in stages['stages'].values())==1
    assert stages['bp_rescue']['rate']==1 and stages['bp_rescue']['denominator']==1
    assert stages['cycles'][0]['bp_iterations']==3 and stages['cycles'][0]['hint_zeros']==2
    assert stages['stages']['failed']['failure_contribution']['rate']==.2
    result=summarize_pair(pairs,settings=Analysis(bootstrap_count=15))
    for stage in ('zero_syndrome','search','guided_bp','pre_osd_failure'):
        assert result['estimates'][f'cpu_avoided_{stage}_ns']==20
    assert result['estimates']['cpu_prefix_on_osd_ns']==4
    assert result['estimates']['failed_failure_difference']==.2


@pytest.mark.parametrize('update',[{'bootstrap_count':0},{'bootstrap_seed':-1},{'bootstrap_unit':'unpaired'},
    {'accuracy_margin_absolute':float('nan')},{'accuracy_margin_absolute':-1},{'accuracy_margin_absolute':1.1}])
def test_analysis_config_rejects_invalid_hypothesis_settings(update):
    with pytest.raises(ValueError): Analysis(**update)


def test_int64_duration_difference_precedes_float_conversion():
    h,b=pair(0,hybrid_time=2**60+1,baseline_time=2**60)
    result=summarize_pair([(h,b)],settings=Analysis(bootstrap_count=5))
    assert result['estimates']['cpu_difference_ns']==1
    assert result['estimates']['wall_difference_ns']==2
    assert result['integer_totals']['cpu']=={'difference_ns':1,'four_term_sum_ns':1,'shots':1}
