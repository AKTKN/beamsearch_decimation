"""Truth-free SEARCH-BP-2.1 adapter and six-field paired simulator integration."""
import inspect
import itertools
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pyarrow.parquet as pq
import pytest
import stim
import yaml
from pydantic import ValidationError

from qec_bp_benchmark import _native
from qec_bp_benchmark.config import Config, SearchBP
from qec_bp_benchmark.decoders import DecoderAdapter
from qec_bp_benchmark.dem.model import convert_dem
from qec_bp_benchmark.runner import worker
from qec_bp_benchmark.runner.pipeline import run_benchmark
from qec_bp_benchmark.runner.plan import BatchTask
from qec_bp_benchmark.storage.minimal import SCHEMA
from analysis.simple_search_bp import summarize_run

ROOT=Path(__file__).resolve().parents[1]


def config(**overrides):
    return SearchBP(algorithm_version='SEARCH-BP-2.1', **overrides)


@pytest.mark.parametrize('overrides',[
    {'search':{'max_fixations':5}}, {'search':{'local_variable_policy':'fixed_root','max_fixations':5}},
    {'search':{'selected_checks':0}}, {'search':{'local_variables':2**31}},
    {'search':{'max_cycles':-1}}, {'search':{'guidance_strength':float('inf')}},
    {'search':{'beta':-1.}}, {'admission':{'k_run':1,'k_keep':2}},
    {'admission':{'k_run':True}}, {'bp':{'history_window':0}},
    {'bp':{'history_window':21}}, {'bp':{'average_llr_clip':float('nan')}},
    {'bp':{'average_llr_clip':float.fromhex('0x1.fffffffffffffp+1023')}},
    {'bp':{'scaling_factor':0.}}, {'bp':{'scaling_factor':1.1}}, {'native_threads':2},
    {'search':{'expansions_per_cycle':8}}, {'search':{'det_beam':2}},
    {'search':{'guidance_selection':'best'}}, {'search':{'retention_score':'old'}},
    {'search':{'max_generated_nodes':100}}, {'fallback':{'osd_order':0}},
    {'numerics':{'fast_math':False}},
])
def test_strict_native_settings_reject_invalid_and_removed_fields(overrides):
    with pytest.raises(ValidationError): config(**overrides)


def test_every_algorithm_setting_reaches_native_and_no_truth(monkeypatch):
    import qec_bp_benchmark.decoders as adapters
    captured={}
    class NativeSpy:
        def __init__(self, h,n,p,a,s):
            captured.update(h=h,n=n,p=p,a=a,settings=s)
        def decode(self,syndrome):
            captured['syndrome']=syndrome
            return SimpleNamespace(valid=True, correction=[0], osd_called=False,
                                   correction_by_search=False)
    monkeypatch.setattr(adapters,'native_hybrid',lambda:SimpleNamespace(SearchBP2Settings=_native.SearchBP2Settings,SearchBP2Decoder=NativeSpy))
    monkeypatch.setattr(adapters,'implementation_identity',lambda kind:{'test':kind})
    cfg=config(bp={'initial_iterations':7,'candidate_iterations':9,'history_window':3,'average_llr_clip':4.,'scaling_factor':.6},
               search={'selected_checks':3,'local_variables':5,'max_fixations':3,'max_cycles':4,
                       'beta':2.,'guidance_strength':.4,'local_variable_policy':'fixed_root'},
               admission={'k_run':7,'k_keep':3})
    problem=convert_dem(stim.DetectorErrorModel('error(0.1) D0 L0'))
    adapter=DecoderAdapter(problem,cfg)
    expected=dict(initial_iterations=7,candidate_iterations=9,history_window=3,history_clip=4.,scaling_factor=.6,
                  selected_checks=3,local_variables=5,max_fixations=3,max_cycles=4,beta=2.,guidance_strength=.4,
                  local_variable_policy='fixed_root',k_run=7,k_keep=3,osd_fallback=True)
    assert {k:getattr(captured['settings'],k) for k in expected}==expected
    assert list(inspect.signature(adapter.decode).parameters)==['syndrome']
    assert adapter.decode(np.array([0])).status=='SUCCESS'
    assert captured['syndrome']==[0]
    with pytest.raises(TypeError): adapter.decode([0],truth=[0])
    with pytest.raises(ValueError): DecoderAdapter(problem,cfg,profiling=True)
    with pytest.raises(ValueError): DecoderAdapter(problem,cfg,diagnostics=True)


