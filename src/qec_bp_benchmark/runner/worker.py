"""Spawn-worker service; every native object and bounded cache stays process-local."""
from __future__ import annotations
from collections import OrderedDict
import json
from pathlib import Path
import time
from typing import TYPE_CHECKING
from ..config import Config, SearchBPOutput
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
_STREAM_QUEUE=None


def _append_row(columns: dict[str, list], row: dict) -> None:
    for name in columns:
        columns[name].append(row[name])


def _extend_columns(target: dict[str, list], source: dict[str, list]) -> None:
    if set(target) != set(source):
        raise ValueError("column sets differ")
    for name, values in source.items():
        target[name].extend(values)


def _event_columns(dataset: str, source: dict[str, list], key: dict) -> dict[str, list]:
    """Complete native-owned columns with storage keys and nullable fields."""
    from ..storage.search_bp_schema import column_count, empty_columns
    count = column_count(source)
    columns = empty_columns(dataset)
    unknown = set(source) - set(columns)
    if unknown:
        raise ValueError(f"unexpected native {dataset} columns: {sorted(unknown)}")
    for name, values in source.items():
        columns[name] = values
    for name, value in key.items():
        columns[name] = [value] * count
    for name, values in tuple(columns.items()):
        if not values and count:
            columns[name] = [None] * count
    return columns


