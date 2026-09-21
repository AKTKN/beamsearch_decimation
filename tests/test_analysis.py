"""Independent hand-counted and exact-quantile expectations for Stage 6 analysis."""
import copy
import json
import math
from pathlib import Path
import shutil
import numpy as np
import pytest
from analysis.statistics import (wilson_interval,aggregate_failures,summarize_failure_group,
    timing_statistics,aggregate_timings,empirical_distribution)
from analysis.io import discover_runs,load_run,select_records
from qec_bp_benchmark.storage import failure_labels,atomic_json


def synthetic(index,*,failed=False,bits=None,k=12,**overrides):
    bits=[False]*k if bits is None else bits
    row=dict(run_id='run',instance_id='instance',sampling_id='sampling',decoder_id='decoder',family='bb72',
        distance=6,n=72,k_Z=k,rounds=6,physical_p=.001,noise_id='noise',model_hash='model',
        timing_mode='isolated_latency',workers=1,native_threads=1,blas_threads=1,concurrent_load=False,
        oversubscribed=False,profiling='none',execution_id='execution',comparison_id='comparison',run_status='complete',
        shot_id=f'shot{index}',batch_id=0 if index==0 else 1,decoder_name='test',decoder_profile='beam8',
        decoder_parameters={},status='DECLARED_FAILURE' if failed else 'SUCCESS',syndrome_valid=not failed,
        prediction=None if failed else bits,initial_success=None,native_status='SEARCH_EXHAUSTED' if failed else 'CONVERGED',
        cpu_ns=index*10,wall_ns=index*20)
    row.update(failure_labels(row['status'],not failed,row['prediction'],[False]*k))
    row.update(overrides)
    return row


def test_wilson_exact_endpoints_and_zero_denominator():
    # Independent known two-sided 95% score interval endpoints.
    assert wilson_interval(0,10)==pytest.approx((0,0.2775327998628892))
    assert wilson_interval(5,10)==pytest.approx((0.236593090512564,0.763406909487436))
    assert wilson_interval(10,10)==pytest.approx((0.7224672001371107,1))
    assert wilson_interval(0,0)==(None,None)
    assert wilson_interval(0,10,.9)[1]<wilson_interval(0,10,.95)[1]
    for k,n,c in [(-1,2,.95),(3,2,.95),(True,2,.95),(0,2,1),(0,2,float('nan'))]:
        with pytest.raises(ValueError): wilson_interval(k,n,c)


def test_summed_counts_components_and_bb_block_denominator():
    # Batch 0: 1/1 failure. Batch 1: 1/3 mismatch; total is 2/4, not mean(1,1/3).
    bits=[False]*12; bits[0]=bits[11]=True
    data=[synthetic(0,failed=True),synthetic(1,bits=bits),synthetic(2),synthetic(3)]
    out=aggregate_failures(data)[0]
    assert out['shots']==4 and out['valid_outputs']==3
    assert out['block_failure']['rate']==.5 and out['block_failure']['denominator']==4
    assert out['decoding_failure']['rate']==.25 and out['valid_mismatch_contribution']['rate']==.25
    assert out['conditional_valid_mismatch']['rate']==pytest.approx(1/3)
    assert out['observable_mismatch_counts']==[1]+[0]*10+[1]
    assert out['observable_total_failure_counts']==[2]+[1]*10+[2]
    assert out['block_failure']['high']==pytest.approx(wilson_interval(2,4)[1])
    failed=aggregate_failures([synthetic(0,failed=True),synthetic(1,failed=True)])[0]
    assert failed['conditional_valid_mismatch']['rate'] is None
    assert failed['conditional_valid_mismatch']['high'] is None
    zeros=aggregate_failures([synthetic(0),synthetic(1)])[0]
    assert zeros['block_failure']['rate']==0 and zeros['block_failure']['high']>0


@pytest.mark.parametrize('change',[{'timing_mode':'throughput'},{'workers':2},{'profiling':'phases'},
    {'noise_id':'different'},{'instance_id':'different'},{'decoder_id':'different'},{'execution_id':'different'},
    {'run_id':'replay'},{'sampling_id':'different'}])