def test_adapter_real_backend_reset_empty_shapes_and_exact_flag():
    problem=convert_dem(stim.DetectorErrorModel('error(0.1) D0 D1 L0\nerror(0.2) D1 D2\nerror(0.3) D0 D2 L1'))
    cfg=config(bp={'initial_iterations':2,'candidate_iterations':2,'history_window':2,'scaling_factor':.75})
    adapter=DecoderAdapter(problem,cfg)
    original=(problem.H.data.copy(),problem.A.data.copy(),problem.probabilities.copy())
    for bits in itertools.product((0,1),repeat=3):
        s=np.array(bits,dtype=np.uint8)
        result=adapter.decode(s)
        fresh=DecoderAdapter(problem,cfg).decode(s)
        assert result.status==fresh.status and result.osd_called is fresh.osd_called
        assert type(result.osd_called) is bool
        assert type(result.correction_by_search) is bool
        assert np.array_equal(result.correction,fresh.correction)
        assert tuple(s)==bits
        if result.status=='SUCCESS':
            assert np.array_equal(problem.H@result.correction%2,s)
            assert np.array_equal(problem.A@result.correction%2,result.prediction)
    assert all(np.array_equal(a,b) for a,b in zip(original,(problem.H.data,problem.A.data,problem.probabilities)))
    empty=convert_dem(stim.DetectorErrorModel('detector D0\nlogical_observable L11'))
    decoder=DecoderAdapter(empty,cfg)
    assert decoder.decode([0]).prediction.tolist()==[0]*12
    assert decoder.decode([0]).osd_called is False
    invalid=decoder.decode([1])
    assert invalid.status=='DECLARED_FAILURE' and invalid.osd_called is True


def test_adapter_independent_validation_and_missing_flag():
    problem=convert_dem(stim.DetectorErrorModel('error(0.1) D0 L0'))
    adapter=DecoderAdapter(problem,config())
    class Backend:
        def decode(self,syndrome):
            return SimpleNamespace(valid=True,correction=[0],prediction=[0],osd_called=True,
                                   correction_by_search=False)
    adapter._native=Backend()
    result=adapter.decode([1])
    assert result.status=='INVALID_OUTPUT' and not result.syndrome_valid
    assert result.prediction is None and result.osd_called is True
    class Missing:
        def decode(self,syndrome): return SimpleNamespace(valid=False,correction=[],osd_called=None)
    adapter._native=Missing()
    with pytest.raises(ValueError,match='exact boolean'): adapter.decode([1])


