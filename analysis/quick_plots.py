"""On-demand column-projected plots of trusted saved decode shards.

This opt-in reader does not verify manifests, checksums, provenance, pairing or
row invariants. It reads available decode shards, including any uncommitted ones.
The verified report workflow remains in analysis.io and analysis.report.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Sequence

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from qec_bp_benchmark.identity import content_hash
from .plots import plot_failure_rates, plot_timings
from .statistics import GROUP_KEYS, wilson_interval

PlotKind = Literal['failure_rate', 'cpu_ecdf', 'wall_ecdf', 'cpu_survival', 'wall_survival']
_DERIVED = {'comparison_id', 'execution_id', 'run_status'}
_GROUP_COLUMNS = [key for key in GROUP_KEYS if key not in _DERIVED]
_LABEL_COLUMNS = ['decoder_name', 'decoder_profile']


def _metric(count: int, denominator: int, confidence: float) -> dict:
    low, high = wilson_interval(count, denominator, confidence)
    return dict(count=count, denominator=denominator,
                rate=count / denominator if denominator else None,
                low=low, high=high, confidence=confidence,
                interval='two-sided Wilson', zero_observed=count == 0 and denominator > 0)


def plot_saved_data(
    run_paths: Sequence[str | Path], output: str | Path, *, plot: PlotKind,
    confidence: float = .95, min_expected_tail_count: int = 10,
) -> list[Path]:
    """Read only a requested plot's decode columns and export PNG/PDF paths.

    Inputs are trusted run directories. No integrity validation, sample/event
    table loading, decoder execution, bootstrap or global record cache occurs.
    Each instance is loaded separately. Failure counts use Arrow aggregation;
    timing plots materialize only the selected clock and grouping/label columns.
    All-shot curves include failed shots; there is no timing-path stratification.
    Separate run/model/sampling/decoder/execution contexts retain their identities.
    Returned paths are owned output files; existing output files are not replaced.
    Missing/malformed JSON or Parquet raises the underlying I/O/Arrow error;
    unknown plot names and a selection with no decode rows raise ValueError.
    """
    if plot not in ('failure_rate', 'cpu_ecdf', 'wall_ecdf', 'cpu_survival', 'wall_survival'):
        raise ValueError(f'unknown plot: {plot}')
    failure_plot = plot == 'failure_rate'
    timer = 'cpu_ns' if plot.startswith('cpu_') else 'wall_ns'
    metrics = ['block_failure', 'decoding_failure', 'valid_logical_mismatch'] if failure_plot else [timer]
    columns = _GROUP_COLUMNS + _LABEL_COLUMNS + metrics
    summaries: list[dict] = []
    paths: list[Path] = []
    row_count = 0
    for run_path in run_paths:
        run_path = Path(run_path).expanduser().resolve()
        manifest = json.loads((run_path / 'manifest.json').read_text())
        profiles = {item['id']: item['config'] for item in manifest['decoders']}
        for entry in manifest['instances']:
            folder = run_path / entry['directory']
            shards = sorted((folder / 'decodes').glob('part-*.parquet'))
            if not shards:
                continue
            table = pq.read_table(shards, columns=columns)
            row_count += table.num_rows
            metadata = json.loads((folder / 'instance.json').read_text())
            comparison = {k: v for k, v in metadata.items() if k not in ('p', 'hashes', 'scientific_instance_id')}
            extra = dict(comparison_id=content_hash(comparison),
                         execution_id=manifest['run_id'], run_status=manifest['status'])
            if failure_plot:
                # Count physical decode rows directly; no per-shot dictionary checks.
                for metric in metrics:
                    values = pc.cast(pc.fill_null(table[metric], False), pa.int64())
                    if metric == 'valid_logical_mismatch':
                        values = pc.if_else(pc.not_equal(table['decoding_failure'], 0), 0, values)
                    table = table.set_column(table.schema.get_field_index(metric), metric, values)
                grouped = table.group_by(_GROUP_COLUMNS + _LABEL_COLUMNS).aggregate(
                    [(metric, 'sum') for metric in metrics] + [('block_failure', 'count')])
                for row in grouped.to_pylist():
                    n = row.pop('block_failure_count')
                    failed = row.pop('decoding_failure_sum')
                    blocks = row.pop('block_failure_sum')
                    mismatches = row.pop('valid_logical_mismatch_sum')
                    row.update(extra, decoder_parameters=profiles[row['decoder_id']], shots=n,
                               valid_outputs=n-failed,
                               block_failure=_metric(blocks, n, confidence),
                               decoding_failure=_metric(failed, n, confidence),
                               valid_mismatch_contribution=_metric(mismatches, n, confidence),
                               conditional_valid_mismatch=_metric(mismatches, n-failed, confidence))
                    summaries.append(row)
            else:
                records = table.to_pylist()
                for row in records:
                    row.update(extra, decoder_parameters=profiles[row['decoder_id']])
                paths.extend(plot_timings(records, output, timer=timer,
                                          survival=plot.endswith('survival'), stratify=False,
                                          min_expected_tail_count=min_expected_tail_count))
    if not row_count:
        raise ValueError('selection contains no saved decode rows')
    if failure_plot:
        paths.extend(plot_failure_rates(summaries, output))
    return paths
