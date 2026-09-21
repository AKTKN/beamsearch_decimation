"""Bounded parent scheduler and run lifecycle; no decoder objects cross processes."""
from __future__ import annotations
from concurrent.futures import Executor,ProcessPoolExecutor,wait,FIRST_COMPLETED
from datetime import datetime,timezone
import json
import multiprocessing
from pathlib import Path
import shutil
import sys
import time
import traceback
import uuid
from typing import Callable,Iterable,Iterator,TypeVar
from ..config import load_config,require_available_decoder,Hybrid
from ..identity import content_hash,run_identity,sampling_identity
from ..storage import atomic_json,commit_batch,committed_batches,sha256
from . import configure_execution
from .plan import BatchTask,task_stream,SEED_RECIPE
from .worker import initialize,process_batch

TaskType=TypeVar('TaskType')
ResultType=TypeVar('ResultType')

def bounded_results(executor: Executor, tasks: Iterable[TaskType], limit: int,
                    function: Callable[[TaskType],ResultType]=process_batch) -> Iterator[ResultType]:
    """Lazy at most limit submitted/unconsumed tasks; cancel pending work on error."""
    if limit<1: raise ValueError('pending bound must be positive')
    iterator=iter(tasks); pending={}; exhausted=False
    try:
        while pending or not exhausted:
            while not exhausted and len(pending)<limit:
                try: task=next(iterator)
                except StopIteration: exhausted=True; break
                pending[executor.submit(function,task)]=task
            if not pending: break
            ready,_=wait(pending,return_when=FIRST_COMPLETED)
            for future in ready:
                del pending[future]
                yield future.result()
    finally:
        for future in pending: future.cancel()


def _copy_artifact(source: Path, destination: Path) -> dict:
    from ..artifacts import verify_artifact
    manifest=verify_artifact(source)
    destination.mkdir(exist_ok=False)
    # Copy only immutable artifact files; a replay source also contains batch output.
    for name in (*manifest['files'],'manifest.json'):
        target=destination/name; target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source/name,target)
    verify_artifact(destination)
    return manifest


def _replay_tasks(source: Path, destinations: dict[str,str]):
    manifest=json.loads((source/'manifest.json').read_text())
    for instance in manifest['instances']:
        original=source/instance['directory']
        for batch in committed_batches(original):
            name=f'samples/part-{batch["batch_id"]:08d}.parquet'
            yield BatchTask(instance['instance_id'],destinations[instance['instance_id']],batch['sampling_id'],
                batch['batch_id'],batch['offset'],batch['count'],batch['seed'],str(original/name),batch['files'][name]['sha256'])


def _update_summary(summary: dict, rows: list[dict]) -> None:
    """Counts only; Stage 6 statistical analysis/plotting is deliberately separate."""
    for row in rows:
        key=row['instance_id']+':'+row['decoder_id']
        item=summary.setdefault(key,{'instance_id':row['instance_id'],'decoder_id':row['decoder_id'],
            'shots':0,'decoding_failures':0,'valid_outputs':0,'valid_logical_mismatches':0,'block_failures':0,
            'observable_mismatches':[0]*row['k_Z'],'observable_total_failures':[0]*row['k_Z']})
        item['shots']+=1
        item['decoding_failures']+=int(row['decoding_failure'])
        item['valid_outputs']+=int(not row['decoding_failure'])
        item['valid_logical_mismatches']+=int(bool(row['valid_logical_mismatch']))
        item['block_failures']+=int(row['block_failure'])
        if row['observable_mismatch'] is not None:
            item['observable_mismatches']=[a+int(b) for a,b in zip(item['observable_mismatches'],row['observable_mismatch'])]
        item['observable_total_failures']=[a+int(b) for a,b in zip(item['observable_total_failures'],row['observable_total_failure'])]