@pytest.mark.parametrize('family,distance,observables', [('surface',3,1), ('bb72',6,12)])
def test_physical_models_deterministic_corrections_and_shot_reset(tmp_path, family, distance, observables):
    from qec_bp_benchmark.artifacts import prepare_instance, load_problem
    data=yaml.safe_load((ROOT/'config/search_bp.yaml.example').read_text())
    data['circuit']['cache']=str(tmp_path/'cache')
    cfg=Config.model_validate(data)
    problem=load_problem(prepare_instance(cfg,family,distance,.003))
    assert problem.A.shape[0]==observables
    adapter=DecoderAdapter(problem,cfg.decoders[0])
    zero=np.zeros(problem.H.shape[0],dtype=np.uint8)
    rng=np.random.default_rng(20260922)
    syndromes=[zero]
    # Deterministic algebraic test inputs on physical H; no simulation or truth.
    for count in (1,3,7):
        error=np.zeros(problem.H.shape[1],dtype=np.uint8)
        error[rng.choice(len(error),count,replace=False)]=1
        syndromes.append(np.asarray(problem.H@error%2,dtype=np.uint8))
    for syndrome in syndromes:
        result=adapter.decode(syndrome)
        adapter.decode(syndromes[-1])
        adapter.decode(zero)
        repeated=adapter.decode(syndrome)
        fresh=DecoderAdapter(problem,cfg.decoders[0]).decode(syndrome)
        for other in (repeated,fresh):
            assert other.status==result.status and other.osd_called is result.osd_called
            assert other.correction_by_search is result.correction_by_search
            assert np.array_equal(other.correction,result.correction)
            assert np.array_equal(other.prediction,result.prediction)
        assert type(result.osd_called) is bool
        assert type(result.correction_by_search) is bool
        if result.status=='SUCCESS':
            assert np.array_equal(problem.H@result.correction%2,syndrome)
            assert np.array_equal(problem.A@result.correction%2,result.prediction)
            assert len(result.prediction)==observables


def test_worker_pairs_shots_labels_failures_and_complete_service_latency(monkeypatch):
    from qec_bp_benchmark.decoders import DecodeResult
    from qec_bp_benchmark.storage import failure_labels
    ticks=[0]
    monkeypatch.setattr(worker.time,'perf_counter_ns',lambda:ticks[0])
    monkeypatch.setattr(worker.time,'process_time_ns',lambda:ticks[0])
    import qec_bp_benchmark.provenance as provenance
    import threadpoolctl
    monkeypatch.setattr(provenance,'timer_diagnostics',lambda:{})
    monkeypatch.setattr(threadpoolctl,'threadpool_info',lambda:[])
    syndromes=np.array([[0],[1],[0],[1]],dtype=np.uint8)
    truths=np.array([[0],[0],[1],[1]],dtype=np.uint8)
    calls=[]
    class Spy:
        def __init__(self,name,profile,opaque=False):
            self.identity=name;self.config=SimpleNamespace(name=name,profile=profile);self.index=0;self.opaque=opaque
        def decode(self,syndrome):
            i=self.index;self.index+=1
            calls.append((i,self.config.name,id(syndrome),syndrome.copy()))
            ticks[0]+=11  # native work
            if i==2:
                ticks[0]+=7  # service handles failure before returning
                return DecodeResult(None,None,False,'DECLARED_FAILURE','FAIL',None,
                                    osd_called=None if self.opaque else True,
                                    correction_by_search=None if self.opaque else False)
            ticks[0]+=7  # final service validation/prediction
            prediction=np.array([int(syndrome[0])],dtype=np.uint8)
            return DecodeResult(prediction,prediction,True,'SUCCESS','OK',0.,
                                osd_called=None if self.opaque else bool(i%2),
                                correction_by_search=None if self.opaque else i == 0)
    decoders=[Spy('search_bp','search_bp'),Spy('opaque','opaque',True)]
    problem=SimpleNamespace(H=SimpleNamespace(shape=(1,1)))
    monkeypatch.setattr(worker,'_prepared',lambda task:((problem,None,[0],{'family':'surface','distance':3,'p':.003},decoders),False,0,0))
    def sample(circuit,selected,count,seed):
        assert count==4 and seed==123
        ticks[0]+=1000  # sampling must not enter per-decoder latency
        return syndromes,truths
    monkeypatch.setattr(worker,'sample_physical',sample)
    cfg=Config.model_validate({'noise':{'rates':[.003]},'sampling':{'warmup_count':0}})
    monkeypatch.setattr(worker,'_CONFIG',cfg)
    monkeypatch.setattr(worker,'_CONTEXT',{'execution':{}})
    def compare(*args,**kwargs):
        ticks[0]+=2000 # truth comparison is outside the timed decoder service
        return failure_labels(*args,**kwargs)
    import qec_bp_benchmark.storage as storage
    monkeypatch.setattr(storage,'failure_labels',compare)
    out=worker.process_batch(BatchTask('instance','unused','sampling',0,0,4,123))
    assert 'samples' not in out and 'decodes' not in out and 'hybrid_rounds' not in out
    rows=out['results'];assert len(rows)==8
    for i in range(4):
        pair=[c for c in calls if c[0]==i]
        assert len(pair)==2 and pair[0][2]==pair[1][2]
        assert np.array_equal(pair[0][3],syndromes[i]) and np.array_equal(pair[1][3],syndromes[i])
        shot=[r for r in rows if r['shot_id']==f'instance:sampling:{i}']
        assert len(shot)==2
        assert all(r['logical_error']==[False,True,True,False][i] for r in shot)
        assert all(r['latency_ns']==18 and set(r)==set(SCHEMA.names) for r in shot)
    assert [r['osd_called'] for r in rows if r['decoder_name']=='search_bp']==[False,True,True,True]
    assert [r['correction_by_search'] for r in rows if r['decoder_name']=='search_bp']==[True,False,False,False]
    assert all(r['osd_called'] is None for r in rows if r['decoder_name']=='opaque')
    assert all(r['correction_by_search'] is None for r in rows if r['decoder_name']=='opaque')


