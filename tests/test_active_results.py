"""Active storage and instrumentation checks independent of decoder decisions."""
import numpy as np
import pytest
import json
import pyarrow.parquet as pq
from pathlib import Path
from beam_search_decoder import BeamSearchDecoder
from qec_bp_benchmark.storage.minimal import SCHEMA_VERSION, minimal_record, result_table
from qec_bp_benchmark.storage.results import condition_prefix
from qec_bp_benchmark.config import load_config
from analysis import (summarize_run, plot_decode_time_histogram,
                      plot_logical_error_rate, plot_mean_decode_time,
                      plot_mean_total_iterations)


def test_exact_active_schema_and_failure_rows():
    row = minimal_record(dict(shot_id='shot', decoder_name='beam8',
        status='DECLARED_FAILURE', syndrome_valid=False, valid_logical_mismatch=None,
        wall_ns=47, total_iterations=9))
    assert row == dict(shot_id='shot', decoder_name='beam8', logical_error=True,
                       latency_ns=47, total_iterations=9)
    assert result_table([row]).schema.metadata[b'qec_schema'] == SCHEMA_VERSION.encode()
    assert SCHEMA_VERSION == 'benchmark_results/2'
    with pytest.raises(ValueError, match='duplicate'):
        result_table([row, row])
    with pytest.raises(ValueError, match='invalid'):
        result_table([{**row, 'total_iterations': -1}])
    with pytest.raises(ValueError, match='fields'):
        result_table([{key: value for key, value in row.items()
                       if key != 'total_iterations'}])


def test_beam_total_counts_all_paths_and_resets_on_zero():
    h = np.array([[1,1,0,1,0,0,0,0], [0,1,1,0,1,0,0,0],
                  [1,0,1,0,0,1,0,0], [0,1,1,1,0,0,1,1]], dtype=np.uint8)
    decoder = BeamSearchDecoder(h, error_channel=[.1] * 8, beam_width=8,
        initial_iters=1, iters_per_round=2, max_rounds=2, num_results=1)
    syndrome = np.array([1,0,0,0], dtype=np.uint8)
    decoder.decode(syndrome)
    assert decoder.total_iterations == 4 > decoder.iter
    decoder.decode(np.zeros(4, dtype=np.uint8))
    assert decoder.total_iterations == 0
    decoder.decode(syndrome)
    assert decoder.total_iterations == 4


def test_beam_instrumentation_preserves_pristine_decisions():
    # Captured from a clean build of upstream 084a475 (without the counter patch).
    # Lexicographic 4-bit syndrome order; the patched build must agree on all 16.
    pristine = ('00000000', '00101100', '00000100', '00101000',
                '00001000', '00100100', '00001100', '00100000',
                '10000100', '00010000', '10000000', '11110111',
                '01101100', '01000000', '01101000', '11111111')
    h = np.array([[1,1,0,1,0,0,0,0], [0,1,1,0,1,0,0,0],
                  [1,0,1,0,0,1,0,0], [0,1,1,1,0,0,1,1]], dtype=np.uint8)
    decoder = BeamSearchDecoder(h, error_channel=[.1] * 8, beam_width=8,
        initial_iters=1, iters_per_round=2, max_rounds=2, num_results=1)
    for value, expected in enumerate(pristine):
        syndrome = np.array([int(bit) for bit in f'{value:04b}'], dtype=np.uint8)
        assert ''.join(map(str, decoder.decode(syndrome))) == expected
        assert decoder.converge is True


def test_saved_baseline_reader_and_plots(tmp_path):
    root = Path(__file__).resolve().parents[1]
    config = load_config(root / 'config/baselines.yaml.example').resolved()
    (tmp_path / 'data').mkdir()
    (tmp_path / 'config_resolved.json').write_text(json.dumps(config))
    prefix = condition_prefix('surface', 3, 3, .003, 'Z')
    rows = [
        dict(shot_id='s0', decoder_name=name, logical_error=False,
             latency_ns=100, total_iterations=0)
        for name in ('beam8', 'bposd')
    ] + [
        dict(shot_id='s1', decoder_name=name, logical_error=True,
             latency_ns=300, total_iterations=4)
        for name in ('beam8', 'bposd')
    ]
    pq.write_table(result_table(rows), tmp_path / 'data' / f'{prefix}_results.parquet')
    summaries = summarize_run(tmp_path)
    assert len(summaries) == 2
    assert all(item['logical_errors'] == 1 and item['total_iterations']['max'] == 4
               for item in summaries)
    import matplotlib.pyplot as plt
    figures = [plot_decode_time_histogram(tmp_path, code='surface', distance=3,
                                           physical_rate=.003),
               *plot_logical_error_rate(tmp_path), *plot_mean_decode_time(tmp_path),
               *plot_mean_total_iterations(tmp_path)]
    assert len(figures) == 4
    assert figures[-1].axes[0].get_ylabel() == 'Mean total BP iterations'
    for figure in figures:
        plt.close(figure)


def test_old_schema_is_legacy_only(tmp_path):
    import pyarrow as pa
    from analysis.legacy.benchmark_plots import SCHEMA as OLD_SCHEMA
    from analysis.legacy.benchmark_plots import plot_mean_decode_time as legacy_plot
    root = Path(__file__).resolve().parents[1]
    config = load_config(root / 'config/baselines.yaml.example').resolved()
    (tmp_path / 'data').mkdir()
    (tmp_path / 'config_resolved.json').write_text(json.dumps(config))
    prefix = condition_prefix('surface', 3, 3, .003, 'Z')
    old = pa.Table.from_pylist([dict(shot_id='s0', decoder_name='beam8',
        logical_error=False, latency_ns=100, total_iterations=1)], schema=OLD_SCHEMA)
    pq.write_table(old, tmp_path / 'data' / f'{prefix}_results.parquet')
    with pytest.raises(ValueError, match='unsupported active'):
        summarize_run(tmp_path)
    with pytest.raises(ValueError, match='unexpected result schema'):
        plot_mean_decode_time(tmp_path)
    import matplotlib.pyplot as plt
    figures = legacy_plot(tmp_path)
    assert len(figures) == 1
    plt.close(figures[0])
