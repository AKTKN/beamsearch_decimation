"""Read and select verified paired datasets without loading a decoder or resampling."""
from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable,Iterator
import pyarrow as pa
import pyarrow.parquet as pq
from qec_bp_benchmark.identity import content_hash
from qec_bp_benchmark.storage import committed_batches,sha256
from qec_bp_benchmark.storage.schema import SAMPLES,DECODES,DECODES_V2,HYBRID_ROUNDS,DECODER_PHASES,HYBRID_FIELDS,TABLE_VERSIONS
from qec_bp_benchmark.storage.search_bp_schema import SCHEMAS as SEARCH_BP_SCHEMAS,unpack_bits


@dataclass(frozen=True)
class RunData:
    """Owned Arrow tables and detached JSON metadata from one verified run.

    Loading materializes the selected dataset in memory. No numerical decoder state
    is constructed. Incomplete data are opt-in and retain their status in outputs.
    """
    path: Path
    manifest: dict
    samples: pa.Table
    decodes: pa.Table
    instances: dict[str,dict]
    execution_id: str
    hybrid_rounds: pa.Table | None=None
    decoder_phases: pa.Table | None=None
    frontier_tables: dict[str,pa.Table] | None=None

    def records(self) -> list[dict]:
        """Return detached decode records with analysis grouping/label metadata."""
        if self.frontier_tables is not None:
            return self._frontier_records()
        profiles={d['id']:d['config'] for d in self.manifest['decoders']}
        output=[]
        for row in self.decodes.to_pylist():
            metadata=self.instances[row['instance_id']]
            comparison={k:v for k,v in metadata.items() if k not in ('p','hashes','scientific_instance_id')}
            output.append(dict(row,comparison_id=content_hash(comparison),execution_id=self.execution_id,
                trial_id=self.manifest['run_id'],physical_trial_id=row['shot_id'],
                replayed='replay' in self.manifest,run_status=self.manifest['status'],decoder_parameters=profiles[row['decoder_id']]))
        return output

    def _frontier_records(self) -> list[dict]:
        """Normalize separate v2 datasets to the stable analysis record surface."""
        tables=self.frontier_tables;assert tables is not None
        conditions={row['condition_id']:row for row in tables['conditions'].to_pylist()}
        profiles={row['decoder_id']:row for row in tables['decoder_profiles'].to_pylist()}
        config=self.manifest['config'];execution=config['execution'];timing=config['timing']
        summaries={(row['condition_id'],row['shot_id'],row['decoder_id']):row
                   for row in tables['search_summary'].to_pylist()}
        bp={(row['condition_id'],row['shot_id'],row['decoder_id']):row
            for row in tables['bp_summary'].to_pylist()}
        osd={}
        for event in tables['osd_calls'].to_pylist():
            osd.setdefault((event['condition_id'],event['shot_id'],event['decoder_id']),[]).append(event)
        phases={}
        for event in tables['phase_timings'].to_pylist():
            phases.setdefault((event['condition_id'],event['shot_id'],event['decoder_id']),[]).append(event)
        output=[]
        for row in tables['decode_results'].to_pylist():
            condition=conditions[row['condition_id']];profile=profiles[row['decoder_id']]
            key=(row['condition_id'],row['shot_id'],row['decoder_id']);search=summaries.get(key);bps=bp.get(key)
            osd_rows=osd.get(key,[]);phase_rows=phases.get(key,[])
            k=condition['num_observables'];prediction=None if row['predicted_observables_packed'] is None else unpack_bits(row['predicted_observables_packed'],k)
            mismatch=None if row['observable_mismatch_packed'] is None else unpack_bits(row['observable_mismatch_packed'],k)
            failed=not row['syndrome_valid'];physical_id=f"{row['condition_id']}:{row['shot_id']}"
            parameters=json.loads((self.path/profile['resolved_config_path']).read_text())
            metadata=self.instances[row['condition_id']]
            comparison={name:value for name,value in metadata.items() if name not in ('p','hashes','scientific_instance_id')}
            winner=row['winner_source'];exit_stage=(None if winner is None else 'guided_bp' if winner in ('bp_transition','bp_iteration')
                else 'search' if winner in ('zero_syndrome','search') else 'osd')
            exit_reason=(None if winner is None else 'zero_syndrome' if winner=='zero_syndrome' else
                'search_goal_generated' if winner=='search' else 'bp_transition_valid' if winner=='bp_transition' else
                'bp_iteration_valid' if winner=='bp_iteration' else 'osd_valid')
            normalized=dict(row,
                instance_id=row['condition_id'],sampling_id=condition['sampling_id'],batch_id=row['storage_batch_id'],
                shot_index=row['shot_id'],shot_id=physical_id,batch_seed=0,family=condition['family'],
                distance=condition['distance'],n=condition['num_fault_variables'],k_Z=k,rounds=condition['rounds'],
                physical_p=condition['physical_rate'],noise_id=condition['noise_config_sha256'],
                model_hash=condition['model_sha256'],source_hash=self.manifest['provenance']['source_hash'],
                config_hash=content_hash(config),decoder_name=profile['name'],decoder_profile=profile['profile'],
                prediction=prediction,status='SUCCESS' if row['syndrome_valid'] else 'DECLARED_FAILURE',
                decoding_failure=failed,valid_logical_mismatch=row['logical_mismatch'],
                observable_mismatch=mismatch,observable_total_failure=[True]*k if failed else mismatch,
                cost=row['physical_cost'],cpu_ns=row['service_cpu_ns'],wall_ns=row['service_wall_ns'],
                workers=execution['workers'],native_threads=profile['native_threads'],blas_threads=execution['blas_threads'],
                concurrent_load=timing['mode']=='throughput' and execution['workers']>1,
                oversubscribed=self.manifest['timing']['execution']['oversubscribed'],
                algorithm_version=profile['algorithm_version'] if profile['v2_telemetry_available'] else None,
                exit_stage=exit_stage,exit_reason=exit_reason,
                fallback_reason=row['fallback_reason'],osd_llr_source=None,
                bp_attempts=None if bps is None else bps['evaluated_visits'],
                bp_iterations=None if bps is None else bps['actual_iterations'],
                bp_warm_transitions=None if bps is None else bps['ancestor_inheritances']+bps['own_continuations'],
                osd_calls=None if row['osd_entered'] is None else int(row['osd_entered']),
                native_prefix_cpu_ns=row['prefix_cpu_ns'],native_prefix_wall_ns=row['prefix_wall_ns'],
                search_cpu_ns=None if search is None else search['search_cpu_ns'],
                search_wall_ns=None if search is None else search['search_wall_ns'],
                bp_transition_cpu_ns=None if bps is None else bps['bp_prepare_cpu_ns'],
                bp_transition_wall_ns=None if bps is None else bps['bp_prepare_wall_ns'],
                bp_iterations_cpu_ns=None if bps is None else bps['bp_iter_cpu_ns'],
                bp_iterations_wall_ns=None if bps is None else bps['bp_iter_wall_ns'],
                prefix_other_cpu_ns=None,prefix_other_wall_ns=None,
                osd_cpu_ns=sum(event['osd_cpu_ns'] for event in osd_rows) if osd_rows and osd_rows[0]['osd_cpu_ns'] is not None else None,
                osd_wall_ns=sum(event['osd_wall_ns'] for event in osd_rows) if osd_rows and osd_rows[0]['osd_wall_ns'] is not None else None,
                service_other_cpu_ns=sum(event['exclusive_cpu_ns'] for event in phase_rows if event['phase']=='other') if phase_rows else None,
                service_other_wall_ns=sum(event['exclusive_wall_ns'] for event in phase_rows if event['phase']=='other') if phase_rows else None,
                trial_id=self.manifest['run_id'],physical_trial_id=physical_id,replayed='replay' in self.manifest,
                run_status=self.manifest['status'],decoder_parameters=parameters,comparison_id=content_hash(comparison),
                execution_id=self.execution_id)
            output.append(normalized)
        return output


