"""Versioned active AF-BP benchmark rows; old runs remain read-only."""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from typing import Any
import pyarrow as pa

LEGACY_SCHEMA_VERSION = 'benchmark_results/2'
LEGACY_SCHEMA = pa.schema([
    pa.field('shot_id', pa.string(), nullable=False),
    pa.field('decoder_name', pa.string(), nullable=False),
    pa.field('logical_error', pa.bool_(), nullable=False),
    pa.field('latency_ns', pa.int64(), nullable=False),
    pa.field('total_iterations', pa.int64(), nullable=False),
], metadata={b'qec_schema': LEGACY_SCHEMA_VERSION.encode()})

SCHEMA_VERSION = 'benchmark_results/3'
SCHEMA = pa.schema([
    *LEGACY_SCHEMA,
    pa.field('converged', pa.bool_(), nullable=False),
    pa.field('initial_bp_converged', pa.bool_()),
    pa.field('first_transform_converged', pa.bool_()),
], metadata={b'qec_schema': SCHEMA_VERSION.encode()})


def schema_for_version(schema_version: str) -> pa.Schema:
    if schema_version == SCHEMA_VERSION:
        return SCHEMA
    if schema_version == LEGACY_SCHEMA_VERSION:
        return LEGACY_SCHEMA
    raise ValueError(f'unsupported active result schema: {schema_version}')


def minimal_record(record: Mapping[str, Any], *, schema_version: str = SCHEMA_VERSION) -> dict[str, Any]:
    """Project one complete decoder service row; include declared failures."""
    schema_for_version(schema_version)
    row = {
        'shot_id': record['shot_id'], 'decoder_name': record['decoder_name'],
        'logical_error': bool(record['status'] != 'SUCCESS' or
                              not record['syndrome_valid'] or record['valid_logical_mismatch']),
        'latency_ns': record['wall_ns'],
        'total_iterations': record['total_iterations'],
    }
    if schema_version == SCHEMA_VERSION:
        row.update(converged=record['converged'],
                   initial_bp_converged=record['initial_bp_converged'],
                   first_transform_converged=record['first_transform_converged'])
    return row


def result_table(rows: Sequence[Mapping[str, Any]] | Mapping[str, Sequence[Any]], *,
                 schema_version: str = SCHEMA_VERSION) -> pa.Table:
    """Return an owned exact-schema table; reject duplicates and invalid scalars."""
    schema = schema_for_version(schema_version)
    if isinstance(rows, Mapping):
        if set(rows) != set(schema.names) or len({len(v) for v in rows.values()}) != 1:
            raise ValueError('result column names or lengths differ')
        values = [dict(zip(rows, items)) for items in zip(*rows.values())]
    else:
        values = list(rows)
    seen = set()
    for row in values:
        if set(row) != set(schema.names):
            raise ValueError('result fields differ from benchmark schema')
        if (not isinstance(row['shot_id'], str) or not row['shot_id'] or
            not isinstance(row['decoder_name'], str) or not row['decoder_name'] or
            type(row['logical_error']) is not bool or
            type(row['latency_ns']) is not int or not 0 <= row['latency_ns'] < 2**63 or
            type(row['total_iterations']) is not int or not 0 <= row['total_iterations'] < 2**63):
            raise ValueError('invalid benchmark result value')
        if schema_version == SCHEMA_VERSION:
            initial = row['initial_bp_converged']
            first = row['first_transform_converged']
            if (type(row['converged']) is not bool or
                (initial is not None and type(initial) is not bool) or
                (first is not None and type(first) is not bool) or
                (first is not None and initial is not False) or
                (initial is True and row['converged'] is not True) or
                (first is True and row['converged'] is not True)):
                raise ValueError('invalid convergence result value')
        key = row['shot_id'], row['decoder_name']
        if key in seen:
            raise ValueError('duplicate shot/decoder result')
        seen.add(key)
    return pa.Table.from_pylist(values, schema=schema)
