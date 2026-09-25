"""V2 storage checks on deterministic native paths and bounded physical runs."""
import copy
import json
from pathlib import Path
import time
import numpy as np
import pytest
import pyarrow.parquet as pq
import yaml
from qec_bp_benchmark.storage import failure_labels,commit_batch,committed_batches
from qec_bp_benchmark.storage.schema import COMMON,DECODES_V2,HYBRID_ROUNDS,DECODER_PHASES,table
from qec_bp_benchmark.storage.telemetry import attach_telemetry,validate_events
from qec_bp_benchmark.runner.pipeline import run_benchmark
from analysis.io import load_run
from analysis.validation import compare_runs
from test_hybrid_search import decoder,settings


def native_rows(rows,p,s,reason,profiling='phases',cfg=None):
    d=decoder(rows,p,cfg or settings(expansions=[1]*3,iterations=[1]*3),a=[list(range(len(p)))])
    start=time.process_time_ns(); wall=time.perf_counter_ns()
    result=d.decode(s,profiling=='phases')
    wall_ns=time.perf_counter_ns()-wall; cpu_ns=time.process_time_ns()-start
    events=d.export_telemetry()
    assert result.summary['exit_reason']==reason
    common=dict(run_id='run',instance_id='instance',sampling_id='sampling',batch_id=0,shot_index=0,
        shot_id='instance:sampling:0',batch_seed=91,family='fixture',distance=3,n=7,k_Z=1,rounds=3,
        physical_p=.1,noise_id='noise',model_hash='model',source_hash='source',config_hash='config')
    sample=dict(common,num_detectors=len(rows),detectors_packed=np.packbits(s,bitorder='little').tobytes(),actual_observables=[True])
    record={f.name:None for f in DECODES_V2}
    record.update(common,decoder_id='hybrid',decoder_name='fixture',decoder_profile='hybrid_search_soft_ms_osd0_v1',
        execution_position=0,prediction=list(map(bool,result.prediction)) if result.valid else None,
        status='SUCCESS' if result.valid else 'DECLARED_FAILURE',native_status=reason,syndrome_valid=result.valid,
        cost=result.cost if result.valid else None,cpu_ns=cpu_ns,wall_ns=wall_ns,timing_mode='isolated_latency',
        concurrent_load=False,workers=1,native_threads=1,blas_threads=1,oversubscribed=False,profiling=profiling)
    record.update(failure_labels(record['status'],result.valid,record['prediction'],[True],version=2))
    rr,pp=attach_telemetry(record,result.summary,events)
    validate_events([record],rr,pp,profiling)
    table([record],DECODES_V2);table(rr,HYBRID_ROUNDS);table(pp,DECODER_PHASES)
    return [sample],[record],rr,pp


PATHS=[([[0]],[.1],[0],'zero_syndrome'),([[]],[],[1],'inconsistent_syndrome'),
    ([[0,1],[1,2]],[.1,.05,.1],[1,1],'search_goal_generated'),
    ([[1,2,3],[1,2],[0,3]],[.1,.1,.5,.5,.5],[0,1,1],'bp_transition_valid'),
    ([[0,3,4],[1,2,3,4,5],[5],[0,4,5]],[.05,.2,.05,.05,.05,.5],[0,0,1,1],'bp_iteration_valid'),
    ([[0,1,2,3],[1,2,4,5],[3,4],[1,2,3]],[.2,.1,.05,.2,.2,.2],[0,1,1,1],'osd_valid'),
    ([[2],[0,1],[1,3,4],[0,1,2]],[.1,.05,.2,.2,.2,.2],[0,0,1,1],'osd_invalid')]


@pytest.mark.parametrize('fixture',PATHS)
@pytest.mark.parametrize('profiling',['none','phases'])
def test_native_paths_roundtrip(tmp_path,fixture,profiling):
    samples,decodes,rr,pp=native_rows(*fixture,profiling)
    commit_batch(tmp_path,0,samples,decodes,('hybrid',),'zstd',{},version=2,profiling=profiling,hybrid_rounds=rr,decoder_phases=pp)
    batch=next(committed_batches(tmp_path))
    assert len(batch['files'])==(4 if profiling=='phases' else 2)
    assert pq.read_table(tmp_path/'decodes/part-00000000.parquet').to_pylist()==decodes
    if decodes[0]['decoding_failure']: assert decodes[0]['valid_logical_mismatch'] is None
    if fixture[-1]=='zero_syndrome': assert decodes[0]['block_failure'] and not pp and not rr


def test_numerical_failure_and_signed_residual():
    rows=[[0,1,3,4,6,7],[0,2,3,4,6],[0,3,4,5,7],[2,3,4,6],[0,2,4],[3,4,5,6]]
    _,decodes,rr,pp=native_rows(rows,[.1]*8,[1,1,0,1,1,1],'numerical_failure',
        cfg=settings(expansions=[1]*3,iterations=[2]*3,max_depth=3,clip=1e308,margin=1e308))
    assert pp[-1]['candidate_logical_mismatch'] is None
    row=decodes[0]
    row['cpu_ns']=0;row['service_other_cpu_ns']=-row['native_prefix_cpu_ns']-row['osd_cpu_ns'];row['timing_accounting_ok']=False
    validate_events(decodes,rr,pp,'phases') # signed error retained, never clamped


