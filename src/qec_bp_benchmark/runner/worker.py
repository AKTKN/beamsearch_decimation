"""Spawn-worker service; every native object and bounded cache stays process-local."""
from __future__ import annotations
from collections import OrderedDict
import json
from pathlib import Path
import time
from typing import TYPE_CHECKING
from ..config import Config
from . import configure_execution
from .plan import BatchTask,batch_seed

if TYPE_CHECKING:
    import numpy as np
    import stim
    from numpy.typing import NDArray

_CONFIG=None
_CONTEXT=None
_CACHE=OrderedDict()
_THREAD_LIMIT=None


def initialize(config_data: dict, context: dict) -> None:
    """Worker initializer receives JSON-safe metadata, never a native object."""
    global _CONFIG,_CONTEXT,_CACHE,_THREAD_LIMIT
    _CONFIG=Config.model_validate(config_data)
    execution=configure_execution(_CONFIG)
    import numpy  # noqa: F401 -- pools must exist before controlling already-loaded libraries
    import scipy.linalg  # noqa: F401
    from threadpoolctl import threadpool_limits
    _THREAD_LIMIT=threadpool_limits(limits=1)
    _CONTEXT=dict(context,execution=execution)
    _CACHE=OrderedDict()


def _prepared(task: BatchTask):
    from ..artifacts import load_problem
    from ..decoders import DecoderAdapter
    from ..identity import content_hash
    import stim
    key=(task.instance_id,content_hash([d.model_dump() for d in _CONFIG.decoders]),
         _CONFIG.output.retain_traces,_CONFIG.timing.profiling)
    if key in _CACHE:
        _CACHE.move_to_end(key); return _CACHE[key],True,0,0
    cpu=time.process_time_ns(); wall=time.perf_counter_ns()
    path=Path(task.artifact); problem=load_problem(path)
    mapping=json.loads((path/'detector_mapping.json').read_text())
    metadata=json.loads((path/'instance.json').read_text())
    decoders=[DecoderAdapter(problem,d,diagnostics=_CONFIG.output.retain_traces,
                            profiling=_CONFIG.timing.profiling=='phases') for d in _CONFIG.decoders if d.enabled]
    decoders.sort(key=lambda d:d.identity) # stable across YAML decoder reordering
    if len({d.identity for d in decoders})!=len(decoders): raise ValueError('duplicate semantic decoder configurations')
    value=(problem,stim.Circuit((path/'circuit.stim').read_text()),mapping['selected_to_full'],metadata,decoders)
    _CACHE[key]=value
    if len(_CACHE)>_CONFIG.execution.worker_cache_size: _CACHE.popitem(last=False)
    return value,False,time.process_time_ns()-cpu,time.perf_counter_ns()-wall


def sample_physical(circuit: stim.Circuit, selected: list[int], count: int,
                    seed: int) -> tuple[NDArray[np.bool_],NDArray[np.bool_]]:
    """One physical Stim sampling call, then project detectors; retain all truth columns."""
    detectors,truth=circuit.compile_detector_sampler(seed=seed).sample(shots=count,separate_observables=True)
    return detectors[:,selected].copy(),truth.copy()


