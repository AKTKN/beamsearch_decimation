"""Truth-free LPM-DP-BP-1.0 simulator registration and minimal-result contract."""
from __future__ import annotations

import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pyarrow.parquet as pq
import pytest
import stim
import yaml
from pydantic import ValidationError

from qec_bp_benchmark import _native
from qec_bp_benchmark.config import Config, LPMDP, load_config
from qec_bp_benchmark.decoders import DecoderAdapter
from qec_bp_benchmark.dem.model import convert_dem
from qec_bp_benchmark.runner.pipeline import run_benchmark
from qec_bp_benchmark.storage import failure_labels
from qec_bp_benchmark.storage.minimal import (
    LPM_DP_SCHEMA, LPM_DP_SCHEMA_VERSION, minimal_record, result_table,
)

ROOT = Path(__file__).resolve().parents[1]


def test_strict_config_identity_defaults_and_removed_search_fields():
    decoder = LPMDP()
    assert (decoder.kind, decoder.profile, decoder.name, decoder.algorithm_version) == (
        "lpm_dp_bp", "lpm_dp_bp_v1", "lpm_dp_bp_v1", "LPM-DP-BP-1.0")
    assert decoder.model_dump(exclude={"kind", "profile", "name", "enabled", "algorithm_version"}) == {
        "history_window": 8, "history_clip": 25.0, "pool_size": 32,
        "local_check_limit": 2, "max_fixations": 4, "candidates_per_parent": 2,
        "retained_mass_target": 0.9, "proposal_clip": 30.0,
        "initial_iterations": 30, "candidate_iterations": 20,
        "retained_parents": 8, "max_cycles": 10, "scaling_factor": 1.0,
        "osd_fallback": False,
    }
    loaded = load_config(ROOT / "config/lpm_dp.yaml.example")
    assert loaded.config_schema_version == "lpm_dp_config/1"
    assert loaded.output.data_schema_version == LPM_DP_SCHEMA_VERSION
    assert isinstance(loaded.decoders[0], LPMDP)
    assert Config.model_validate_json(loaded.model_dump_json()) == loaded

    for patch in (
        {"selected_checks": 2}, {"local_variables": 4}, {"beta": 1.0},
        {"guidance_strength": 1.0}, {"k_run": 4}, {"k_keep": 2},
        {"unknown": 1}, {"history_window": 21}, {"local_check_limit": 3},
        {"candidates_per_parent": 1}, {"scaling_factor": 0.0},
        {"osd_fallback": 1}, {"algorithm_version": "SEARCH-BP-2.1"},
    ):
        with pytest.raises(ValidationError):
            LPMDP.model_validate(patch)

    base = loaded.model_dump(mode="json")
    base["decoders"].append({
        "kind": "search_bp", "profile": "search_bp", "name": "search_bp",
        "algorithm_version": "SEARCH-BP-2.1",
    })
    with pytest.raises(ValidationError, match="different minimal result contracts"):
        Config.model_validate(base)


def test_all_settings_reach_one_native_truth_free_call(monkeypatch):
    import qec_bp_benchmark.decoders as adapters

    captured = {}

    class NativeSpy:
        def __init__(self, h, n, p, a, settings):
            captured.update(h=h, n=n, p=p, a=a, settings=settings)

        def decode(self, syndrome):
            captured["syndrome"] = syndrome
            return SimpleNamespace(valid=True, correction=[0], osd_called=False)

    monkeypatch.setattr(adapters, "native_hybrid", lambda: SimpleNamespace(
        LPMDPBPSettings=_native.LPMDPBPSettings, LPMDPBPDecoder=NativeSpy))
    monkeypatch.setattr(adapters, "implementation_identity", lambda profile: {"test": profile})
    config = LPMDP(
        history_window=3, history_clip=4.0, pool_size=9, local_check_limit=1,
        max_fixations=3, candidates_per_parent=5, retained_mass_target=0.8,
        proposal_clip=6.0, initial_iterations=7, candidate_iterations=9,
        retained_parents=4, max_cycles=5, scaling_factor=0.6, osd_fallback=True)
    problem = convert_dem(stim.DetectorErrorModel("error(0.1) D0 L0"))
    adapter = DecoderAdapter(problem, config)
    expected = config.model_dump(exclude={"kind", "profile", "name", "enabled", "algorithm_version"})
    assert {key: getattr(captured["settings"], key) for key in expected} == expected
    assert list(inspect.signature(adapter.decode).parameters) == ["syndrome"]
    assert adapter.decode(np.array([0], dtype=np.uint8)).status == "SUCCESS"
    assert captured["syndrome"] == [0]
    with pytest.raises(TypeError):
        adapter.decode([0], truth=[0])
    with pytest.raises(ValueError):
        DecoderAdapter(problem, config, diagnostics=True)
    with pytest.raises(ValueError):
        DecoderAdapter(problem, config, profiling=True)