def test_paired_search_bp_smoke_single_and_multi_worker(tmp_path):
    data=yaml.safe_load((ROOT/'config/search_bp.yaml.example').read_text())
    data['experiment']['codes']=[{'family':'surface','distances':[3]},{'family':'bb72','distances':[6]}]
    data['sampling'].update(shots_per_point=4,batch_size=2,warmup_count=1)
    data['noise']['rates']=[.003]
    data['output']['root']=str(tmp_path/'runs')
    data['output']['parquet']['shots_per_flush']=3
    data['circuit']['cache']=str(tmp_path/'cache')
    data['decoders'][2]={'profile':'bposd_ms30_cs0'}
    path=tmp_path/'config.yaml'
    runs=[]
    for count in (1,2):
        data['execution']={'workers':count}
        path.write_text(yaml.safe_dump(data))
        run=run_benchmark(path);runs.append(run)
        assert {p.name for p in run.iterdir()}=={'config_resolved.json','data'}
        files=sorted((run/'data').iterdir())
        assert len(files)==2 and all(p.name.endswith('_results.parquet') for p in files)
        for file in files:
            parquet=pq.ParquetFile(file)
            assert parquet.schema_arrow.equals(SCHEMA,check_metadata=True)
            assert parquet.metadata.num_rows==12 and parquet.metadata.num_row_groups==2
            rows=parquet.read().to_pylist()
            assert len({(r['shot_id'],r['decoder_name']) for r in rows})==12
            assert all(r['latency_ns']>=0 for r in rows)
            assert all(type(r['osd_called']) is bool and
                       type(r['correction_by_search']) is bool
                       for r in rows if r['decoder_name']=='search_bp')
            for shot in {r['shot_id'] for r in rows}:
                assert {r['decoder_name'] for r in rows if r['shot_id']==shot}=={'search_bp','beam8','bposd_ms30_cs0'}
        summaries=summarize_run(run)
        assert len(summaries)==6 and all(s['shots']==4 for s in summaries)
        assert all(s['decode_time']['p99_ns']>=0 and s['osd_call_fraction']['denominator']==4 for s in summaries)
    def scientific(run):
        return sorted(json.dumps({k:v for k,v in r.items() if k!='latency_ns'},sort_keys=True)
                      for file in (run/'data').glob('*.parquet') for r in pq.read_table(file).to_pylist())
    assert scientific(runs[0])==scientific(runs[1])
    # Reader preserves earlier five-field filenames without rewriting their data.
    for file in (runs[0]/'data').glob('*_results.parquet'):
        file.rename(file.with_name(file.name.replace('_results.parquet','_logicalerror.parquet')))
    assert len(summarize_run(runs[0]))==6
