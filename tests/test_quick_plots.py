"""Trusted plot reads project only requested columns and retain basic summaries."""
import pytest

from analysis import quick_plots
from analysis.io import load_run, select_records
from analysis.statistics import aggregate_failures
from test_analysis import saved_run


def test_failure_projection_matches_verified_counts(saved_run, tmp_path, monkeypatch):
    expected = aggregate_failures(select_records([load_run(saved_run)]))
    original = quick_plots.pq.read_table
    reads = []
    def read(paths, *, columns):
        reads.append(columns)
        assert all(path.parent.name == 'decodes' for path in paths)
        assert not {'cpu_ns', 'wall_ns', 'prediction', 'observable_mismatch', 'shot_id'} & set(columns)
        return original(paths, columns=columns)
    captured = []
    monkeypatch.setattr(quick_plots.pq, 'read_table', read)
    monkeypatch.setattr(quick_plots, 'plot_failure_rates', lambda rows, output: captured.extend(rows) or [])
    quick_plots.plot_saved_data([saved_run], tmp_path, plot='failure_rate')
    assert reads and len(captured) == len(expected)
    by_id = {row['decoder_id']: row for row in expected}
    for row in captured:
        for key in ('shots', 'valid_outputs', 'block_failure', 'decoding_failure',
                    'valid_mismatch_contribution', 'conditional_valid_mismatch'):
            assert row[key] == by_id[row['decoder_id']][key]


@pytest.mark.parametrize('plot,timer', [('cpu_ecdf', 'cpu_ns'), ('wall_survival', 'wall_ns')])
def test_timing_reads_only_selected_clock(saved_run, tmp_path, monkeypatch, plot, timer):
    original = quick_plots.pq.read_table
    reads = []
    def read(paths, *, columns):
        reads.append(columns)
        assert timer in columns
        assert ({'cpu_ns', 'wall_ns'} - {timer}).isdisjoint(columns)
        assert not {'block_failure', 'prediction', 'observable_mismatch'} & set(columns)
        return original(paths, columns=columns)
    captured = []
    def draw(rows, output, **kwargs):
        assert kwargs['timer'] == timer and kwargs['stratify'] is False
        captured.extend(rows)
        return []
    monkeypatch.setattr(quick_plots.pq, 'read_table', read)
    monkeypatch.setattr(quick_plots, 'plot_timings', draw)
    quick_plots.plot_saved_data([saved_run], tmp_path, plot=plot)
    assert reads and len(captured) == 9
