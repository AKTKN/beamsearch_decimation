"""Active storage and instrumentation checks independent of decoder decisions."""
import numpy as np
import pytest
import json
import pyarrow.parquet as pq
from pathlib import Path
from beam_search_decoder import BeamSearchDecoder
from qec_bp_benchmark.storage.minimal import (
    SCHEMA_VERSION, LEGACY_SCHEMA_VERSION, minimal_record, result_table,
)
from qec_bp_benchmark.storage.results import condition_prefix
from qec_bp_benchmark.config import load_config
from analysis import (summarize_run, list_run_conditions, plot_decode_time_histogram,
                      plot_logical_error_rate, plot_convergence_rate, plot_mean_decode_time,
                      plot_mean_total_iterations)


def test_exact_active_schema_and_failure_rows():
    row = minimal_record(dict(shot_id='shot', decoder_name='beam8',
        status='DECLARED_FAILURE', syndrome_valid=False, valid_logical_mismatch=None,
        wall_ns=47, total_iterations=9, converged=False,
        initial_bp_converged=None, first_transform_converged=None))
    assert row == dict(shot_id='shot', decoder_name='beam8', logical_error=True,
                       latency_ns=47, total_iterations=9, converged=False,
                       initial_bp_converged=None, first_transform_converged=None)
    assert result_table([row]).schema.metadata[b'qec_schema'] == SCHEMA_VERSION.encode()
    assert SCHEMA_VERSION == 'benchmark_results/3'
    with pytest.raises(ValueError, match='duplicate'):
        result_table([row, row])
    with pytest.raises(ValueError, match='invalid'):
        result_table([{**row, 'total_iterations': -1}])
    with pytest.raises(ValueError, match='fields'):
        result_table([{key: value for key, value in row.items()
                       if key != 'total_iterations'}])
    with pytest.raises(ValueError, match='convergence'):
        result_table([{**row, 'first_transform_converged': True}])


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
             latency_ns=100, total_iterations=0, converged=True,
             initial_bp_converged=None, first_transform_converged=None)
        for name in ('beam8', 'bposd')
    ] + [
        dict(shot_id='s1', decoder_name=name, logical_error=True,
             latency_ns=300, total_iterations=4, converged=False,
             initial_bp_converged=None, first_transform_converged=None)
        for name in ('beam8', 'bposd')
    ]
    pq.write_table(result_table(rows), tmp_path / 'data' / f'{prefix}_results.parquet')
    conditions = list_run_conditions(tmp_path)
    assert len(conditions) == 1
    assert conditions[0].result_path.name == f'{prefix}_results.parquet'
    assert (conditions[0].family, conditions[0].distance,
            conditions[0].physical_rate) == ('surface', 3, .003)
    summaries = summarize_run(tmp_path)
    assert len(summaries) == 2
    assert all(item['logical_errors'] == 1 and item['total_iterations']['max'] == 4
               for item in summaries)
    assert all(item['convergence_rate']['count'] == 1 and
               item['logical_error_given_converged']['rate'] == 0
               for item in summaries)
    import matplotlib.pyplot as plt
    figures = [plot_decode_time_histogram(tmp_path, code='surface', distance=3,
                                           physical_rate=.003),
               *plot_logical_error_rate(tmp_path), *plot_mean_decode_time(tmp_path),
               *plot_mean_total_iterations(tmp_path), *plot_convergence_rate(tmp_path)]
    assert len(figures) == 5
    assert figures[-2].axes[0].get_ylabel() == 'Mean total BP iterations'
    assert figures[-1].axes[0].get_ylabel() == 'Convergence rate'
    for figure in figures:
        plt.close(figure)


