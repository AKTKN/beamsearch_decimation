"""Strict configuration tests for the hard-fixation search_bp decoder."""
from pathlib import Path

import pytest
from pydantic import ValidationError

from qec_bp_benchmark.config import Config, ParquetOutput, SearchBP, load_config

ROOT = Path(__file__).resolve().parents[1]


def test_template_uses_scalar_cycle_work_and_new_identity():
    config = load_config(ROOT / "config/search_bp.yaml.example")
    decoder = config.decoders[0]
    assert isinstance(decoder, SearchBP)
    assert decoder.kind == decoder.profile == decoder.name == "search_bp"
    assert decoder.algorithm_version == "SEARCH-BP-1.0"
    assert decoder.search.expansions_per_cycle == 2
    assert decoder.bp.beam_width == 2
    assert decoder.bp.max_iteration == 4
    assert config.output.parquet.shots_per_flush == 1024
    assert Config.model_validate_json(config.model_dump_json()) == config


def test_parquet_output_accepts_only_shot_flush_control():
    assert ParquetOutput(shots_per_flush=7).shots_per_flush == 7
    for removed in ({"row_group_rows": 1024}, {"max_buffer_rows": 4096}):
        with pytest.raises(ValidationError):
            ParquetOutput.model_validate(removed)
    with pytest.raises(ValidationError):
        ParquetOutput(shots_per_flush=0)


def test_removed_soft_hint_and_global_cap_options_are_rejected():
    removed = [
        ("search", "max_expansions", 10),
        ("search", "max_generated_nodes", 64),
        ("bp", "admissions_per_cycle", 2),
        ("bp", "max_total_iterations", 100),
        ("bp", "max_iterations_per_candidate_per_cycle", 20),
        ("bp", "hint_max_depth", 4),
        ("bp", "hint_mode", "soft"),
        ("bp", "hint_policy", "signed_channel_magnitude_plus_margin"),
        ("bp", "hint_margin_llr", 8.0),
        ("bp", "llr_clip", 25.0),
        ("bp", "hard_decision_zero", "one"),
    ]
    for section, name, value in removed:
        with pytest.raises(ValidationError):
            SearchBP.model_validate({section: {name: value}})


@pytest.mark.parametrize("override", [
    {"search": {"expansions_per_cycle": [1, 1]}},
    {"bp": {"enabled": False, "beam_width": 1, "max_iteration": 0}},
    {"bp": {"enabled": False, "beam_width": 0, "max_iteration": 1}},
    {"fallback": {"osd_order": 1}},
    {"native_threads": 2},
    {"unknown": 1},
])
def test_invalid_search_bp_combinations_are_rejected(override):
    with pytest.raises(ValidationError):
        SearchBP.model_validate(override)


def test_zero_cycles_and_disabled_bp_need_no_synthetic_global_budget():
    direct = SearchBP(search={"max_cycles": 0})
    assert direct.search.max_cycles == 0
    disabled = SearchBP(bp={"enabled": False, "beam_width": 0, "max_iteration": 0})
    assert not disabled.bp.enabled
