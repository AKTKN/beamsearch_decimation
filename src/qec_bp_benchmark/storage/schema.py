"""Exact historical and hybrid Arrow schemas: stable identifiers, explicit nulls."""
import pyarrow as pa

VERSION=1

def f(name: str, typ: pa.DataType, nullable: bool=False) -> pa.Field:
    return pa.field(name,typ,nullable=nullable)
S=pa.string(); I=pa.int64(); U=pa.uint64(); B=pa.bool_(); D=pa.float64()
BITS=pa.list_(pa.field('element',B,nullable=False))
INTS=pa.list_(pa.field('element',I,nullable=False))
COMMON=[f('run_id',S),f('instance_id',S),f('sampling_id',S),f('batch_id',U),f('shot_index',U),f('shot_id',S),
        f('batch_seed',U),f('family',S),f('distance',I),f('n',I),f('k_Z',I),f('rounds',I),f('physical_p',D),
        f('noise_id',S),f('model_hash',S),f('source_hash',S),f('config_hash',S)]
SAMPLES=pa.schema(COMMON+[f('num_detectors',I),f('detectors_packed',pa.binary()),f('actual_observables',BITS)],
    metadata={b'qec_schema':b'samples/1',b'bit_order':b'little'})
DECODES=pa.schema(COMMON+[
    f('decoder_id',S),f('decoder_name',S),f('decoder_profile',S),f('execution_position',I),
    f('prediction',BITS,True),f('status',S),f('native_status',S),f('syndrome_valid',B),
    f('decoding_failure',B),f('valid_logical_mismatch',B),f('block_failure',B),
    f('observable_mismatch',BITS,True),f('observable_total_failure',BITS),
    f('cost',D,True),f('cpu_ns',I),f('wall_ns',I),f('timing_mode',S),f('concurrent_load',B),
    f('workers',I),f('native_threads',I),f('blas_threads',I),f('oversubscribed',B),f('profiling',S),
    f('initial_success',B,True),f('initial_iterations',I,True),f('post_iterations',U,True),
    f('candidates',U,True),f('rejected',U,True),f('retained',U,True),f('bp_completions',U,True),
    f('successful_completions',U,True),f('selected_pattern',INTS,True),
    f('correction_packed',pa.binary(),True),f('diagnostics_json',S,True),f('phases_json',S,True)],
    metadata={b'qec_schema':b'decodes/1',b'bit_order':b'little'})


def table(rows: list[dict], schema: pa.Schema) -> pa.Table:
    """Strict field membership and nullability before Arrow construction."""
    names=set(schema.names)
    for row in rows:
        if set(row)!=names: raise ValueError(f'schema fields differ: {set(row)^names}')
        for field in schema:
            if not field.nullable and row[field.name] is None: raise ValueError(f'null required field {field.name}')
    result=pa.Table.from_pylist(rows,schema=schema)
    result.validate(full=True)
    return result

# Historical schemas above remain byte-for-byte compatible at the Arrow boundary.
HYBRID_STRINGS='algorithm_version exit_stage exit_reason fallback_reason osd_llr_source'.split()
HYBRID_COUNTERS=('input_syndrome_weight cycles_started cycles_completed search_slices search_expanded_nodes '
    'search_generated_nodes search_rejected_local search_depth_limited search_frontier_peak search_guidance_peak '
    'search_max_depth_reached bp_attempts bp_iterations bp_warm_transitions selected_hint_node_id '
    'selected_hint_ones selected_hint_zeros hint_disagreements_final osd_calls effective_osd_order').split()
HYBRID_FLAGS='osd_entered prefix_cap_hit node_cap_hit timing_accounting_ok'.split()
DURATION_FIELDS=[f'{phase}_{clock}_ns' for phase in ('native_prefix','search','bp_transition','bp_iterations',
    'osd','prefix_other','service_other') for clock in ('cpu','wall')]
HYBRID_FIELDS=([f(n,S,True) for n in HYBRID_STRINGS]+[f(n,U,True) for n in HYBRID_COUNTERS]+
    [f(n,B,True) for n in HYBRID_FLAGS]+[f(n,I,True) for n in DURATION_FIELDS])
DECODES_V2=pa.schema([f(x.name,x.type,True) if x.name=='valid_logical_mismatch' else x for x in DECODES]+
    HYBRID_FIELDS,metadata={b'qec_schema':b'decodes/2',b'bit_order':b'little'})
EVENT_KEY=[f(n,S) for n in ('run_id','instance_id','sampling_id','decoder_id','shot_id')]+[f('batch_id',U)]
CANDIDATE=[f('candidate_prediction',BITS,True),f('candidate_logical_mismatch',B,True)]
HYBRID_ROUNDS=pa.schema(EVENT_KEY+[f('cycle_index',U)]+
    [f(n,I) for n in 'start_cpu_ns end_cpu_ns start_wall_ns end_wall_ns'.split()]+
    [f(n,U) for n in ('frontier_before frontier_after guidance_before guidance_after expansion_budget iteration_budget '
        'expanded generated iterations').split()]+
    [f(n,U,True) for n in 'hint_node_id hint_ones hint_zeros hint_depth hint_residual_weight residual_before residual_after'.split()]+
    [f(n,D,True) for n in 'hint_g hint_h hint_f'.split()]+[f('hint_digest',S,True)]+
    [f(n,B) for n in 'bp_entered warm node_cap_hit prefix_cap_hit'.split()]+[f('result',S)]+CANDIDATE,
    metadata={b'qec_schema':b'hybrid_rounds/1'})
DECODER_PHASES=pa.schema(EVENT_KEY+[f('phase_index',U),f('phase',S),f('cycle_index',U,True)]+
    [f(n,I) for n in 'cpu_ns wall_ns native_wall_start_ns native_wall_end_ns'.split()]+
    [f('work',U),f('result',S),f('candidate_syndrome_valid',B,True)]+CANDIDATE,
    metadata={b'qec_schema':b'decoder_phases/1'})
TABLE_VERSIONS={'samples':1,'decodes':2,'hybrid_rounds':1,'decoder_phases':1}
V2_SCHEMAS=dict(samples=SAMPLES,decodes=DECODES_V2,hybrid_rounds=HYBRID_ROUNDS,decoder_phases=DECODER_PHASES)
