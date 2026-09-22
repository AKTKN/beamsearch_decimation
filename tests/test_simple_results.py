"""Focused checks for the minimal simulation result contract."""
from datetime import datetime, timezone
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from qec_bp_benchmark.identity import content_hash
from qec_bp_benchmark.runner.pipeline import _resolved_run_directory, run_benchmark
from qec_bp_benchmark.storage.results import (
    ResultStore, ShotChunkBuffer, condition_prefix, physical_rate_tag,
)
from analysis.simple_search_bp import summarize_search_bp_run, summarize_run


def test_run_and_condition_names_are_exact_and_stable(tmp_path):
    resolved = {"noise": {"rates": [0.003]}, "output": {"root": str(tmp_path)}}
    started = datetime(2026, 9, 22, 14, 5, tzinfo=timezone.utc)
    path, digest = _resolved_run_directory(tmp_path, resolved, started)
    assert digest == content_hash(resolved)
    assert path.name == f"2026_09_22_14_05_{digest[:8]}"
    assert physical_rate_tag(0.003) == "p003"
    assert physical_rate_tag(0.01) == "p01"
    assert physical_rate_tag(0.5) == "p5"
    assert physical_rate_tag(0) == "p0"
    assert condition_prefix("bb72", 6, 6, 0.003, "Z") == "bb72_d6_r6_p003_Z"


def test_result_store_creates_only_data_and_resolved_config(tmp_path):
    run = tmp_path / "2026_09_22_14_05_12345678"
    run.mkdir()
    (run / "config_resolved.json").write_text(json.dumps({"test": True}))
    schema = pa.schema([pa.field("logical_error", pa.bool_(), nullable=False)])
    with ResultStore(run, {"condition": "bb72_d6_r6_p003_Z"}) as store:
        store.append(
            "condition", "decodes", [{"logical_error": True}], schema,
            lambda rows: pa.Table.from_pylist(rows, schema=schema), compression="none",
        )
        store.ensure("condition", "samples", schema, compression="none")
    assert sorted(path.name for path in run.iterdir()) == ["config_resolved.json", "data"]
    assert sorted(path.name for path in (run / "data").iterdir()) == [
        "bb72_d6_r6_p003_Z_logicalerror.parquet",
        "bb72_d6_r6_p003_Z_samples.parquet",
    ]
    assert pq.read_table(run / "data" / "bb72_d6_r6_p003_Z_logicalerror.parquet").num_rows == 1
    assert pq.read_table(run / "data" / "bb72_d6_r6_p003_Z_samples.parquet").num_rows == 0


def test_shot_chunk_buffer_flushes_full_and_final_groups():
    flushed = []
    buffer = ShotChunkBuffer(2, flushed.append)
    for condition, value in (("a", 1), ("b", 8), ("a", 2), ("a", 3)):
        buffer.append({
            "condition_id": condition,
            "tables": {"samples": {"value": [value]}, "events": {"value": []}},
        })
    assert flushed == [{
        "condition_id": "a",
        "tables": {"samples": {"value": [1, 2]}, "events": {"value": []}},
    }]
    buffer.flush_all()
    assert flushed[1:] == [
        {"condition_id": "b",
         "tables": {"samples": {"value": [8]}, "events": {"value": []}}},
        {"condition_id": "a",
         "tables": {"samples": {"value": [3]}, "events": {"value": []}}},
    ]


def test_runner_emits_minimal_layout_end_to_end(tmp_path):
    config = {
        "experiment": {"codes": [{"family": "surface", "distances": [3]}]},
        "noise": {"rates": [0.003]},
        "circuit": {"cache": str(tmp_path / "circuit-cache")},
        "sampling": {"shots_per_point": 1, "batch_size": 1, "warmup_count": 0},
        "execution": {"workers": 1},
        "output": {"root": str(tmp_path / "runs")},
        "decoders": [{"profile": "screened_reference", "T0": 1, "Tpost": 1,
                      "M": 2, "q": 1, "K": 1}],
    }
    path = tmp_path / "run.yaml"
    path.write_text(yaml.safe_dump(config))
    run = run_benchmark(path)
    resolved = json.loads((run / "config_resolved.json").read_text())
    assert run.name.endswith("_" + content_hash(resolved)[:8])
    assert sorted(item.name for item in run.iterdir()) == ["config_resolved.json", "data"]
    assert sorted(item.name for item in (run / "data").iterdir()) == [
        "surface_d3_r3_p003_Z_logicalerror.parquet",
    ]
    assert pq.read_table(run / "data" / "surface_d3_r3_p003_Z_logicalerror.parquet").num_rows == 1
    rows = summarize_run(run)
    assert len(rows) == 1 and rows[0]["shots"] == 1
