"""Small real-native pairing/parallel/replay checks and targeted storage fault tests."""
import copy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import time
import numpy as np
import pyarrow.parquet as pq
import pytest
import yaml
from qec_bp_benchmark.config import Config,load_config
from qec_bp_benchmark.runner.plan import batch_seed,task_stream
from qec_bp_benchmark.runner.pipeline import run_benchmark,bounded_results
from qec_bp_benchmark.storage import committed_batches,commit_batch,failure_labels,atomic_json,validate_pair
from qec_bp_benchmark.storage.schema import SAMPLES,DECODES,table


def write_config(path,root,**updates):
    data={'experiment':{'codes':[{'family':'surface','distances':[3]}]},'noise':{'rates':[.005]},
          'circuit':{'cache':str(root/'circuits')},'sampling':{'shots_per_point':5,'batch_size':2,'master_seed':91,'warmup_count':1},
          'decoders':[{'profile':'screened_reference','T0':2,'Tpost':3,'M':4,'q':2,'K':4},
                      {'profile':'bposd_ms30_cs10','max_iter':3,'osd_order':2},
                      {'profile':'beam8','initial_iters':3,'iters_per_round':3,'max_rounds':2}],
          'execution':{'workers':1,'worker_cache_size':1},'output':{'root':str(root/'runs')}}
    data.update(updates); path.write_text(yaml.safe_dump(data)); return path


def rows(run):
    manifest=json.loads((run/'manifest.json').read_text()); samples=[]; decodes=[]
    for instance in manifest['instances']:
        directory=run/instance['directory']
        for batch in committed_batches(directory):
            samples+=pq.read_table(directory/f'samples/part-{batch["batch_id"]:08d}.parquet').to_pylist()
            decodes+=pq.read_table(directory/f'decodes/part-{batch["batch_id"]:08d}.parquet').to_pylist()
    return samples,decodes


@pytest.fixture(scope='module')
def runs(tmp_path_factory):
    root=tmp_path_factory.mktemp('paired')
    config=write_config(root/'one.yaml',root)
    one=run_benchmark(config)
    data=yaml.safe_load(config.read_text()); data['execution']['workers']=2
    data['decoders'].reverse(); data['sampling']['warmup_count']=2
    data['sampling']['warmup_seed']=1248
    two_config=root/'two.yaml'; two_config.write_text(yaml.safe_dump(data))
    two=run_benchmark(two_config)
    replay=run_benchmark(two_config,replay_source=one)
    return root,one,two,replay


def test_plan_is_lazy_immutable_and_uint64():
    c=Config(noise={'rates':[.001]},sampling={'shots_per_point':5,'batch_size':2})
    tasks=task_stream((('a','/tmp/a'),),c,'sampling')
    assert iter(tasks) is tasks
    t=list(tasks); assert [x.count for x in t]==[2,2,1] and [x.offset for x in t]==[0,2,4]
    with pytest.raises(FrozenInstanceError): t[0].count=99
    assert all(0<=x.seed<2**64 for x in t)
    assert batch_seed(91,'a',0)!=batch_seed(91,'a',0,'warmup')
    assert batch_seed(91,'a',0)==batch_seed(91,'a',0)


def test_real_native_parallel_pairing_warmup_and_replay(runs):
    root,one,two,replay=runs
    s1,d1=rows(one)
    sample_drop={'run_id','source_hash','config_hash'}
    decode_drop=sample_drop|{'cpu_ns','wall_ns','workers','concurrent_load','oversubscribed'}
    normalize=lambda records,drop:sorted((json.dumps({k:v.hex() if isinstance(v,bytes) else v for k,v in r.items() if k not in drop},sort_keys=True) for r in records))
    for run in (two,replay):
        ss,dd=rows(run)
        assert normalize(s1,sample_drop)==normalize(ss,sample_drop)
        assert normalize(d1,decode_drop)==normalize(dd,decode_drop)
    assert len(s1)==5 and len(d1)==15
    assert {r['batch_id'] for r in s1}=={0,1,2}
    assert all(r['cpu_ns']>=0 and r['wall_ns']>=0 for r in d1)
    for shot in s1:
        grouped=[d for d in d1 if d['shot_id']==shot['shot_id']]
        assert len(grouped)==3
    for run in (one,two,replay):
        manifest=json.loads((run/'manifest.json').read_text())
        assert manifest['status']=='complete' and manifest['completed_batches']==3
        env=json.loads((run/'environment.json').read_text())
        assert env['native_modules']['beam_search_decoder._beam_search_decoder']['path'].endswith('.so')
        for inst in manifest['instances']:
            for batch in committed_batches(run/inst['directory']):
                assert batch['setup']['cache_entries']<=1
                assert all(x['num_threads']==1 for x in batch['setup']['threadpools'])


