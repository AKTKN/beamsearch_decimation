"""Historical SEARCH-BP-1.0 14-dataset normalization, never an active writer."""
from __future__ import annotations
import json
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
from qec_bp_benchmark.identity import content_hash
from qec_bp_benchmark.storage.schema import HYBRID_ROUNDS, DECODER_PHASES
from qec_bp_benchmark.storage.legacy.search_bp_v1.search_bp_schema import SCHEMAS as SEARCH_BP_SCHEMAS, unpack_bits

def records(self) -> list[dict]:
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


def load(path: Path,manifest: dict,instances: dict[str,dict],execution_id: str):
    """Load only inventory-committed v2 shards after the storage validator passes."""
    from qec_bp_benchmark.storage.legacy.search_bp_v1.search_bp import verify
    from analysis.io import RunData
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
