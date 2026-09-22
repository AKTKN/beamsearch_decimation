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
    """Process one bounded physical batch with unchanged paired decoder scheduling."""
    import numpy as np
    from ..storage import failure_labels
    from ..storage.minimal import minimal_record
    from ..provenance import timer_diagnostics
    from threadpoolctl import threadpool_info
    assert _CONFIG is not None and _CONTEXT is not None
    benchmark = bool(_CONTEXT.get("simulation_benchmark"))
    benchmark_total_start = time.perf_counter_ns() if benchmark else 0
    benchmark_phases: dict[str, int] = {}

    def add_phase(name: str, started_ns: int) -> None:
        if benchmark:
            benchmark_phases[name] = (
                benchmark_phases.get(name, 0) + time.perf_counter_ns() - started_ns
            )

    phase_start = time.perf_counter_ns() if benchmark else 0
    (problem,circuit,selected,metadata,decoders),hit,setup_cpu,setup_wall=_prepared(task)
    add_phase("worker_model_setup", phase_start)
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
    if benchmark:
        benchmark_phases["warmup"] = warm_wall
    start=time.perf_counter_ns()
    if task.replay_samples:
        raise ValueError("saved-sample replay is legacy-only")
    syndromes,truths=sample_physical(circuit,selected,task.count,task.seed)
    sample_wall=time.perf_counter_ns()-start
    if benchmark:
        benchmark_phases["physical_sampling"] = sample_wall
    phase_start = time.perf_counter_ns() if benchmark else 0
    results=[]
    add_phase("batch_metadata", phase_start)
    for local,(syndrome,truth) in enumerate(zip(syndromes,truths)):
        phase_start = time.perf_counter_ns() if benchmark else 0
        index=task.offset+local
        shot_id=f'{task.instance_id}:{task.sampling_id}:{index}'
        rotate=index%len(decoders)
        order=decoders[rotate:]+decoders[:rotate]
        add_phase("shot_input_preparation", phase_start)
        for position,decoder in enumerate(order):
            # Both timers enclose the entire same service; no sampling or labels.
            cpu_start=time.process_time_ns(); wall_start=time.perf_counter_ns()
            result=decoder.decode(syndrome)
            wall_ns=time.perf_counter_ns()-wall_start; cpu_ns=time.process_time_ns()-cpu_start
            if benchmark:
                benchmark_phases["decoding"] = benchmark_phases.get("decoding", 0) + wall_ns
            phase_start = time.perf_counter_ns() if benchmark else 0
            prediction=None if result.prediction is None else result.prediction.astype(bool).tolist()
            labels=failure_labels(result.status,result.syndrome_valid,prediction,truth,version=2)
            record=minimal_record(dict(shot_id=shot_id,decoder_name=decoder.config.name,
                decoder_profile=decoder.config.profile,status=result.status,
                syndrome_valid=result.syndrome_valid,valid_logical_mismatch=labels['valid_logical_mismatch'],
                wall_ns=wall_ns,osd_called=result.osd_called,
                correction_by_search=result.correction_by_search))
            results.append(record)
            add_phase("result_normalization", phase_start)
    phase_start = time.perf_counter_ns() if benchmark else 0
    info=threadpool_info()
    if any(pool['num_threads']!=1 for pool in info): raise RuntimeError('effective numerical thread limit is not one')
    add_phase("threadpool_verification", phase_start)
    if benchmark:
        measured = sum(benchmark_phases.values())
        benchmark_phases["worker_unattributed"] = max(
            0, time.perf_counter_ns() - benchmark_total_start - measured
        )
    return {'task':task,'results':results,
        'decoder_ids':tuple(d.identity for d in decoders),
        'progress':{'family':metadata['family'],'distance':metadata['distance'],'physical_p':metadata['p']},
        'simulation_timings':benchmark_phases if benchmark else None,
        'setup':{'cache_hit':hit,'setup_cpu_ns':setup_cpu,'setup_wall_ns':setup_wall,
                 'warmup_seed':warm_seed,'warmup_count':_CONFIG.sampling.warmup_count,'warmup_wall_ns':warm_wall,
                 'sampling_wall_ns':sample_wall,'cache_entries':len(_CACHE),'threadpools':info,
                 'execution':_CONTEXT['execution'],'timer_diagnostics':timer_diagnostics()}}