def test_incompatible_groups_cannot_pool(change):
    data=[synthetic(0),synthetic(1,**change)]
    assert len(aggregate_failures(data))==2
    with pytest.raises(ValueError,match='compatible'): summarize_failure_group(data)


def test_duplicate_rows_are_not_extra_trials():
    row=synthetic(0)
    with pytest.raises(ValueError,match='duplicate'): aggregate_failures([row,copy.deepcopy(row)])


def test_exact_quantiles_ecdf_and_tail_support():
    stats=timing_statistics([0,10,20,30],quantiles=[.25])
    assert stats['mean_ns']==15 and stats['median_ns']==15 and stats['max_ns']==30
    assert stats['p90_ns']==pytest.approx(27) and stats['p95_ns']==pytest.approx(28.5)
    assert stats['p99_ns']==pytest.approx(29.7) and stats['p99_9_ns']==pytest.approx(29.97)
    q99=next(q for q in stats['quantiles'] if q['q']==.99)
    assert q99['expected_tail_count']==pytest.approx(.04) and q99['insufficient_for_performance_claim']
    x,y=empirical_distribution([10,0,10,20]); assert x.tolist()==[0,10,20]
    assert y.tolist()==[.25,.75,1]
    assert empirical_distribution([10,0,10,20],survival=True)[1].tolist()==[.75,.25,0]
    assert timing_statistics([])['mean_ns'] is None
    for values in [[-1],[float('nan')],[1.5]]:
        with pytest.raises(ValueError): timing_statistics(values)
    with pytest.raises(ValueError): timing_statistics([1],quantiles=[1.1])


def test_failure_timings_and_missing_counters_remain_visible():
    data=[synthetic(0),synthetic(1,failed=True),synthetic(2,initial_success=True)]
    result=aggregate_timings(data,stratify=True)
    all_cpu=next(r for r in result if r['timer']=='cpu_ns' and r['stratum']=='all')
    assert all_cpu['samples']==3 and all_cpu['mean_ns']==10
    assert {'all','failure','valid_output_unclassified','initial_bp_success'}=={r['stratum'] for r in result}


@pytest.fixture(scope='module')
def saved_run(tmp_path_factory):
    # Real native run, tiny physical surface model; no fake manifest or parquet.
    import yaml
    from qec_bp_benchmark.runner.pipeline import run_benchmark
    root=tmp_path_factory.mktemp('analysis')
    config={'experiment':{'codes':[{'family':'surface','distances':[3]}]},'noise':{'rates':[0]},
        'circuit':{'cache':str(root/'cache')},'sampling':{'shots_per_point':3,'batch_size':2,'warmup_count':0},
        'execution':{'workers':1},'output':{'root':str(root/'runs')}}
    path=root/'config.yaml'; path.write_text(yaml.safe_dump(config))
    return run_benchmark(path)


def test_loading_selection_and_manifest_integrity(saved_run,tmp_path):
    run=load_run(saved_run)
    assert run.samples.num_rows==3 and run.decodes.num_rows==9
    assert discover_runs(saved_run)==(saved_run,)
    assert len(select_records([run],families=['surface'],distances=[3],decoder_ids=[run.manifest['decoders'][0]['id']]))==3
    assert select_records([run],families=['bb72'])==[]
    with pytest.raises(ValueError,match='duplicate'): select_records([run,run])
    damaged=tmp_path/'damaged'; shutil.copytree(saved_run,damaged)
    manifest=json.loads((damaged/'manifest.json').read_text()); manifest['completed_batches']=0
    atomic_json(damaged/'manifest.json',manifest)
    with pytest.raises(ValueError,match='inconsistent'): load_run(damaged)