@pytest.mark.parametrize('workers,replay,verbose',[(1,False,False),(1,False,True),(2,False,True),(2,True,True)])
def test_verbose_cli_progress_and_scientific_equality(runs,tmp_path,workers,replay,verbose):
    import subprocess,sys
    from analysis.io import load_run
    from analysis.validation import compare_runs
    _,source,_,_=runs
    config=write_config(tmp_path/'verbose.yaml',tmp_path,execution={'workers':workers})
    if replay:
        data=yaml.safe_load(config.read_text())
        data['sampling']['shots_per_point']=999
        config.write_text(yaml.safe_dump(data))
    root=Path(__file__).resolve().parents[1]
    script='replay_samples.py' if replay else 'run_benchmark.py'
    command=[sys.executable,str(root/'python_scripts'/script)]
    if replay: command.append(str(source))
    result=subprocess.run([*command,str(config),*(['--verbose'] if verbose else [])],capture_output=True,text=True,check=True)
    assert len(result.stdout.strip().splitlines())==1
    target=Path(result.stdout.strip())
    assert compare_runs(load_run(source),load_run(target))['shared_decodes_equal']==15
    if not verbose:
        assert '[qec ' not in result.stderr
        return
    assert result.stderr.count('Committed batch ')==3
    assert '5 physical shots, 15 decode rows, 3 batches' in result.stderr
    assert 'Committed batch 3/3 (100.0%); shots=5/5' in result.stderr
    assert f'workers={workers}, timing=throughput' in result.stderr
    assert 'Complete: 5 physical shots, 15 decode rows' in result.stderr
    assert ('Reading saved samples' if replay else 'Preparing surface d=3') in result.stderr


@pytest.mark.parametrize('compression',['zstd','snappy','none'])
def test_parquet_nulls_seeds_and_duplicate_guard(runs,tmp_path,compression):
    _,one,_,_=runs; samples,decodes=rows(one)
    samples=[copy.deepcopy(s) for s in samples if s['batch_id']==0]
    decodes=[copy.deepcopy(d) for d in decodes if d['batch_id']==0]
    for row in samples+decodes: row['batch_seed']=2**64-1
    ids=tuple(sorted({r['decoder_id'] for r in decodes}))
    for row in decodes:
        row.update(status='DECLARED_FAILURE',native_status='TEST_EXHAUSTED',syndrome_valid=False,prediction=None,cost=None)
        row.update(failure_labels(row['status'],False,None,[False]))
    instance=tmp_path/'instance'; instance.mkdir()
    commit_batch(instance,0,samples,decodes,ids,compression,{})
    batch=list(committed_batches(instance))[0]
    assert batch['seed']==2**64-1
    actual=pq.read_table(instance/'decodes/part-00000000.parquet')
    assert actual.schema.equals(DECODES,check_metadata=True)
    assert actual['prediction'].null_count==len(decodes) and actual['cost'].null_count==len(decodes)
    assert actual['batch_seed'].to_pylist()==[2**64-1]*len(decodes)
    with pytest.raises(FileExistsError): commit_batch(instance,0,samples,decodes,ids,'none',{})
    missing=decodes[:-1]
    with pytest.raises(ValueError,match='missing'): validate_pair(samples,missing,ids)
    bad=copy.deepcopy(decodes); bad[0]['cost']=float('nan')
    with pytest.raises(ValueError): validate_pair(samples,bad,ids)
    with pytest.raises(ValueError): atomic_json(tmp_path/'nonfinite.json',{'cost':float('nan')})
    altered=copy.deepcopy(samples); altered[0]['unexpected']='silent drop forbidden'
    with pytest.raises(ValueError): table(altered,SAMPLES)


def test_failure_definitions_all_12_observables():
    truth=[False]*12; prediction=truth.copy(); prediction[11]=True
    mismatch=failure_labels('SUCCESS',True,prediction,truth)
    assert mismatch['block_failure'] and not mismatch['decoding_failure']
    assert mismatch['valid_logical_mismatch'] and sum(mismatch['observable_mismatch'])==1
    failed=failure_labels('DECLARED_FAILURE',False,None,truth)
    assert failed['decoding_failure'] and failed['block_failure'] and not failed['valid_logical_mismatch']
    assert failed['observable_mismatch'] is None and failed['observable_total_failure']==[True]*12
    with pytest.raises(ValueError): failure_labels('SUCCESS',True,[False],truth)


