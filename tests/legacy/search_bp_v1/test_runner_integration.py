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


def test_search_bp_reader_uses_direct_named_files(tmp_path):
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load((root / "config/search_bp.yaml.example").read_text())
    config["experiment"]["codes"] = [{"family": "surface", "distances": [3]}]
    config["circuit"]["cache"] = str(tmp_path / "circuit-cache")
    config["sampling"].update(shots_per_point=1, batch_size=1, warmup_count=0)
    config["execution"] = {"workers": 1}
    config["output"]["root"] = str(tmp_path / "runs")
    config["decoders"] = config["decoders"][:1]
    path = tmp_path / "frontier.yaml"
    path.write_text(yaml.safe_dump(config))
    run = run_benchmark(path)
    names = sorted(item.name for item in (run / "data").iterdir())
    assert len(names) == 14
    assert all(name.startswith("surface_d3_r3_p003_Z_") for name in names)
    rows = summarize_search_bp_run(run)
    assert len(rows) == 1 and rows[0]["shots"] == 1


def test_search_bp_streams_shots_through_spawn_queue(tmp_path):
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load((root / "config/search_bp.yaml.example").read_text())
    config["experiment"]["codes"] = [{"family": "surface", "distances": [3]}]
    config["circuit"]["cache"] = str(tmp_path / "circuit-cache")
    config["sampling"].update(shots_per_point=4, batch_size=2, warmup_count=0)
    config["execution"] = {"workers": 2, "max_pending": 2}
    config["timing"] = {"mode": "throughput", "profiling": "phases"}
    config["output"]["root"] = str(tmp_path / "runs")
    config["output"]["parquet"]["compression"] = "none"
    config["output"]["parquet"]["shots_per_flush"] = 3
    config["decoders"] = config["decoders"][:1]
    path = tmp_path / "streaming.yaml"
    path.write_text(yaml.safe_dump(config))
    run = run_benchmark(path)
    samples = pq.ParquetFile(run / "data/surface_d3_r3_p003_Z_samples.parquet")
    results = pq.ParquetFile(run / "data/surface_d3_r3_p003_Z_logicalerror.parquet")
    assert samples.metadata.num_rows == results.metadata.num_rows == 4
    # Workers still stream one completed shot at a time.  The parent coalesces
    # three shots into one row group and flushes the final one-shot remainder.
    assert samples.metadata.num_row_groups == results.metadata.num_row_groups == 2
    phases = pq.ParquetFile(run / "data/surface_d3_r3_p003_Z_phase_timings.parquet")
    assert phases.metadata.num_rows > 0