def test_incomplete_reads_only_committed_subset(saved_run,tmp_path):
    source=tmp_path/'incomplete'; shutil.copytree(saved_run,source)
    manifest=json.loads((source/'manifest.json').read_text()); manifest['status']='incomplete'
    atomic_json(source/'manifest.json',manifest)
    instance=source/manifest['instances'][0]['directory']
    (instance/'batch_manifests/part-00000001.json').unlink()
    with pytest.raises(ValueError,match='incomplete'): load_run(source)
    assert discover_runs(source)==()
    partial=load_run(source,allow_incomplete=True)
    assert partial.samples.num_rows==2 and partial.decodes.num_rows==6
    assert all(r['run_status']=='incomplete' for r in aggregate_failures(partial.records()))
    # Claiming complete cannot hide the missing marker or orphan final shard.
    manifest['status']='complete'; atomic_json(source/'manifest.json',manifest)
    with pytest.raises(ValueError,match='missing'): load_run(source)


def test_corrupt_shard_is_not_a_null_output(saved_run,tmp_path):
    target=tmp_path/'corrupt'; shutil.copytree(saved_run,target)
    manifest=json.loads((target/'manifest.json').read_text())
    shard=next((target/manifest['instances'][0]['directory']/'decodes').glob('*.parquet'))
    shard.write_bytes(shard.read_bytes()+b'corruption')
    with pytest.raises(ValueError,match='checksum'): load_run(target)


def test_report_and_standalone_exports(saved_run,tmp_path):
    import matplotlib
    matplotlib.use('Agg')
    from analysis.report import create_report
    from qec_bp_benchmark.config import Analysis
    settings=Analysis(plots=('failure_rate','cpu_ecdf','wall_survival'),stratify_timing=True)
    path=create_report([saved_run],tmp_path,settings=settings)
    manifest=json.loads((path/'manifest.json').read_text())
    assert manifest['status']=='complete' and manifest['decode_rows']==9
    assert len(list((path/'figures').glob('*.png')))==3
    assert len(list((path/'figures').glob('*.pdf')))==3
    failures=json.loads((path/'failures.json').read_text())['groups']
    assert all(g['block_failure']['rate']==0 and g['block_failure']['high']>0 for g in failures)
    assert 'NaN' not in (path/'timings.json').read_text()


def test_zero_failure_plot_shows_bound_not_positive_rate(tmp_path,monkeypatch):
    import matplotlib
    matplotlib.use('Agg')
    from analysis import plots
    data=[synthetic(0),synthetic(1)]
    summary=aggregate_failures(data)
    inspected=[]
    def inspect(figure,output,stem):
        axis=figure.axes[0]
        triangle=next(line for line in axis.lines if line.get_marker()=='v')
        assert list(triangle.get_ydata())==[summary[0]['block_failure']['high']]
        assert any('0/2 upper' in text.get_text() for text in axis.texts)
        inspected.append(True)
        return []
    monkeypatch.setattr(plots,'_save',inspect)
    plots.plot_failure_rates(summary,tmp_path)
    assert inspected and summary[0]['block_failure']['rate']==0


def test_analysis_import_does_not_load_decoders_or_sample():
    import subprocess,sys
    subprocess.run([sys.executable,'-c',
        'import analysis,sys; assert not any(name in sys.modules for name in ("ldpc","beam_search_decoder","stim","qldpc"))'],check=True)


def test_analysis_configuration_rejects_duplicate_outputs():
    from qec_bp_benchmark.config import Analysis
    with pytest.raises(ValueError,match='unique'): Analysis(plots=('cpu_ecdf','cpu_ecdf'))
    with pytest.raises(ValueError,match='unique'): Analysis(quantiles=(.9,.9))


def test_saved_run_comparison_ignores_only_execution_fields(saved_run):
    from dataclasses import replace
    import pyarrow as pa
    from analysis.validation import compare_runs
    run=load_run(saved_run)
    rows=run.decodes.to_pylist()
    for row in rows: row['cpu_ns']+=1000; row['wall_ns']+=2000
    changed=replace(run,decodes=pa.Table.from_pylist(rows,schema=run.decodes.schema))
    assert compare_runs(run,changed)['shared_decodes_equal']==9
    rows[0]['prediction']=[not rows[0]['prediction'][0]]
    changed=replace(run,decodes=pa.Table.from_pylist(rows,schema=run.decodes.schema))
    with pytest.raises(ValueError,match='non-timing'): compare_runs(run,changed)