def delayed(value):
    time.sleep(.04 if value==0 else .001)
    if value<0: raise RuntimeError('deliberate worker failure')
    return value


def test_bounded_out_of_order_and_errors():
    produced=0; consumed=0
    def tasks():
        nonlocal produced
        for x in range(15):
            produced+=1
            assert produced-consumed<=3
            yield x
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=[]
        for result in bounded_results(pool,tasks(),3,delayed):
            consumed+=1; results.append(result)
    assert sorted(results)==list(range(15)) and results[0]!=0
    with ThreadPoolExecutor(max_workers=2) as pool:
        with pytest.raises(RuntimeError,match='deliberate'): list(bounded_results(pool,[0,-1,2],2,delayed))


def test_incomplete_run_readable_after_exception(tmp_path,monkeypatch,capsys):
    import qec_bp_benchmark.runner.pipeline as pipeline
    config=write_config(tmp_path/'failure.yaml',tmp_path)
    real=pipeline.process_batch
    def failing(task):
        if task.batch_id==1: raise RuntimeError('test backend exception')
        return real(task)
    monkeypatch.setattr(pipeline,'process_batch',failing)
    with pytest.raises(RuntimeError,match='test backend exception'): pipeline.run_benchmark(config,verbose=True)
    output=capsys.readouterr()
    assert output.out==''
    assert 'Failed: RuntimeError: test backend exception' in output.err
    assert 'Committed batch 1/3' in output.err and 'Committed batch 2/3' not in output.err
    assert 'Complete:' not in output.err
    run=next((tmp_path/'runs').iterdir()); manifest=json.loads((run/'manifest.json').read_text())
    assert manifest['status']=='incomplete' and manifest['completed_batches']==1
    assert len(rows(run)[0])==2
    assert 'test backend exception' in (run/'logs/exception.txt').read_text()
    # Orphan paired files have no commit marker and are never exposed as a batch.
    inst=run/manifest['instances'][0]['directory']
    (inst/'samples/part-00000099.parquet').write_bytes(b'orphan')
    assert len(list(committed_batches(inst)))==1


def test_worker_spawn_exception_propagates(tmp_path):
    from concurrent.futures import ProcessPoolExecutor
    import multiprocessing
    from qec_bp_benchmark.runner.worker import initialize,process_batch
    from qec_bp_benchmark.runner.plan import BatchTask
    cfg=load_config(write_config(tmp_path/'spawn.yaml',tmp_path))
    task=BatchTask('absent',str(tmp_path/'missing'),'sampling',0,0,1,2**64-1)
    with ProcessPoolExecutor(max_workers=2,mp_context=multiprocessing.get_context('spawn'),
        initializer=initialize,initargs=(cfg.model_dump(mode='json'),{})) as executor:
        with pytest.raises(FileNotFoundError): executor.submit(process_batch,task).result()


def test_timing_boundary_pairing_and_optional_diagnostics(tmp_path,monkeypatch):
    from qec_bp_benchmark.runner import worker
    from qec_bp_benchmark.runner.plan import BatchTask
    from qec_bp_benchmark.artifacts import prepare_instance
    from qec_bp_benchmark.decoders import DecoderAdapter
    from qec_bp_benchmark.identity import sampling_identity
    import stim
    config_path=write_config(tmp_path/'instrumented.yaml',tmp_path,
        timing={'mode':'isolated_latency','profiling':'phases'},
        output={'root':str(tmp_path/'runs'),'retain_traces':True,'retain_corrections':True},
        sampling={'shots_per_point':2,'batch_size':2,'master_seed':91,'warmup_count':0})
    cfg=load_config(config_path)
    path=prepare_instance(cfg,'surface',3,.005)
    iid=json.loads((path/'instance.json').read_text())['scientific_instance_id']
    task=next(task_stream(((iid,str(path)),),cfg,sampling_identity(cfg,stim.__version__)))
    worker.initialize(cfg.model_dump(mode='json'),{'run_id':'test','source_hash':'test','config_hash':'test'})
    delivered=[]; real=DecoderAdapter.decode
    def spy(self,syndrome):
        delivered.append((self.identity,syndrome.copy()))
        time.sleep(.001) # Must appear in per-shot wall time, including service entry.
        return real(self,syndrome)
    monkeypatch.setattr(DecoderAdapter,'decode',spy)
    result=worker.process_batch(task)
    assert len(delivered)==6
    for i,sample in enumerate(result['samples']):
        selected=np.unpackbits(np.frombuffer(sample['detectors_packed'],dtype=np.uint8),bitorder='little')[:sample['num_detectors']]
        assert all(np.array_equal(s,selected) for _,s in delivered[3*i:3*i+3])
    for row in result['decodes']:
        assert row['wall_ns']>=1_000_000 and row['profiling']=='phases'
        phases=json.loads(row['phases_json']); assert phases['validation_prediction_cost_wall_ns']>=0
        if row['status']=='SUCCESS': assert row['correction_packed'] is not None
        if row['decoder_profile']=='screened_reference': assert row['diagnostics_json'] is not None


