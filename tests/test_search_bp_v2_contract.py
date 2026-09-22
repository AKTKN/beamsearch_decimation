"""Migration boundaries, independent result semantics, and baseline integration."""
from pathlib import Path

import pytest
import yaml
import pyarrow.parquet as pq
from pydantic import ValidationError

from qec_bp_benchmark.config import Config, SearchBP, load_config
from qec_bp_benchmark.runner.pipeline import run_benchmark
from qec_bp_benchmark.storage.minimal import SCHEMA, minimal_record, result_table

ROOT = Path(__file__).resolve().parents[1]


def test_v2_contract_and_v1_rejection():
    config = load_config(ROOT / 'config/search_bp.yaml.example')
    assert config.config_schema_version == 'search_bp_config/3'
    assert config.decoders[0].algorithm_version == 'SEARCH-BP-2.0'
    assert Config.model_validate_json(config.model_dump_json()) == config
    with pytest.raises(ValidationError):
        load_config(ROOT / 'config/legacy/search_bp_v1/search_bp.yaml.example')
    for override in ({}, {'algorithm_version': 'SEARCH-BP-1.0'},
                     {'algorithm_version': 'SEARCH-BP-2.0', 'bp': {'beam_width': 2}},
                     {'algorithm_version': 'SEARCH-BP-2.0', 'admission': {'k_run': 1, 'k_keep': 2}},
                     {'algorithm_version': 'SEARCH-BP-2.0', 'search': {'beta': float('nan')}},
                     {'algorithm_version': 'SEARCH-BP-2.0', 'search': {'max_fixations': 5}}):
        with pytest.raises(ValidationError):
            SearchBP.model_validate(override)


def test_v2_execution_fails_before_artifacts_and_old_binding_is_absent(tmp_path):
    from qec_bp_benchmark.decoders import DecoderAdapter, native_hybrid
    config = load_config(ROOT / 'config/search_bp.yaml.example')
    with pytest.raises(NotImplementedError, match='SEARCH-BP-2.0'):
        DecoderAdapter(None, config.decoders[0])
    data = config.model_dump(mode='json')
    data['output']['root'] = str(tmp_path / 'runs')
    data['circuit']['cache'] = str(tmp_path / 'circuits')
    path = tmp_path / 'config.yaml'; path.write_text(yaml.safe_dump(data))
    with pytest.raises(NotImplementedError, match='contract-only'):
        run_benchmark(path)
    assert not (tmp_path / 'runs').exists() and not (tmp_path / 'circuits').exists()
    native = native_hybrid()
    assert not hasattr(native, 'SearchBPDecoder') and not hasattr(native, 'SearchBPSettings')
    assert (ROOT / 'src/qec_bp_benchmark/native/legacy/search_bp_v1/search_bp.hpp').is_file()


@pytest.mark.parametrize('status,valid,mismatch,expected', [
    ('SUCCESS', True, False, False), ('SUCCESS', True, True, True),
    ('DECLARED_FAILURE', True, None, True), ('INVALID_OUTPUT', False, None, True),
])
def test_logical_error_includes_declared_failure_and_latency(status, valid, mismatch, expected):
    row = minimal_record(dict(shot_id='s', decoder_name='search_bp', decoder_profile='search_bp',
        status=status, syndrome_valid=valid, valid_logical_mismatch=mismatch,
        wall_ns=123, osd_called=True))
    assert row['logical_error'] is expected and row['latency_ns'] == 123
    assert result_table([row]).schema == SCHEMA
    with pytest.raises(ValueError):
        result_table([row, row])
    with pytest.raises(ValueError):
        result_table([{**row, 'osd_called': None}])


def test_baselines_write_only_five_fields_with_grouped_spawn_output(tmp_path):
    from analysis.simple_search_bp import summarize_run
    data = yaml.safe_load((ROOT / 'config/search_bp.yaml.example').read_text())
    data['decoders'] = [{'profile': 'bposd_ms30_cs0'}, {'profile': 'beam8'}]
    data['experiment']['codes'] = [{'family': 'surface', 'distances': [3]}]
    data['sampling'].update(shots_per_point=4, batch_size=2, warmup_count=0)
    data['execution'] = {'workers': 2}
    data['circuit']['cache'] = str(tmp_path / 'circuits')
    data['output']['root'] = str(tmp_path / 'runs')
    data['output']['parquet']['shots_per_flush'] = 3
    path = tmp_path / 'baseline.yaml'; path.write_text(yaml.safe_dump(data))
    run = run_benchmark(path)
    files = list((run / 'data').iterdir())
    assert len(files) == 1
    parquet = pq.ParquetFile(files[0])
    assert parquet.schema_arrow.equals(SCHEMA, check_metadata=True)
    assert parquet.metadata.num_rows == 8 and parquet.metadata.num_row_groups == 2
    rows = parquet.read().to_pylist()
    assert all(type(row['osd_called']) is bool for row in rows)
    assert all(not row['osd_called'] for row in rows if row['decoder_name'] == 'beam8')
    summaries = summarize_run(run)
    assert len(summaries) == 2 and all(row['shots'] == 4 for row in summaries)
    assert all(row['osd_call_fraction']['denominator'] == 4 for row in summaries)