def test_real_native_one_and_multiple_shots_osd_and_declared_failure():
    solvable = convert_dem(stim.DetectorErrorModel("error(0.1) D0 L0"))
    adapter = DecoderAdapter(solvable, LPMDP(
        history_window=1, initial_iterations=1, candidate_iterations=1,
        pool_size=2, max_fixations=1, retained_parents=1, max_cycles=1))
    zero = adapter.decode(np.array([0], dtype=np.uint8))
    one = adapter.decode(np.array([1], dtype=np.uint8))
    repeated = adapter.decode(np.array([0], dtype=np.uint8))
    assert zero.status == repeated.status == one.status == "SUCCESS"
    assert zero.osd_called is repeated.osd_called is one.osd_called is False
    assert zero.prediction.tolist() == [0] and one.prediction.tolist() == [1]

    impossible = convert_dem(stim.DetectorErrorModel("error(0.1) D0 D1 L0"))
    common = dict(history_window=1, initial_iterations=1, candidate_iterations=1,
                  pool_size=2, max_fixations=1, retained_parents=1, max_cycles=1)
    no_osd = DecoderAdapter(impossible, LPMDP(**common)).decode([1, 0])
    assert no_osd.status == "DECLARED_FAILURE" and no_osd.correction is None
    assert no_osd.prediction is None and no_osd.osd_called is False
    with_osd = DecoderAdapter(impossible, LPMDP(**common, osd_fallback=True)).decode([1, 0])
    assert with_osd.status == "DECLARED_FAILURE" and with_osd.correction is None
    assert with_osd.prediction is None and with_osd.osd_called is True

    labels = failure_labels(no_osd.status, no_osd.syndrome_valid, None, [False], version=2)
    row = minimal_record({
        "shot_id": "s", "decoder_name": "lpm_dp_bp_v1",
        "decoder_profile": "lpm_dp_bp_v1", "status": no_osd.status,
        "syndrome_valid": no_osd.syndrome_valid,
        "valid_logical_mismatch": labels["valid_logical_mismatch"],
        "wall_ns": 123, "osd_called": no_osd.osd_called,
        "correction_by_search": None,
    }, schema_version=LPM_DP_SCHEMA_VERSION)
    assert row == {
        "shot_id": "s", "decoder_name": "lpm_dp_bp_v1", "logical_error": True,
        "latency_ns": 123, "osd_called": False,
    }
    assert result_table([row], schema_version=LPM_DP_SCHEMA_VERSION).schema == LPM_DP_SCHEMA


def test_bounded_simulator_smoke_and_old_decoders(tmp_path):
    from analysis.simple_search_bp import summarize_run

    data = yaml.safe_load((ROOT / "config/lpm_dp.yaml.example").read_text())
    data["circuit"]["cache"] = str(tmp_path / "cache")
    data["output"]["root"] = str(tmp_path / "runs")
    data["sampling"].update(shots_per_point=2, batch_size=1, warmup_count=0)
    data["output"]["parquet"]["shots_per_flush"] = 2
    data["decoders"][0].update(
        history_window=1, initial_iterations=1, candidate_iterations=1,
        pool_size=4, max_fixations=1, retained_parents=1, max_cycles=1)
    path = tmp_path / "lpm.yaml"
    path.write_text(yaml.safe_dump(data))
    run = run_benchmark(path)
    assert {item.name for item in run.iterdir()} == {"config_resolved.json", "data"}
    files = list((run / "data").glob("*_results.parquet"))
    assert len(files) == 1
    parquet = pq.ParquetFile(files[0])
    assert parquet.schema_arrow.equals(LPM_DP_SCHEMA, check_metadata=True)
    assert parquet.metadata.num_rows == 6
    rows = parquet.read().to_pylist()
    assert set(rows[0]) == set(LPM_DP_SCHEMA.names)
    assert {row["decoder_name"] for row in rows} == {
        "lpm_dp_bp_v1", "beam8", "bposd_ms30_cs0"}
    assert all(type(row["logical_error"]) is bool and row["latency_ns"] >= 0
               and type(row["osd_called"]) is bool for row in rows)
    resolved = json.loads((run / "config_resolved.json").read_text())
    assert resolved["output"]["data_schema_version"] == LPM_DP_SCHEMA_VERSION
    summaries = summarize_run(run)
    assert len(summaries) == 3 and all(item["shots"] == 2 for item in summaries)
    assert all(item["correction_by_search_unknown"] == 2 for item in summaries)