def test_atomic_second_shard_failure_leaves_no_commit(runs,tmp_path,monkeypatch):
    import qec_bp_benchmark.storage as storage
    _,one,_,_=runs; samples,decodes=rows(one)
    samples=[r for r in samples if r['batch_id']==0]; decodes=[r for r in decodes if r['batch_id']==0]
    ids=tuple(sorted({r['decoder_id'] for r in decodes}))
    instance=tmp_path/'atomic'; instance.mkdir()
    real=storage.os.link
    def fail_second(source,destination):
        if Path(destination).parent.name=='decodes': raise OSError('second shard interrupted')
        return real(source,destination)
    monkeypatch.setattr(storage.os,'link',fail_second)
    with pytest.raises(OSError,match='second shard'): commit_batch(instance,0,samples,decodes,ids,'zstd',{})
    assert not list(committed_batches(instance))
    assert (instance/'samples/part-00000000.parquet').exists()
    with pytest.raises(FileExistsError): commit_batch(instance,0,samples,decodes,ids,'zstd',{})


def test_preserved_source_bytes_and_dirty_patch(runs):
    import hashlib
    import zipfile
    _,one,_,_=runs
    hashes=json.loads((one/'source_provenance/source_hashes.json').read_text())
    with zipfile.ZipFile(one/'source_provenance/sources.zip') as archive:
        for name,expected in hashes.items(): assert hashlib.sha256(archive.read(name)).hexdigest()==expected
        assert 'external_lib/ldpc/src_cpp/reference_bp.hpp' in archive.namelist()
        assert 'external_lib/ldpc/src_python/ldpc/reference_bp/bindings.cpp' in archive.namelist()
        assert 'analysis/statistics.py' in archive.namelist()
        assert 'notebook/benchmark_analysis.ipynb' in archive.namelist()
        assert 'src/qec_bp_benchmark/native/search.hpp' in archive.namelist()
        assert 'src/qec_bp_benchmark/runner/pipeline.py' in archive.namelist()
        assert len(archive.read('external_lib/patches/ldpc.patch'))>0
    # The opt-in extension is untracked: git diff HEAD can correctly be empty.
    # Both its source bytes and the audited patch including new files are retained.
    env=json.loads((one/'environment.json').read_text())
    assert hashlib.sha256((one/'source_provenance/ldpc.patch').read_bytes()).hexdigest()==env['repositories']['ldpc']['patch_sha256']


def test_replay_committed_subset_of_incomplete_run(runs,tmp_path):
    import shutil
    _,one,_,_=runs
    source=tmp_path/'interrupted'; shutil.copytree(one,source)
    manifest=json.loads((source/'manifest.json').read_text()); manifest['status']='incomplete'
    atomic_json(source/'manifest.json',manifest)
    instance=source/manifest['instances'][0]['directory']
    (instance/'batch_manifests/part-00000001.json').unlink()
    config=write_config(tmp_path/'replay_partial.yaml',tmp_path)
    replay=run_benchmark(config,replay_source=source)
    assert len(rows(replay)[0])==3 # offsets 0,1 and 4; incomplete hole preserved
    assert json.loads((replay/'manifest.json').read_text())['status']=='complete'


def test_affinity_and_oversubscription_in_isolated_process():
    import subprocess,sys
    script='''
import os
from qec_bp_benchmark.config import Config
from qec_bp_benchmark.runner import configure_execution
available=sorted(os.sched_getaffinity(0))
config=Config(noise={'rates':[.001]},execution={'workers':2,'affinity':[available[0]]})
result=configure_execution(config)
assert result['affinity']==[available[0]] and result['oversubscribed']
assert set(result['thread_environment'].values())=={'1'}
try:
    configure_execution(Config(noise={'rates':[.001]},execution={'affinity':[max(available)+1]}))
except ValueError:
    pass
else:
    raise AssertionError('out-of-range affinity accepted')
'''
    subprocess.run([sys.executable,'-c',script],check=True)
