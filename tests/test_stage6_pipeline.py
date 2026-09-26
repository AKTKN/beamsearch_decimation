"""Bounded active four-decoder pairing, worker equality, and BB144 checks."""
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest
import yaml
from analysis import (plot_logical_error_rate, plot_convergence_rate,
                      plot_mean_decode_time, plot_mean_total_iterations)

from qec_bp_benchmark.circuits import apply_noise, make_template, select_z_detectors
from qec_bp_benchmark.config import AFBP, Beam, Bposd, Multipliers, RelayBP
from qec_bp_benchmark.decoders import DecoderAdapter
from qec_bp_benchmark.dem.model import convert_dem
from qec_bp_benchmark.runner.pipeline import run_benchmark
from qec_bp_benchmark.storage.minimal import SCHEMA


@pytest.fixture(scope='module')
def bb144_problem():
    template = make_template('bb144', 12, rounds=1)
    eligible = tuple(sorted((*template.data_qubits, *template.check_sectors)))
    circuit = apply_noise(template.circuit, .001, Multipliers(), eligible)
    view = select_z_detectors(circuit, template)
    return convert_dem(view.circuit.detector_error_model(
        decompose_errors=False, approximate_disjoint_errors=False))


@pytest.mark.parametrize('settings', [
    AFBP(initial_iteration_budget=1, transformed_iteration_budget=0,
         graph_rounds=0, n_fact=0),
    RelayBP(pre_iter=1, num_sets=1, set_max_iter=1),
    Beam(initial_iters=1, iters_per_round=1, max_rounds=1),
    Bposd(max_iter=1, osd_order=0),
])
def test_bb144_all_active_decoders(settings, bb144_problem):
    problem = bb144_problem
    assert problem.A.shape[0] == 12 and problem.H.shape[0] == 144
    decoder = DecoderAdapter(problem, settings)
    syndrome = np.asarray(problem.H[:, 0].toarray().ravel(), dtype=np.uint8)
    result = decoder.decode(syndrome)
    assert result.status in ('SUCCESS', 'DECLARED_FAILURE')
    assert type(result.converged) is bool
    if settings.profile == 'af_bp':
        assert type(result.initial_bp_converged) is bool
    assert isinstance(result.total_iterations, int) and result.total_iterations >= 0
    if result.correction is not None:
        np.testing.assert_array_equal(problem.H @ result.correction % 2, syndrome)
        assert result.prediction.shape == (12,)


def _run_config(path: Path, cache: Path, root: Path, workers: int) -> None:
    data = {
        'experiment': {'name': 'stage6_pairing_smoke',
                       'purpose': 'Two-shot integration test only',
                       'codes': [{'family': 'surface', 'distances': [3]}]},
        'noise': {'rates': [.003]},
        'circuit': {'cache': str(cache)},
        'sampling': {'shots_per_point': 2, 'batch_size': 1, 'warmup_count': 0},
        'execution': {'workers': workers},
        'output': {'root': str(root)},
        'decoders': [
            {'profile': 'af_bp', 'initial_iteration_budget': 1,
             'transformed_iteration_budget': 0, 'graph_rounds': 0, 'n_fact': 0},
            {'profile': 'relay_bp', 'pre_iter': 1, 'num_sets': 0,
             'set_max_iter': 1, 'seed': 7},
            {'profile': 'beam8', 'max_rounds': 1, 'initial_iters': 1,
             'iters_per_round': 1},
            {'profile': 'bposd', 'max_iter': 1, 'osd_order': 0},
        ],
    }
    path.write_text(yaml.safe_dump(data))


def _rows(run: Path) -> list[dict]:
    paths = list((run / 'data').glob('*_results.parquet'))
    assert len(paths) == 1
    assert pq.read_schema(paths[0]).equals(SCHEMA, check_metadata=True)
    return pq.read_table(paths[0]).to_pylist()


def test_paired_inputs_and_worker_non_latency_equality(tmp_path, monkeypatch):
    cache = tmp_path / 'cache'
    serial_config = tmp_path / 'serial.yaml'
    parallel_config = tmp_path / 'parallel.yaml'
    _run_config(serial_config, cache, tmp_path / 'serial', 1)
    _run_config(parallel_config, cache, tmp_path / 'parallel', 2)
    seen = []
    original = DecoderAdapter.decode

    def observing_decode(self, syndrome):
        seen.append((self.config.profile, np.asarray(syndrome).copy()))
        return original(self, syndrome)

    monkeypatch.setattr(DecoderAdapter, 'decode', observing_decode)
    serial = run_benchmark(serial_config)
    assert len(seen) == 8
    for first in (0, 4):
        assert {name for name, _ in seen[first:first + 4]} == {
            'af_bp', 'relay_bp', 'beam8', 'bposd'}
        assert all(np.array_equal(seen[first][1], syndrome)
                   for _, syndrome in seen[first:first + 4])
    parallel = run_benchmark(parallel_config)
    one, two = _rows(serial), _rows(parallel)
    assert len(one) == len(two) == 8
    strip_time = lambda rows: sorted((row['shot_id'], row['decoder_name'],
        row['logical_error'], row['total_iterations'], row['converged'],
        row['initial_bp_converged'], row['first_transform_converged']) for row in rows)
    assert strip_time(one) == strip_time(two)
    assert len({row['shot_id'] for row in one}) == 2
    assert {row['decoder_name'] for row in one} == {'af_bp', 'relay_bp', 'beam8', 'bposd'}
    assert all(row['latency_ns'] >= 0 and row['total_iterations'] >= 0 for row in one)
    assert all(type(row['converged']) is bool for row in one)
    assert all((row['initial_bp_converged'] is None) == (row['decoder_name'] != 'af_bp')
               for row in one)
    import matplotlib.pyplot as plt
    figures = [*plot_logical_error_rate(serial), *plot_mean_decode_time(serial),
               *plot_mean_total_iterations(serial), *plot_convergence_rate(serial)]
    assert len(figures) == 4
    for figure in figures:
        plt.close(figure)