def run_benchmark(config_path: str | Path, *, replay_source: str | Path | None=None,
                  verbose: bool=False) -> Path:
    """Execute finite YAML plan and return new run path, or propagate errors.

    Failure leaves manifest status=incomplete, a traceback and committed readable
    pairs. Replay uses the source's saved physical dataset (including committed
    subsets of incomplete runs); YAML controls decoders/execution/output only.
    verbose emits flushed parent-only lifecycle and committed-batch messages to
    stderr, outside per-shot decode timers. It changes no scientific settings.
    """
    config_path=Path(config_path).resolve(); config=load_config(config_path)
    for decoder in config.decoders:
        if decoder.enabled:
            require_available_decoder(decoder.profile)
    setup_cpu_start=time.process_time_ns(); setup_wall_start=time.perf_counter_ns()
    def report(message: str) -> None:
        if verbose:
            elapsed=(time.perf_counter_ns()-setup_wall_start)/1e9
            print(f'[qec {elapsed:.1f}s] {message}',file=sys.stderr,flush=True)
    report(f'Loading backends; config={config_path}')
    execution=configure_execution(config)
    import numpy  # noqa: F401
    import scipy.linalg  # noqa: F401
    import pyarrow as pa
    import stim
    from threadpoolctl import threadpool_limits
    from ..artifacts import prepare_instance
    from ..decoders import implementation_identity
    from ..identity import decoder_identity
    from ..provenance import capture
    pa.set_cpu_count(1); pa.set_io_thread_count(1)
    timestamp=datetime.now(timezone.utc); nonce=uuid.uuid4().hex
    run_id=run_identity(config,timestamp,nonce)
    directory=config.output.root/(timestamp.strftime('%Y%m%dT%H%M%S.%fZ')+'_'+nonce[:12])
    directory.mkdir(parents=True,exist_ok=False)
    manifest={'schema_version':2,'run_id':run_id,'status':'incomplete','created_utc':timestamp.isoformat(),
        'completed_batches':0,'expected_batches':None,'instances':[],'config':config.resolved(),
        'sampling':{'recipe':SEED_RECIPE,'recipe_details':'SeedSequence([master, *LE uint32 SHA256(instance_id + NUL + stream), batch_id]).generate_state(1,uint64)',
                    'batch_layout':'range(0, shots_per_point, batch_size), final batch may be short',
                    'sample_call':'one compile_detector_sampler(seed).sample(shots=count,separate_observables=True) per physical batch',
                    'bitwise_scope':'fixed Stim version, platform and batch layout; stored samples permit exact replay'},
        'timing':{'mode':config.timing.mode,'profiling':config.timing.profiling,'units':'integer nanoseconds',
                  'boundary':'complete DecoderAdapter.decode; includes reset/adaptation/H validation/A prediction/cost',
                  'order':'decoder IDs sorted, cyclic rotation by stable shot_index',
                  'concurrent_load':config.timing.mode=='throughput' and config.execution.workers>1,
                  'warmup':'separate warmup seed/stream each batch; excluded; published per-call reset before measured shots',
                  'execution':execution},
        'failure_convention':{'decoding_failure':'declared failure OR invalid correction',
            'block_failure':'decoding_failure OR any valid logical mismatch',
            'conditional_mismatch_denominator':'valid_outputs','component_denominator':'shots',
            'observable_total_failure':'decoding_failure OR observable mismatch; all 12 BB outcomes stay in one block'},
        'resume':'not implemented; committed batches remain readable; every attempt creates a new run'}
    from ..storage.schema import TABLE_VERSIONS
    manifest.update(table_versions=TABLE_VERSIONS,event_tables='present' if config.timing.profiling=='phases' else 'omitted',
                    algorithm_contract='HSBP-ALG-1.0',experiment_contract='HSBP-EXP-1.0')
    atomic_json(directory/'manifest.json',manifest,exclusive=True)
    try:
        report(f'Run directory: {directory}')
        (directory/'config_original.yaml').write_bytes(config_path.read_bytes())
        atomic_json(directory/'config_resolved.json',config.resolved(),exclusive=True)
        (directory/'instances').mkdir(); (directory/'summaries').mkdir(); (directory/'figures').mkdir(); (directory/'logs').mkdir()
        with threadpool_limits(limits=1):
            # Verify all configured backend builds before freezing native provenance.
            decoders=[]
            for d in config.decoders:
                if d.enabled:
                    identity=implementation_identity(d.profile)
                    decoders.append({'id':decoder_identity(d,identity),'config':d.model_dump(),'implementation':identity})
            if len({d['id'] for d in decoders})!=len(decoders): raise ValueError('duplicate semantic decoder configurations')
            manifest['decoders']=decoders
            report('Enabled decoders: '+', '.join(d['config']['name'] for d in decoders))
            report('Capturing source and environment provenance')
            manifest['provenance']=capture(directory/'source_provenance',execution)
            context={'run_id':run_id,'config_hash':content_hash(config.resolved()),'source_hash':manifest['provenance']['source_hash']}
            expected=0; instances=[]
            if replay_source is None:
                sampling_id=sampling_identity(config,stim.__version__)
                manifest['sampling']['sampling_id']=sampling_id
                for code in config.experiment.codes:
                    for distance in code.distances:
                        for p in config.noise.expanded_rates:
                            report(f'Preparing {code.family} d={distance}, R={code.rounds or distance}, p={p:g}')
                            artifact=prepare_instance(config,code.family,distance,p,code.rounds)
                            dest=directory/'instances'/artifact.name
                            info=_copy_artifact(artifact,dest)
                            count=(config.sampling.shots_per_point+config.sampling.batch_size-1)//config.sampling.batch_size
                            expected+=count
                            iid=info['scientific_instance_id']; instances.append((iid,str(dest)))
                            manifest['instances'].append({'instance_id':iid,'directory':str(dest.relative_to(directory)),
                                'artifact_manifest_sha256':sha256(dest/'manifest.json'),'expected_batches':count,
                                'expected_shots':config.sampling.shots_per_point})
                tasks=task_stream(tuple(instances),config,sampling_id)
            else:
                source=Path(replay_source).resolve()
                report(f'Reading saved samples from {source}')
                original=json.loads((source/'manifest.json').read_text())
                if original.get('schema_version') not in (1,2): raise ValueError('unsupported replay run version')
                manifest['replay']={'source_run_id':original['run_id'],'source_status':original['status'],
                    'source_manifest_sha256':sha256(source/'manifest.json'),'source_path':str(source),
                    'physical_plan':'saved source batches are authoritative; current YAML experiment/noise/sampling do not resample or select shots'}
                for instance in original['instances']:
                    path=source/instance['directory']; dest=directory/'instances'/path.name
                    _copy_artifact(path,dest)
                    count=shots=0
                    for batch in committed_batches(path): count+=1; shots+=batch['count']
                    if count==0: continue
                    expected+=count; instances.append((instance['instance_id'],str(dest)))
                    manifest['instances'].append({'instance_id':instance['instance_id'],'directory':str(dest.relative_to(directory)),
                        'artifact_manifest_sha256':sha256(dest/'manifest.json'),'expected_batches':count,'expected_shots':shots})
                if not expected: raise ValueError('source run contains no committed batches')
                destinations=dict(instances)
                tasks=(task for task in _replay_tasks(source,destinations) if task.instance_id in destinations)
                atomic_json(directory/'replay_source_manifest.json',original,exclusive=True)
                shutil.copyfile(source/'config_original.yaml',directory/'replay_source_config.yaml')
            for entry in manifest['instances']:
                folder=directory/entry['directory']
                h=numpy.load(folder/'matrices/H_shape.npy',allow_pickle=False)
                a=numpy.load(folder/'matrices/A_shape.npy',allow_pickle=False)
                entry.update(num_detectors=int(h[0]),num_mechanisms=int(h[1]),num_observables=int(a[0]))
            manifest['timing']['prefix_cpu_limits_active']=any(isinstance(d,Hybrid) and d.enabled and d.search.prefix_cpu_budget_ns is not None for d in config.decoders)
            manifest['expected_batches']=expected
            manifest['run_setup']={'cpu_ns':time.process_time_ns()-setup_cpu_start,
                                   'wall_ns':time.perf_counter_ns()-setup_wall_start,
                                   'includes':'imports, provenance, circuit/DEM preparation and artifact copies; worker decoder setup is per-batch metadata'}
            atomic_json(directory/'manifest.json',manifest)
            total_shots=sum(i['expected_shots'] for i in manifest['instances'])
            completed_shots=0
            report(f'Plan: {len(instances)} instances, {total_shots} physical shots, '
                   f'{total_shots*len(decoders)} decode rows, {expected} batches; '
                   f'workers={config.execution.workers}, timing={config.timing.mode}')
            report('Starting decoding; progress updates after each batch is committed')
            summary={}; seen=set()
            def consume(result):
                nonlocal completed_shots
                task=result['task']; key=(task.instance_id,task.batch_id)
                if key in seen: raise ValueError('duplicate task completion')
                commit_batch(Path(task.artifact),task.batch_id,result['samples'],result['decodes'],
                             result['decoder_ids'],config.output.compression,result['setup'],version=2,
                             profiling=config.timing.profiling,hybrid_rounds=result['hybrid_rounds'],decoder_phases=result['decoder_phases'])
                seen.add(key); _update_summary(summary,result['decodes'])
                manifest['completed_batches']+=1
                atomic_json(directory/'manifest.json',manifest)
                completed_shots+=task.count
                if verbose:
                    sample=result['samples'][0]
                    report(f'Committed batch {manifest["completed_batches"]}/{expected} '
                           f'({100*manifest["completed_batches"]/expected:.1f}%); '
                           f'shots={completed_shots}/{total_shots}; '
                           f'{sample["family"]} d={sample["distance"]}, p={sample["physical_p"]:g}, '
                           f'batch_id={task.batch_id}')
            if config.execution.workers==1:
                initialize(config.model_dump(mode='json'),context)
                for task in tasks: consume(process_batch(task))
            else:
                with ProcessPoolExecutor(max_workers=config.execution.workers,mp_context=multiprocessing.get_context('spawn'),
                    initializer=initialize,initargs=(config.model_dump(mode='json'),context)) as executor:
                    for result in bounded_results(executor,tasks,config.execution.max_pending): consume(result)
            if len(seen)!=expected: raise ValueError('incomplete task count')
            report('Verifying committed shards and writing summaries')
            for instance in manifest['instances']:
                count=shots=0; previous_end=0
                for batch in committed_batches(directory/instance['directory']):
                    count+=1; shots+=batch['count']
                    # Batch intervals must not overlap even in incomplete-source replay.
                    if batch['offset']<previous_end: raise ValueError('overlapping shot indices')
                    previous_end=batch['offset']+batch['count']
                    if set(batch['decoder_ids'])!={d['id'] for d in decoders}: raise ValueError('incomplete decoder set')
                if count!=instance['expected_batches'] or shots!=instance['expected_shots']: raise ValueError('incomplete instance')
            for item in summary.values():
                item['block_failure_rate']=item['block_failures']/item['shots']
                item['decoding_failure_rate']=item['decoding_failures']/item['shots']
                item['valid_mismatch_contribution']=item['valid_logical_mismatches']/item['shots']
                item['conditional_valid_mismatch_rate']=item['valid_logical_mismatches']/item['valid_outputs'] if item['valid_outputs'] else None
            atomic_json(directory/'summaries'/'counts.json',{'schema_version':1,'groups':list(summary.values()),
                'purpose':'software validation counts; not a performance claim'},exclusive=True)
            manifest['status']='complete'; manifest['completed_utc']=datetime.now(timezone.utc).isoformat()
            atomic_json(directory/'manifest.json',manifest)
            report(f'Complete: {completed_shots} physical shots, '
                   f'{completed_shots*len(decoders)} decode rows; {directory}')
    except BaseException as error:
        manifest['status']='incomplete'; manifest['error']={'type':type(error).__name__,'message':str(error)}
        manifest['stopped_utc']=datetime.now(timezone.utc).isoformat()
        (directory/'logs').mkdir(exist_ok=True)
        (directory/'logs'/'exception.txt').write_text(traceback.format_exc())
        atomic_json(directory/'manifest.json',manifest)
        report(f'Failed: {type(error).__name__}: {error}; incomplete run retained at {directory}')
        if hasattr(error,'add_note'): error.add_note(f'Incomplete run retained at {directory}')
        raise
    return directory