def read_manifest(path: str | Path) -> dict:
    """Dispatch v1/v2 run manifests; reject unknown versions or inconsistent policies."""
    path=Path(path)
    if path.is_dir(): path=path/'manifest.json'
    value=json.loads(path.read_text())
    required={'run_id','instances','config','completed_batches','expected_batches','status','schema_version'}
    if not required<=value.keys() or value['schema_version'] not in (1,2,3) or value['status'] not in ('complete','incomplete'):
        raise ValueError(f'unsupported run manifest: {path}')
    if value['status']=='complete' and value['completed_batches']!=value['expected_batches']:
        raise ValueError('complete run has inconsistent task counts')
    if value['schema_version']==2:
        if value.get('table_versions')!=TABLE_VERSIONS or value.get('event_tables')!=('present' if value['timing']['profiling']=='phases' else 'omitted'): raise ValueError('unsupported run table policy')
    if value['schema_version']==3 and value.get('data_schema_version')!='search_bp_parquet/1':
        raise ValueError('unsupported frontier data schema')
    return value


def _load_frontier(path: Path,manifest: dict,instances: dict[str,dict],execution_id: str) -> RunData:
    """Load only inventory-committed v2 shards after the storage validator passes."""
    from qec_bp_benchmark.storage.search_bp import verify
    validation=verify(path)
    if manifest['status']=='complete' and validation['batches']!=manifest['completed_batches']:
        raise ValueError('frontier batch count differs from manifest')
    inventory=json.loads((path/'inventory/committed_batches.json').read_text())
    grouped={name:[] for name in SEARCH_BP_SCHEMAS}
    for name in ('conditions','decoder_profiles'):
        grouped[name].append(pq.ParquetFile(path/'tables'/name/'part-00000000.parquet').read())
    for batch in inventory['batches']:
        for relative,detail in batch['files'].items():
            grouped[detail['dataset']].append(pq.ParquetFile(path/relative).read())
    tables={name:(pa.concat_tables(values) if values else pa.Table.from_pylist([],schema=SEARCH_BP_SCHEMAS[name]))
            for name,values in grouped.items()}
    return RunData(path,manifest,tables['shot_inputs'],tables['decode_results'],instances,execution_id,
                   pa.Table.from_pylist([],schema=HYBRID_ROUNDS),pa.Table.from_pylist([],schema=DECODER_PHASES),tables)