def _frontier_decode_columns(*, run_id: str, condition_id: str, shot_id: int,
                             batch_id: int, worker_id: int, decoder, position: int,
                             result, events: dict | None, truth, cpu_ns: int,
                             wall_ns: int, timing) -> dict[str, dict[str, list]]:
    """Normalize one invocation directly into Arrow-compatible columns."""
    import hashlib
    import struct
    from ..storage.search_bp_schema import SCHEMAS, column_count, empty_columns, pack_bits
    names = set(SCHEMAS) - {"conditions", "decoder_profiles", "shot_inputs"}
    tables = {name: empty_columns(name) for name in names}
    key = {"run_id": run_id, "condition_id": condition_id, "shot_id": shot_id,
           "decoder_id": decoder.identity}
    correction = None if result.correction is None else pack_bits(result.correction)
    prediction = None if result.prediction is None else pack_bits(result.prediction)
    truth_values = [bool(value) for value in truth]
    mismatch_values = None if result.prediction is None else [bool(a) != b for a, b in zip(result.prediction, truth_values)]
    summary = result.frontier_summary
    status = (summary["status"] if summary is not None else
              "valid" if result.syndrome_valid else
              "nonconverged" if result.status == "DECLARED_FAILURE" else "adapter_error")
    def blank(dataset: str) -> dict:
        return {field.name: None for field in SCHEMAS[dataset]}
    record = blank("decode_results")
    record.update(key, storage_batch_id=batch_id, worker_id=worker_id, execution_position=position,
        status=status, native_status=result.native_status, syndrome_valid=result.syndrome_valid,
        correction_packed=correction, predicted_observables_packed=prediction,
        observable_mismatch_packed=None if mismatch_values is None else pack_bits(mismatch_values),
        logical_mismatch=None if mismatch_values is None else any(mismatch_values),
        block_failure=not result.syndrome_valid or bool(mismatch_values and any(mismatch_values)),
        physical_cost=result.cost,
        first_solution_source=None if summary is None else summary["first_solution_source"],
        winner_source=None if summary is None else summary["winner_source"],
        first_solution_event_id=None if summary is None else summary["first_solution_event_id"],
        winner_solution_event_id=None if summary is None else summary["winner_solution_event_id"],
        prefix_stop_reason="baseline_native" if summary is None else summary["prefix_stop_reason"],
        fallback_reason=None if summary is None or not summary["osd_entered"] else summary["prefix_stop_reason"],
        osd_entered=None if summary is None else summary["osd_entered"], service_cpu_ns=cpu_ns,
        service_wall_ns=wall_ns, timing_context_id=f"{timing.mode}:{timing.profiling}",
        timing_mode=timing.mode, profiling=timing.profiling,
        timing_accounting_ok=True if timing.profiling == "phases" else None)
    _append_row(tables["decode_results"], record)
    if summary is None:
        if timing.profiling == "phases":
            phase = blank("phase_timings"); phase.update(key, phase_row_id=0, phase="other",
                cycle_index=None, node_id=None, scope_count=1,
                exclusive_cpu_ns=cpu_ns, exclusive_wall_ns=wall_ns)
            _append_row(tables["phase_timings"], phase)
        return tables
    search = blank("search_summary"); search.update(key, **summary["search_summary"])
    _append_row(tables["search_summary"], search)
    bp = blank("bp_summary"); bp.update(key, **summary["bp_summary"])
    _append_row(tables["bp_summary"], bp)
    assert events is not None
    tables["cycles"] = _event_columns("cycles", events["cycles"], key)
    patterns = _event_columns("patterns", events["patterns"], key)
    for offset in range(column_count(patterns)):
        assignments = sorted([(index, 0) for index in patterns["fixed_zero_indices"][offset]] +
                             [(index, 1) for index in patterns["fixed_one_indices"][offset]])
        payload = b"".join(struct.pack("<IB", index, bit) for index, bit in assignments)
        patterns["pattern_sha256"][offset] = hashlib.sha256(payload).hexdigest()
    tables["patterns"] = patterns
    tables["bp_updates"] = _event_columns("bp_updates", events["bp_updates"], key)
    tables["bp_beam_membership"] = _event_columns(
        "bp_beam_membership", events["bp_beam_membership"], key
    )
    source = dict(events["solution_events"])
    corrections = source.pop("correction", [])
    predictions = source.pop("prediction", [])
    solutions = _event_columns("solution_events", source, key)
    for offset, (native_correction, native_prediction) in enumerate(zip(corrections, predictions)):
        packed_correction = pack_bits(native_correction); packed_prediction = pack_bits(native_prediction)
        event_mismatch = [bool(a) != b for a, b in zip(native_prediction, truth_values)]
        solutions["correction_packed"][offset] = packed_correction
        solutions["predicted_observables_packed"][offset] = packed_prediction
        solutions["correction_sha256"][offset] = hashlib.sha256(
            struct.pack("<Q", len(native_correction)) + packed_correction
        ).hexdigest()
        solutions["logical_mismatch"][offset] = any(event_mismatch)
        solutions["observable_mismatch_packed"][offset] = pack_bits(event_mismatch)
    tables["solution_events"] = solutions
    source = dict(events["osd_calls"])
    llr_values = source.pop("_llrs_for_digest", [])
    osd = _event_columns("osd_calls", source, key)
    for offset, llrs in enumerate(llr_values):
        event_id = osd["solution_event_id"][offset]
        logical = None
        if event_id is not None:
            logical = next(value for candidate, value in zip(
                solutions["solution_event_id"], solutions["logical_mismatch"]
            ) if candidate == event_id)
        payload = struct.pack("<Q", len(llrs)) + b"".join(struct.pack("<d", value) for value in llrs)
        osd["llr_sha256"][offset] = hashlib.sha256(payload).hexdigest()
        osd["osd_method"][offset] = "OSD_CS"; osd["osd_order"][offset] = 0
        osd["ordering"][offset] = "pinned_ldpc_signed_llr"
        osd["logical_mismatch"][offset] = logical
    tables["osd_calls"] = osd
    tables["search_nodes"] = _event_columns("search_nodes", events["search_nodes"], key)
    if timing.profiling == "phases":
        phases = _event_columns("phase_timings", events["phase_timings"], key)
        phase_count = column_count(phases)
        phases["phase_row_id"] = list(range(phase_count))
        native_cpu=sum(phases["exclusive_cpu_ns"]);native_wall=sum(phases["exclusive_wall_ns"])
        other_cpu=cpu_ns-native_cpu;other_wall=wall_ns-native_wall
        if other_cpu < 0 or other_wall < 0:
            raise ValueError("native exclusive phases exceed outer service time")
        row = blank("phase_timings"); row.update(key, phase_row_id=phase_count, phase="other",
            cycle_index=None, node_id=None, scope_count=1,
            exclusive_cpu_ns=other_cpu, exclusive_wall_ns=other_wall)
        _append_row(phases, row);tables["phase_timings"] = phases
        tables["decode_results"]["native_cpu_ns"][0]=native_cpu
        tables["decode_results"]["native_wall_ns"][0]=native_wall
    return tables


