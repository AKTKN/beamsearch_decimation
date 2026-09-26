"""Read active benchmark runs without pooling contexts or rewriting old files."""
from __future__ import annotations
import json
from pathlib import Path
from statistics import mean, median
import pyarrow.parquet as pq
from qec_bp_benchmark.storage.minimal import (
    SCHEMA, SCHEMA_VERSION, LEGACY_SCHEMA, LEGACY_SCHEMA_VERSION, result_table,
)
from qec_bp_benchmark.storage.results import condition_prefix
from .statistics import timing_statistics, wilson_interval


def summarize_run(run_path: str | Path, *, confidence: float = .95) -> list[dict]:
    """Summarize saved physical-shot rows, including failed-shot latency and BP work."""
    run = Path(run_path).expanduser().resolve()
    config = json.loads((run / 'config_resolved.json').read_text())
    conditions = {}
    for code in config['experiment']['instances']:
        for rate in config['noise']['expanded_rates']:
            prefix = condition_prefix(code['family'], code['distance'], code['rounds'],
                                      rate, config['experiment']['memory_basis'])
            conditions[prefix] = dict(code, physical_rate=rate)
    decoders = {d['name']: d for d in config['decoders'] if d['enabled']}
    paths = sorted((run / 'data').glob('*_results.parquet'))
    if not paths:
        raise ValueError('no active benchmark result files found')
    summaries = []
    seen = set()
    for path in paths:
        prefix = path.name.removesuffix('_results.parquet')
        if prefix in seen or prefix not in conditions:
            raise ValueError(f'duplicate or unknown condition: {prefix}')
        seen.add(prefix)
        saved_schema = pq.read_schema(path)
        if saved_schema.equals(SCHEMA, check_metadata=True):
            version = SCHEMA_VERSION
        elif saved_schema.equals(LEGACY_SCHEMA, check_metadata=True):
            version = LEGACY_SCHEMA_VERSION
        else:
            raise ValueError(f'unsupported active result schema: {path}')
        groups = {}
        for row in result_table(pq.read_table(path).to_pylist(),
                                schema_version=version).to_pylist():
            if row['decoder_name'] not in decoders:
                raise ValueError('unknown decoder name')
            groups.setdefault(row['decoder_name'], []).append(row)
        for name, values in sorted(groups.items()):
            count = len(values)
            failures = sum(row['logical_error'] for row in values)
            low, high = wilson_interval(failures, count, confidence)
            convergence = None
            conditional_error = None
            initial_convergence = None
            first_rescue = None
            if version == SCHEMA_VERSION:
                successes = sum(row['converged'] for row in values)
                conv_low, conv_high = wilson_interval(successes, count, confidence)
                convergence = dict(count=successes, denominator=count,
                                   rate=successes / count, low=conv_low, high=conv_high)
                conditional_failures = sum(row['logical_error'] for row in values
                                           if row['converged'])
                err_low, err_high = wilson_interval(conditional_failures, successes, confidence)
                conditional_error = dict(count=conditional_failures, denominator=successes,
                    rate=conditional_failures / successes if successes else None,
                    low=err_low, high=err_high)
                initial = [row['initial_bp_converged'] for row in values
                           if row['initial_bp_converged'] is not None]
                if initial:
                    initial_successes = sum(initial)
                    init_low, init_high = wilson_interval(initial_successes, len(initial), confidence)
                    initial_convergence = dict(count=initial_successes,
                        denominator=len(initial), rate=initial_successes / len(initial),
                        low=init_low, high=init_high)
                    initial_failures = len(initial) - initial_successes
                    rescued = sum(row['first_transform_converged'] is True for row in values)
                    rescue_low, rescue_high = wilson_interval(rescued, initial_failures, confidence)
                    first_rescue = dict(count=rescued, denominator=initial_failures,
                        rate=rescued / initial_failures if initial_failures else None,
                        low=rescue_low, high=rescue_high,
                        executed=sum(row['first_transform_converged'] is not None
                                     for row in values))
            summaries.append(dict(run_id=str(run), condition_id=prefix,
                **conditions[prefix], decoder_name=name, decoder_config=decoders[name],
                timing_context=dict(timing=config['timing'], execution=config['execution']),
                shots=count, logical_errors=failures,
                convergence_rate=convergence,
                logical_error_given_converged=conditional_error,
                initial_bp_convergence_rate=initial_convergence,
                first_transform_rescue_rate=first_rescue,
                logical_error_rate=dict(rate=failures / count if count else None,
                    low=low, high=high, zero_event_bound=count > 0 and failures == 0),
                latency_ns=timing_statistics((row['latency_ns'] for row in values)),
                total_iterations=(dict(min=min(iterations), max=max(iterations),
                    mean=mean(iterations), median=median(iterations)) if (
                    iterations := [row['total_iterations'] for row in values]) else None)))
    return summaries