def test_saved_condition_discovery_uses_files_and_rejects_old_schema(tmp_path):
    import pyarrow as pa
    root = Path(__file__).resolve().parents[1]
    config = load_config(root / 'config/baselines.yaml.example').resolved()
    config['noise']['expanded_rates'] = [.003, .004, .005]
    config['experiment']['instances'].append({**config['experiment']['instances'][0],
                                             'rounds': 4})
    (tmp_path / 'data').mkdir()
    (tmp_path / 'config_resolved.json').write_text(json.dumps(config))
    for rate in (.003, .004):
        prefix = condition_prefix('surface', 3, 3, rate, 'Z')
        path = tmp_path / 'data' / f'{prefix}_results.parquet'
        pq.write_table(result_table([dict(shot_id=f'shot-{rate}',
            decoder_name='beam8', logical_error=False, latency_ns=100,
            total_iterations=2, converged=True, initial_bp_converged=None,
            first_transform_converged=None)]), path)
    prefix = condition_prefix('surface', 3, 4, .003, 'Z')
    pq.write_table(result_table([dict(shot_id='shot-r4', decoder_name='beam8',
        logical_error=False, latency_ns=120, total_iterations=3,
        converged=True, initial_bp_converged=None,
        first_transform_converged=None)]),
        tmp_path / 'data' / f'{prefix}_results.parquet')
    assert {(item.rounds, item.physical_rate) for item in list_run_conditions(tmp_path)} == {
        (3, .003), (3, .004), (4, .003)}
    import matplotlib.pyplot as plt
    figure = plot_decode_time_histogram(tmp_path, code='surface', distance=3,
                                        rounds=4, physical_rate=.003)
    assert 'R=4' in figure._suptitle.get_text()
    plt.close(figure)
    figure = plot_logical_error_rate(tmp_path)[0]
    labels = [text.get_text() for text in figure.axes[0].get_legend().get_texts()]
    assert any('R=3' in label for label in labels)
    assert any('R=4' in label for label in labels)
    plt.close(figure)
    # A configured but unsaved .005 condition is intentionally absent.
    path = tmp_path / 'data' / f"{condition_prefix('surface', 3, 3, .004, 'Z')}_results.parquet"
    pq.write_table(pa.Table.from_pylist([dict(shot_id='old', decoder_name='beam8')]), path)
    with pytest.raises(ValueError, match='unexpected result schema'):
        list_run_conditions(tmp_path)


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


def test_previous_benchmark_schema_remains_readable_without_inferred_convergence(tmp_path):
    root = Path(__file__).resolve().parents[1]
    config = load_config(root / 'config/baselines.yaml.example').resolved()
    (tmp_path / 'data').mkdir()
    (tmp_path / 'config_resolved.json').write_text(json.dumps(config))
    prefix = condition_prefix('surface', 3, 3, .003, 'Z')
    row = dict(shot_id='old-shot', decoder_name='beam8', logical_error=False,
               latency_ns=100, total_iterations=2)
    path = tmp_path / 'data' / f'{prefix}_results.parquet'
    pq.write_table(result_table([row], schema_version=LEGACY_SCHEMA_VERSION), path)
    assert list_run_conditions(tmp_path)[0].schema_version == LEGACY_SCHEMA_VERSION
    assert summarize_run(tmp_path)[0]['convergence_rate'] is None
    with pytest.raises(ValueError, match='not saved'):
        plot_convergence_rate(tmp_path)


def test_af_bp_initial_failure_and_first_transform_rescue_denominators(tmp_path):
    root = Path(__file__).resolve().parents[1]
    config = load_config(root / 'config/af_bp_smoke.yaml.example').resolved()
    (tmp_path / 'data').mkdir()
    (tmp_path / 'config_resolved.json').write_text(json.dumps(config))
    prefix = condition_prefix('surface', 3, 3, .003, 'Z')
    cases = [
        # A syndrome-valid result can still have a logical-sector error.
        (True, True, True, None),
        (False, True, False, True),
        (True, False, False, False),
        (True, False, False, None),
    ]
    rows = [dict(shot_id=f's{i}', decoder_name='af_bp', logical_error=error,
                 latency_ns=100, total_iterations=2, converged=converged,
                 initial_bp_converged=initial, first_transform_converged=first)
            for i, (error, converged, initial, first) in enumerate(cases)]
    pq.write_table(result_table(rows), tmp_path / 'data' / f'{prefix}_results.parquet')
    summary = summarize_run(tmp_path)[0]
    assert summary['convergence_rate']['count'] == 2
    assert summary['logical_error_given_converged']['rate'] == .5
    assert summary['initial_bp_convergence_rate']['count'] == 1
    assert summary['first_transform_rescue_rate']['count'] == 1
    assert summary['first_transform_rescue_rate']['denominator'] == 3
    assert summary['first_transform_rescue_rate']['executed'] == 2
