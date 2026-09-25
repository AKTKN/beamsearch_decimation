"""Read one active baseline run without pooling conditions or execution contexts."""
from __future__ import annotations
import json
from pathlib import Path
from statistics import mean, median
import pyarrow.parquet as pq
from qec_bp_benchmark.storage.minimal import SCHEMA, result_table
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
        raise ValueError('no baseline result files found')
    summaries = []
    seen = set()
    for path in paths:
        prefix = path.name.removesuffix('_results.parquet')
        if prefix in seen or prefix not in conditions:
            raise ValueError(f'duplicate or unknown condition: {prefix}')
        seen.add(prefix)
        if not pq.read_schema(path).equals(SCHEMA, check_metadata=True):
            raise ValueError(f'unsupported active result schema: {path}')
        groups = {}
        for row in result_table(pq.read_table(path).to_pylist()).to_pylist():
            if row['decoder_name'] not in decoders:
                raise ValueError('unknown decoder name')
            groups.setdefault(row['decoder_name'], []).append(row)
        for name, values in sorted(groups.items()):
            count = len(values)
            failures = sum(row['logical_error'] for row in values)
            low, high = wilson_interval(failures, count, confidence)
            summaries.append(dict(run_id=str(run), condition_id=prefix,
                **conditions[prefix], decoder_name=name, decoder_config=decoders[name],
                timing_context=dict(timing=config['timing'], execution=config['execution']),
                shots=count, logical_errors=failures,
                logical_error_rate=dict(rate=failures / count if count else None,
                    low=low, high=high, zero_event_bound=count > 0 and failures == 0),
                latency_ns=timing_statistics((row['latency_ns'] for row in values)),
                total_iterations=(dict(min=min(iterations), max=max(iterations),
                    mean=mean(iterations), median=median(iterations)) if (
                    iterations := [row['total_iterations'] for row in values]) else None)))
    return summaries