def discover_runs(root: str | Path, *, include_incomplete: bool=False) -> tuple[Path,...]:
    """Discover immediate run children (or a single run); do not scan artifact trees.

    An incomplete run is skipped by default. A malformed candidate run raises rather
    than disappearing silently. Results are sorted by saved UTC time and run ID.
    """
    root=Path(root).resolve()
    candidates=[root] if (root/'manifest.json').is_file() else sorted(p.parent for p in root.glob('*/manifest.json'))
    found=[]
    for path in candidates:
        manifest=read_manifest(path)
        if manifest['status']=='complete' or include_incomplete:
            found.append((manifest.get('created_utc',''),manifest['run_id'],path))
    return tuple(item[2] for item in sorted(found))


def _inside(parent: Path, relative: str) -> Path:
    path=(parent/relative).resolve()
    if not path.is_relative_to(parent.resolve()): raise ValueError('manifest path escapes run directory')
    return path


def load_run(path: str | Path, *, allow_incomplete: bool=False) -> RunData:
    """Validate manifests, artifacts, provenance, schemas, pairing and counts.

    Returns owned samples/decodes Arrow tables; legitimate nulls remain Arrow nulls.
    Raises ValueError/OSError for corruption, duplicate IDs or missing committed data.
    Uncommitted orphan shards are ignored only for opt-in incomplete runs.
    """
    path=Path(path).resolve(); manifest=read_manifest(path)
    if manifest['status']!='complete' and not allow_incomplete:
        raise ValueError('incomplete run requires allow_incomplete=True')
    if 'provenance' not in manifest or 'decoders' not in manifest:
        raise ValueError('run failed before creating analysis-ready provenance')
    provenance=manifest['provenance']
    for name,expected in [('source_provenance/sources.zip',provenance['archive_sha256']),('environment.json',provenance['environment_sha256'])]:
        if sha256(path/name)!=expected: raise ValueError(f'provenance checksum mismatch: {name}')
    hashes=json.loads((path/'source_provenance/source_hashes.json').read_text())
    if content_hash(hashes)!=provenance['source_hash']: raise ValueError('source hash index mismatch')
    resolved=json.loads((path/'config_resolved.json').read_text())
    if resolved!=manifest['config']: raise ValueError('resolved configuration differs from manifest')
    environment=json.loads((path/'environment.json').read_text())
    execution_id=content_hash({'execution':manifest['timing']['execution'],
        'mode':manifest['timing']['mode'],'profiling':manifest['timing']['profiling'],
        'platform':environment['platform'],'cpu_model':environment['cpu_model'],
        'dependencies':environment['dependencies']})
    decoder_ids=tuple(d['id'] for d in manifest['decoders'])
    if not decoder_ids or len(set(decoder_ids))!=len(decoder_ids): raise ValueError('duplicate/empty manifest decoder IDs')
    if manifest['schema_version']==3:
        instances={}
        for entry in manifest['instances']:
            folder=_inside(path,entry['directory']);iid=entry['instance_id']
            if iid in instances or sha256(folder/'manifest.json')!=entry['artifact_manifest_sha256']:
                raise ValueError('frontier artifact identity mismatch')
            artifact=json.loads((folder/'manifest.json').read_text())
            if artifact.get('status')!='complete' or artifact.get('scientific_instance_id')!=iid:
                raise ValueError('frontier artifact status mismatch')
            for name,expected in artifact['files'].items():
                if sha256(_inside(folder,name))!=expected: raise ValueError(f'artifact checksum mismatch: {name}')
            instances[iid]=json.loads((folder/'instance.json').read_text())
        return _load_frontier(path,manifest,instances,execution_id)
    samples=[]; decodes=[]; rounds=[]; phases=[]; instances={}; total_batches=0
    for entry in manifest['instances']:
        iid=entry['instance_id']; folder=_inside(path,entry['directory'])
        if iid in instances: raise ValueError('duplicate instance in manifest')
        if sha256(folder/'manifest.json')!=entry['artifact_manifest_sha256']: raise ValueError('artifact manifest checksum mismatch')
        artifact=json.loads((folder/'manifest.json').read_text())
        if artifact.get('status')!='complete' or artifact.get('schema_version')!=1 or artifact['scientific_instance_id']!=iid:
            raise ValueError('artifact identity/status mismatch')
        for name,expected in artifact['files'].items():
            if sha256(_inside(folder,name))!=expected: raise ValueError(f'artifact checksum mismatch: {name}')
        metadata=json.loads((folder/'instance.json').read_text()); instances[iid]=metadata
        if manifest['schema_version']==2:
            import numpy as np
            h=np.load(folder/'matrices/H_shape.npy',allow_pickle=False)
            a=np.load(folder/'matrices/A_shape.npy',allow_pickle=False)
            sizes=dict(num_detectors=int(h[0]),num_mechanisms=int(h[1]),num_observables=int(a[0]))
            if any(entry.get(k)!=v for k,v in sizes.items()): raise ValueError('manifest model size mismatch')
        count=shots=0; previous_end=0; expected_batch=0
        for batch in committed_batches(folder):
            if batch['schema_version']!=manifest['schema_version']: raise ValueError('batch/run version mismatch')
            if batch['schema_version']==2 and batch['profiling']!=manifest['timing']['profiling']: raise ValueError('batch/run profiling mismatch')
            count+=1; shots+=batch['count']; total_batches+=1
            if batch['count']<=0 or batch['offset']<previous_end: raise ValueError('invalid/overlapping batch intervals')
            if manifest['status']=='complete' and 'replay' not in manifest:
                if batch['offset']!=previous_end or batch['batch_id']!=expected_batch: raise ValueError('missing batch/shot interval')
            previous_end=batch['offset']+batch['count']; expected_batch+=1
            if set(batch['decoder_ids'])!=set(decoder_ids): raise ValueError('batch decoder set differs from run')
            st=pq.read_table(folder/f'samples/part-{batch["batch_id"]:08d}.parquet')
            dt=pq.read_table(folder/f'decodes/part-{batch["batch_id"]:08d}.parquet')
            if st.num_rows!=batch['count'] or dt.num_rows!=batch['count']*len(decoder_ids): raise ValueError('batch count mismatch')
            for row,expected_index in zip(st.to_pylist(),range(batch['offset'],previous_end)):
                expected={'run_id':manifest['run_id'],'instance_id':iid,'shot_index':expected_index,
                    'batch_id':batch['batch_id'],'batch_seed':batch['seed'],'sampling_id':batch['sampling_id'],
                    'config_hash':content_hash(resolved),'source_hash':provenance['source_hash'],
                    'family':metadata['family'],'distance':metadata['distance'],'n':metadata['n'],
                    'k_Z':metadata['k_Z'],'rounds':metadata['rounds'],'physical_p':metadata['p']}
                if any(row[k]!=v for k,v in expected.items()): raise ValueError('row differs from run/artifact identity')
            for row in dt.to_pylist():
                expected={'timing_mode':resolved['timing']['mode'],'profiling':resolved['timing']['profiling'],
                    'workers':resolved['execution']['workers'],'native_threads':resolved['execution']['native_threads'],
                    'blas_threads':resolved['execution']['blas_threads'],
                    'concurrent_load':manifest['timing']['concurrent_load'],
                    'oversubscribed':manifest['timing']['execution']['oversubscribed']}
                if any(row[k]!=v for k,v in expected.items()): raise ValueError('timing row differs from manifest')
            if manifest['schema_version']==1:
                projected=[]
                for row in dt.to_pylist():
                    row.update({f.name:None for f in HYBRID_FIELDS})
                    if row['decoding_failure']: row['valid_logical_mismatch']=None
                    projected.append(row)
                dt=pa.Table.from_pylist(projected,schema=DECODES_V2)
            elif manifest['event_tables']=='present':
                rounds.append(pq.read_table(folder/f'hybrid_rounds/part-{batch["batch_id"]:08d}.parquet'))
                phases.append(pq.read_table(folder/f'decoder_phases/part-{batch["batch_id"]:08d}.parquet'))
            samples.append(st); decodes.append(dt)
        if manifest['status']=='complete' and (count!=entry['expected_batches'] or shots!=entry['expected_shots']):
            raise ValueError('complete run has missing instance batches/shots')
        if manifest['status']=='complete':
            for sub in (('samples','decodes','hybrid_rounds','decoder_phases') if manifest.get('event_tables')=='present' else ('samples','decodes')):
                if len(list((folder/sub).glob('part-*.parquet')))!=count: raise ValueError('complete run has uncommitted shards')
    if manifest['status']=='complete' and total_batches!=manifest['completed_batches']:
        raise ValueError('complete manifest has missing committed batches')
    return RunData(path,manifest,pa.concat_tables(samples) if samples else pa.Table.from_pylist([],schema=SAMPLES),
        pa.concat_tables(decodes) if decodes else pa.Table.from_pylist([],schema=DECODES_V2),instances,execution_id,
        pa.concat_tables(rounds) if rounds else pa.Table.from_pylist([],schema=HYBRID_ROUNDS),
        pa.concat_tables(phases) if phases else pa.Table.from_pylist([],schema=DECODER_PHASES))


def select_records(runs: Iterable[RunData], *, families: Iterable[str] | None=None,
                   distances: Iterable[int] | None=None, decoder_ids: Iterable[str] | None=None,
                   timing_modes: Iterable[str] | None=None) -> list[dict]:
    """Select explicit values, preserving separate run/scientific/execution identities."""
    filters={key:set(values) for key,values in [('family',families),('distance',distances),
        ('decoder_id',decoder_ids),('timing_mode',timing_modes)] if values is not None}
    selected=[]; seen=set()
    for run in runs:
        for row in run.records():
            if any(row[key] not in values for key,values in filters.items()): continue
            key=(row['run_id'],row['shot_id'],row['decoder_id'])
            if key in seen: raise ValueError('duplicate selected run/shot/decoder')
            seen.add(key); selected.append(row)
    return selected
