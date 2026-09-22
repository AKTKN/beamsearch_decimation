"""Tests for developer-only simulation timing decomposition."""
from pathlib import Path

import yaml

from qec_bp_benchmark.benchmarking.simulation import benchmark_simulation, format_report


def test_simulation_benchmark_keeps_decode_opaque_and_removes_runs(tmp_path):
    config = {
        "experiment": {"codes": [{"family": "surface", "distances": [3]}]},
        "noise": {"rates": [0.003]},
        "circuit": {"cache": str(tmp_path / "circuit-cache")},
        "sampling": {"shots_per_point": 1, "batch_size": 1, "warmup_count": 0},
        "execution": {"workers": 1},
        "output": {"root": str(tmp_path / "ordinary-runs"), "compression": "none"},
        "decoders": [{"profile": "bposd_ms30_cs0"}],
    }
    path = tmp_path / "benchmark.yaml"
    path.write_text(yaml.safe_dump(config))
    report = benchmark_simulation(path, repeats=1)
    assert report["schema_version"] == "simulation_timing_benchmark/1"
    assert report["method"]["decoder_boundary"].startswith("DecoderAdapter.decode")
    assert report["workload"]["decode_calls_per_repeat"] == 1
    assert report["median_end_to_end_ms"] > 0
    assert report["median_decoding_ms"] >= 0
    assert report["non_decoding_bottlenecks"]
    assert not (tmp_path / "ordinary-runs").exists()
    assert "non-decoding bottlenecks" in format_report(report)


def test_simulation_benchmark_rejects_invalid_counts(tmp_path):
    path = Path(tmp_path / "missing.yaml")
    for kwargs in ({"repeats": 0}, {"shots": 0}, {"batch_size": 0}):
        try:
            benchmark_simulation(path, **kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid benchmark count was accepted")