def process_batch(task: BatchTask) -> dict:
    """Return one batch of paired rows; all exceptions propagate with remote traceback."""
    import numpy as np
    from ..identity import content_hash
    from ..storage import failure_labels,sha256
    from ..storage.schema import COMMON,DECODES_V2 as DECODES
    from ..provenance import timer_diagnostics
    from threadpoolctl import threadpool_info
    (problem,circuit,selected,metadata,decoders),hit,setup_cpu,setup_wall=_prepared(task)
    assert _CONFIG is not None and _CONTEXT is not None
    warm_start=time.perf_counter_ns()
    warm_seed=batch_seed(_CONFIG.sampling.warmup_seed,task.instance_id,task.batch_id,'warmup')
    if _CONFIG.sampling.warmup_count:
        warm,_=sample_physical(circuit,selected,_CONFIG.sampling.warmup_count,warm_seed)
        for s in warm:
            for decoder in decoders: decoder.decode(s)
        # Published per-call reset is the same path used by measured shots. Exercise
        # the zero path after warmup; no mutable history enters the next decode.
        for decoder in decoders: decoder.decode(np.zeros(problem.H.shape[0],dtype=np.uint8))
    warm_wall=time.perf_counter_ns()-warm_start
    start=time.perf_counter_ns()
    replay=None
    if task.replay_samples:
        import pyarrow.parquet as pq
        if sha256(Path(task.replay_samples))!=task.replay_sha256: raise ValueError('replay sample checksum changed')
        replay=pq.read_table(task.replay_samples).to_pylist()
        if len(replay)!=task.count: raise ValueError('replay count mismatch')
        syndromes=np.array([np.unpackbits(np.frombuffer(row['detectors_packed'],dtype=np.uint8),bitorder='little')[:row['num_detectors']] for row in replay],dtype=np.uint8)
        truths=[row['actual_observables'] for row in replay]
    else: syndromes,truths=sample_physical(circuit,selected,task.count,task.seed)
    sample_wall=time.perf_counter_ns()-start
    common={'run_id':_CONTEXT['run_id'],'instance_id':task.instance_id,'sampling_id':task.sampling_id,
        'batch_id':task.batch_id,'batch_seed':task.seed,'family':metadata['family'],'distance':metadata['distance'],
        'n':metadata['n'],'k_Z':metadata['k_Z'],'rounds':metadata['rounds'],'physical_p':metadata['p'],
        'noise_id':content_hash(metadata['noise']),'model_hash':content_hash(problem.hashes),
        'source_hash':_CONTEXT['source_hash'],'config_hash':_CONTEXT['config_hash']}
    samples=[]; results=[]; rounds=[]; phases=[]
    for local,(syndrome,truth) in enumerate(zip(syndromes,truths)):
        index=task.offset+local
        row=dict(common,shot_index=index,shot_id=f'{task.instance_id}:{task.sampling_id}:{index}',
            num_detectors=problem.H.shape[0],detectors_packed=np.packbits(syndrome,bitorder='little').tobytes(),
            actual_observables=[bool(b) for b in truth])
        if replay:
            original=replay[local]
            if any(original[k]!=row[k] for k in ('instance_id','sampling_id','shot_index','shot_id','batch_seed','detectors_packed','actual_observables','model_hash')):
                raise ValueError('replay physical identity mismatch')
        samples.append(row)
        shared={f.name:row[f.name] for f in COMMON}
        rotate=index%len(decoders)
        order=decoders[rotate:]+decoders[:rotate]
        for position,decoder in enumerate(order):
            # Both timers enclose the entire same service; no sampling or labels.
            cpu_start=time.process_time_ns(); wall_start=time.perf_counter_ns()
            result=decoder.decode(syndrome)
            wall_ns=time.perf_counter_ns()-wall_start; cpu_ns=time.process_time_ns()-cpu_start
            events=decoder.export_telemetry() if result.hybrid_summary is not None else None
            prediction=None if result.prediction is None else result.prediction.astype(bool).tolist()
            record={f.name:None for f in DECODES}
            record.update(shared,decoder_id=decoder.identity,decoder_name=decoder.config.name,
                decoder_profile=decoder.config.profile,execution_position=position,prediction=prediction,
                status=result.status,native_status=result.native_status,syndrome_valid=result.syndrome_valid,cost=result.cost,
                cpu_ns=cpu_ns,wall_ns=wall_ns,timing_mode=_CONFIG.timing.mode,
                concurrent_load=_CONFIG.timing.mode=='throughput' and _CONFIG.execution.workers>1,
                workers=_CONFIG.execution.workers,native_threads=1,blas_threads=1,
                oversubscribed=_CONTEXT['execution']['oversubscribed'],profiling=_CONFIG.timing.profiling)
            record.update(failure_labels(result.status,result.syndrome_valid,prediction,truth,version=2))
            record.update(result.counters)
            if _CONFIG.output.retain_corrections and result.correction is not None:
                record['correction_packed']=np.packbits(result.correction,bitorder='little').tobytes()
            if result.diagnostics is not None: record['diagnostics_json']=json.dumps(result.diagnostics,allow_nan=False)
            if result.phases is not None: record['phases_json']=json.dumps(result.phases,allow_nan=False)
            from ..storage.telemetry import attach_telemetry
            rr,pp=attach_telemetry(record,result.hybrid_summary,events)
            rounds.extend(rr); phases.extend(pp)
            results.append(record)
    info=threadpool_info()
    if any(pool['num_threads']!=1 for pool in info): raise RuntimeError('effective numerical thread limit is not one')
    return {'task':task,'samples':samples,'decodes':results,'hybrid_rounds':rounds,'decoder_phases':phases,'decoder_ids':tuple(d.identity for d in decoders),
        'setup':{'cache_hit':hit,'setup_cpu_ns':setup_cpu,'setup_wall_ns':setup_wall,
                 'warmup_seed':warm_seed,'warmup_count':_CONFIG.sampling.warmup_count,'warmup_wall_ns':warm_wall,
                 'sampling_wall_ns':sample_wall,'cache_entries':len(_CACHE),'threadpools':info,
                 'execution':_CONTEXT['execution'],'timer_diagnostics':timer_diagnostics()}}
