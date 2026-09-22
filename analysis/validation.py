"""Exact non-timing comparison of already validated saved physical datasets."""
from __future__ import annotations
from .io import RunData
from qec_bp_benchmark.storage.schema import DURATION_FIELDS

# All remaining fields (including every science/status/counter field) must match.
EXECUTION_ONLY={'run_id','source_hash','config_hash','cpu_ns','wall_ns','timing_mode','workers',
                'concurrent_load','oversubscribed','execution_position','decoder_name','profiling',
                'phases_json','diagnostics_json','correction_packed','timing_accounting_ok','worker_id',
                'timing_context_id',*DURATION_FIELDS}


def compare_runs(left: RunData, right: RunData, *, allow_additional_decoders: bool=False) -> dict:
    """Require identical physical bits/truth and shared-decoder scientific outputs.

    Fails on differences instead of reporting an approximate agreement. Optional
    traces/corrections and timing instrument details do not affect this scientific
    equality check; validity, logical prediction, cost and all available counters do.
    Both inputs must already pass load_run. Returns explicit tested row counts.
    """
    def samples(run):
        return {(r.get('condition_id',r.get('instance_id')),r['shot_id']):
                {k:v for k,v in r.items() if k not in {'run_id','source_hash','config_hash'}}
                for r in run.samples.to_pylist()}
    if samples(left)!=samples(right): raise ValueError('physical samples or truth differ')
    def decodes(run):
        return {(r.get('condition_id',r.get('instance_id')),r['shot_id'],r['decoder_id']):
                {k:v for k,v in r.items()
                                                if k not in EXECUTION_ONLY and not k.endswith('_ns')}
                for r in run.decodes.to_pylist()}
    a,b=decodes(left),decodes(right)
    if (allow_additional_decoders and not a.keys()<=b.keys()) or (not allow_additional_decoders and a.keys()!=b.keys()):
        raise ValueError('decoder/shot sets differ')
    for key,row in a.items():
        if row!=b[key]: raise ValueError(f'non-timing decoder result differs: {key}')
    if left.manifest['timing']['profiling']==right.manifest['timing']['profiling']=='phases':
        for table,index in [('hybrid_rounds','cycle_index'),('decoder_phases','phase_index')]:
            def events(run):
                data=getattr(run,table)
                return {(r['shot_id'],r['decoder_id'],r[index]):
                    {k:v for k,v in r.items() if k!='run_id' and not k.endswith('_ns')}
                    for r in data.to_pylist()}
            x,y=events(left),events(right)
            if allow_additional_decoders: y={k:v for k,v in y.items() if k[1] in {r['decoder_id'] for r in left.decodes.to_pylist()}}
            if x!=y: raise ValueError('scientific telemetry differs')
    if left.frontier_tables is not None and right.frontier_tables is not None:
        ignored={'conditions','decoder_profiles','shot_inputs','decode_results','phase_timings'}
        for name in sorted(set(left.frontier_tables)-ignored):
            # Every event/summary schema begins with the decode key; remaining
            # local IDs make sorted row equality deterministic.
            def scientific(run):
                return sorted(({k:v for k,v in row.items() if k!='run_id' and not k.endswith('_ns')}
                               for row in run.frontier_tables[name].to_pylist()),key=repr)
            if scientific(left)!=scientific(right):
                raise ValueError(f'non-timing frontier telemetry differs: {name}')
    return {'left_run_id':left.manifest['run_id'],'right_run_id':right.manifest['run_id'],
        'samples_equal':left.samples.num_rows,'shared_decodes_equal':len(a),
        'additional_decode_rows':len(b)-len(a),'status':'equal'}
