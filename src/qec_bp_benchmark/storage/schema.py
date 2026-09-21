"""Version 1 Arrow schema: no nullable identifiers, no sentinel NaN costs."""
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