@pytest.mark.parametrize('damage',['duplicate','orphan','duration','label','work','cycle'])
def test_event_corruption(damage):
    _,rows,rr,pp=native_rows(*PATHS[4])
    if damage=='duplicate': pp.append(copy.deepcopy(pp[0]))
    elif damage=='orphan': pp[0]['decoder_id']='missing'
    elif damage=='duration': pp[0]['cpu_ns']+=1
    elif damage=='label': pp[-1]['candidate_logical_mismatch']=not pp[-1]['candidate_logical_mismatch']
    elif damage=='work': pp[0]['work']+=1
    elif damage=='cycle': rr[0]['cycle_index']=90
    with pytest.raises(ValueError): validate_events(rows,rr,pp,'phases')


@pytest.mark.parametrize('damage',['missing','corrupt','duplicate','interrupted'])
def test_v2_shard_integrity(tmp_path,monkeypatch,damage):
    import qec_bp_benchmark.storage as storage
    samples,rows,rr,pp=native_rows(*PATHS[4])
    if damage=='duplicate':
        with pytest.raises(ValueError,match='duplicate'): commit_batch(tmp_path,0,samples,rows*2,('hybrid',),'none',{},version=2,profiling='phases',hybrid_rounds=rr,decoder_phases=pp)
        return
    if damage=='interrupted':
        real=storage.os.link
        def fail(source,target):
            if Path(target).parent.name=='decoder_phases': raise OSError('fourth shard interrupted')
            return real(source,target)
        monkeypatch.setattr(storage.os,'link',fail)
        with pytest.raises(OSError): commit_batch(tmp_path,0,samples,rows,('hybrid',),'none',{},version=2,profiling='phases',hybrid_rounds=rr,decoder_phases=pp)
        assert not list(committed_batches(tmp_path));return
    commit_batch(tmp_path,0,samples,rows,('hybrid',),'none',{},version=2,profiling='phases',hybrid_rounds=rr,decoder_phases=pp)
    target=tmp_path/'decoder_phases/part-00000000.parquet'
    if damage=='missing': target.unlink()
    else: target.write_bytes(b'corrupt')
    with pytest.raises((ValueError,OSError)): list(committed_batches(tmp_path))


def test_v1_projection():
    path=Path('assets/runs/20260921T031308.480482Z_694984c065d3')
    if not path.exists(): pytest.skip('historical local acceptance artifact unavailable')
    run=load_run(path)
    assert run.manifest['schema_version']==1
    assert all(r['exit_stage'] is None for r in run.decodes.to_pylist())
    assert run.hybrid_rounds.num_rows==run.decoder_phases.num_rows==0


def test_paired_workers_and_warmup_minimal_output(tmp_path):
    cfg={'noise':{'rates':[.001]},'experiment':{'codes':[{'family':'surface','distances':[3]},{'family':'bb72','distances':[6]}]},
        'sampling':{'shots_per_point':4,'batch_size':2,'master_seed':20260921,'warmup_count':1},
        'decoders':[{'profile':'hybrid_search_soft_ms_osd0_v1'},{'profile':'search_osd0_v1'},
            {'profile':'hybrid_search_soft_ms_osd0_cold_v1'},{'profile':'bposd_ms30_cs0'},{'profile':'beam8'}],
        'timing':{'profiling':'phases'},'output':{'root':str(tmp_path/'runs')}}
    path=tmp_path/'run.yaml';path.write_text(yaml.safe_dump(cfg))
    one=run_benchmark(path)
    cfg['execution']={'workers':2};cfg['sampling']['warmup_count']=2;cfg['sampling']['warmup_seed']=421
    path.write_text(yaml.safe_dump(cfg));two=run_benchmark(path)
    def rows(run, suffix):
        tables=[pq.read_table(file) for file in sorted((run/'data').glob(f'*_{suffix}.parquet'))]
        return [row for table in tables for row in table.to_pylist()]
    one_decodes=rows(one,'results');two_decodes=rows(two,'results')
    normalize=lambda values: sorted(json.dumps({k:v for k,v in row.items() if k!='latency_ns'},
                                               sort_keys=True) for row in values)
    assert normalize(one_decodes)==normalize(two_decodes)
    assert len(one_decodes)==len(two_decodes)==40
    assert len({row['shot_id'] for row in one_decodes})==8
    assert all(type(row['osd_called']) is bool for row in one_decodes)
    assert not rows(one,'samples') and not rows(two,'samples')
    assert sorted(item.name for item in one.iterdir())==['config_resolved.json','data']


@pytest.mark.parametrize('profiling',['future','none'])
def test_event_policy_must_match_decode_rows(profiling):
    _,rows,rr,pp=native_rows(*PATHS[2])
    with pytest.raises(ValueError,match='profiling policy'): validate_events(rows,rr,pp,profiling)


@pytest.mark.parametrize('damage',['result','stage','prefix'])
def test_terminal_phase_semantics(damage):
    _,rows,rr,pp=native_rows(*PATHS[4])
    if damage=='result': pp[-1]['result']='unknown_future_result'
    elif damage=='stage': rows[0].update(exit_stage='search',exit_reason='search_goal_generated')
    else: rows[0]['native_prefix_wall_ns']=0
    with pytest.raises(ValueError): validate_events(rows,rr,pp,'phases')