def initialize(config_data: dict, context: dict, stream_queue=None) -> None:
    """Worker initializer receives JSON-safe metadata, never a native object."""
    global _CONFIG,_CONTEXT,_CACHE,_THREAD_LIMIT,_STREAM_QUEUE
    _CONFIG=Config.model_validate(config_data)
    execution=configure_execution(_CONFIG)
    import numpy  # noqa: F401 -- pools must exist before controlling already-loaded libraries
    import scipy.linalg  # noqa: F401
    from threadpoolctl import threadpool_limits
    _THREAD_LIMIT=threadpool_limits(limits=1)
    _CONTEXT=dict(context,execution=execution)
    _CACHE=OrderedDict()
    _STREAM_QUEUE=stream_queue


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


def process_batch(task: BatchTask, chunk_sink=None) -> dict:
    """Process a batch, streaming each search_bp shot before the batch completes."""
    import numpy as np
    from ..identity import content_hash
    from ..storage import failure_labels,sha256
    from ..storage.schema import COMMON,DECODES_V2 as DECODES
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
    replay=None
    if task.replay_samples:
        import pyarrow.parquet as pq
        if sha256(Path(task.replay_samples))!=task.replay_sha256: raise ValueError('replay sample checksum changed')
        replay=pq.ParquetFile(task.replay_samples).read().to_pylist()
        if len(replay)!=task.count: raise ValueError('replay count mismatch')
        frontier_replay='syndrome_packed' in replay[0]
        if frontier_replay:
            syndromes=np.array([np.unpackbits(np.frombuffer(row['syndrome_packed'],dtype=np.uint8),bitorder='little')[:problem.H.shape[0]] for row in replay],dtype=np.uint8)
            truths=[np.unpackbits(np.frombuffer(row['true_observables_packed'],dtype=np.uint8),bitorder='little')[:problem.A.shape[0]].tolist() for row in replay]
        else:
            syndromes=np.array([np.unpackbits(np.frombuffer(row['detectors_packed'],dtype=np.uint8),bitorder='little')[:row['num_detectors']] for row in replay],dtype=np.uint8)
            truths=[row['actual_observables'] for row in replay]
    else: syndromes,truths=sample_physical(circuit,selected,task.count,task.seed)
    sample_wall=time.perf_counter_ns()-start
    if benchmark:
        benchmark_phases["physical_sampling"] = sample_wall
    phase_start = time.perf_counter_ns() if benchmark else 0
    common={'run_id':_CONTEXT['run_id'],'instance_id':task.instance_id,'sampling_id':task.sampling_id,
        'batch_id':task.batch_id,'batch_seed':task.seed,'family':metadata['family'],'distance':metadata['distance'],
        'n':metadata['n'],'k_Z':metadata['k_Z'],'rounds':metadata['rounds'],'physical_p':metadata['p'],
        'noise_id':content_hash(metadata['noise']),'model_hash':content_hash(problem.hashes),
        'source_hash':_CONTEXT['source_hash'],'config_hash':_CONTEXT['config_hash']}
    samples=[]; results=[]; rounds=[]; phases=[]
    frontier_tables = None
    frontier_output = isinstance(_CONFIG.output, SearchBPOutput)
    if frontier_output:
        from ..storage.search_bp_schema import SCHEMAS, empty_columns, pack_bits
        frontier_tables = {
            name: empty_columns(name)
            for name in set(SCHEMAS) - {"conditions", "decoder_profiles"}
        }
    emit = chunk_sink
    if emit is None and _STREAM_QUEUE is not None:
        emit = _STREAM_QUEUE.put
    import multiprocessing
    identity = multiprocessing.current_process()._identity
    worker_id = max(0, identity[0] - 1) if identity else 0
    add_phase("batch_metadata", phase_start)
    for local,(syndrome,truth) in enumerate(zip(syndromes,truths)):
        phase_start = time.perf_counter_ns() if benchmark else 0
        index=task.offset+local
        row=dict(common,shot_index=index,shot_id=f'{task.instance_id}:{task.sampling_id}:{index}',
            num_detectors=problem.H.shape[0],detectors_packed=np.packbits(syndrome,bitorder='little').tobytes(),
            actual_observables=[bool(b) for b in truth])
        if replay:
            original=replay[local]
            if 'syndrome_packed' in original:
                if (original['condition_id']!=task.instance_id or original['sampling_id']!=task.sampling_id or
                    original['shot_id']!=index or original['sampling_seed']!=task.seed or
                    original['syndrome_packed']!=row['detectors_packed']):
                    raise ValueError('frontier replay physical identity mismatch')
            elif any(original[k]!=row[k] for k in ('instance_id','sampling_id','shot_index','shot_id','batch_seed','detectors_packed','actual_observables','model_hash')):
                raise ValueError('replay physical identity mismatch')
        shot_tables = None
        if frontier_output:
            shot_tables = {
                name: empty_columns(name)
                for name in set(SCHEMAS) - {"conditions", "decoder_profiles"}
            }
            shot_input = {
                "run_id": _CONTEXT["run_id"], "condition_id": task.instance_id, "shot_id": index,
                "sampling_id": task.sampling_id, "sampling_batch_id": task.batch_id,
                "shot_in_sampling_batch": local, "sampling_seed": task.seed,
                "syndrome_packed": pack_bits(syndrome), "true_observables_packed": pack_bits(truth),
                "syndrome_weight": int(np.count_nonzero(syndrome)),
            }
            _append_row(shot_tables["shot_inputs"], shot_input)
        else:
            samples.append(row)
        shared=None if frontier_output else {f.name:row[f.name] for f in COMMON}
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
            has_events = result.hybrid_summary is not None or result.frontier_summary is not None
            events = (decoder.export_telemetry_columns() if frontier_output and has_events else
                      decoder.export_telemetry() if has_events else None)
            add_phase("telemetry_export", phase_start)
            phase_start = time.perf_counter_ns() if benchmark else 0
            if frontier_output:
                converted = _frontier_decode_columns(run_id=_CONTEXT["run_id"], condition_id=task.instance_id,
                    shot_id=index, batch_id=task.batch_id, worker_id=worker_id, decoder=decoder,
                    position=position, result=result, events=events, truth=truth, cpu_ns=cpu_ns,
                    wall_ns=wall_ns, timing=_CONFIG.timing)
                for name, values in converted.items():
                    _extend_columns(shot_tables[name], values)
            else:
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
            add_phase("result_normalization", phase_start)
        if frontier_output:
            message = {"condition_id": task.instance_id, "tables": shot_tables}
            phase_start = time.perf_counter_ns() if benchmark else 0
            if emit is not None:
                emit(message)
            else:
                for name, values in shot_tables.items():
                    _extend_columns(frontier_tables[name], values)
            add_phase("stream_delivery", phase_start)
    phase_start = time.perf_counter_ns() if benchmark else 0
    info=threadpool_info()
    if any(pool['num_threads']!=1 for pool in info): raise RuntimeError('effective numerical thread limit is not one')
    add_phase("threadpool_verification", phase_start)
    if benchmark:
        measured = sum(benchmark_phases.values())
        benchmark_phases["worker_unattributed"] = max(
            0, time.perf_counter_ns() - benchmark_total_start - measured
        )
    return {'task':task,'samples':samples,'decodes':results,'hybrid_rounds':rounds,'decoder_phases':phases,
        'frontier_tables':frontier_tables if emit is None else None,
        'decoder_ids':tuple(d.identity for d in decoders),
        'progress':{'family':metadata['family'],'distance':metadata['distance'],'physical_p':metadata['p']},
        'simulation_timings':benchmark_phases if benchmark else None,
        'setup':{'cache_hit':hit,'setup_cpu_ns':setup_cpu,'setup_wall_ns':setup_wall,
                 'warmup_seed':warm_seed,'warmup_count':_CONFIG.sampling.warmup_count,'warmup_wall_ns':warm_wall,
                 'sampling_wall_ns':sample_wall,'cache_entries':len(_CACHE),'threadpools':info,
                 'execution':_CONTEXT['execution'],'timer_diagnostics':timer_diagnostics()}}
