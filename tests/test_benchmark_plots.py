"""Focused tests for the direct notebook plotting API."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from analysis import (
    decoder_event_rate_table,
    plot_decode_time_histogram,
    plot_logical_error_rate,
    plot_mean_decode_time,
)


def _write_condition(data: Path, family: str, distance: int, rate: float) -> None:
    stem = f"{family}_d{distance}_r{distance}_p01_Z"
    condition_id = f"{family}-{distance}-{rate}"
    pq.write_table(pa.Table.from_pylist([{
        "condition_id": condition_id,
        "family": family,
        "distance": distance,
        "rounds": distance,
        "physical_rate": rate,
        "memory_basis": "Z",
    }]), data / f"{stem}_condition.parquet")
    pq.write_table(pa.Table.from_pylist([{
        "decoder_id": "decoder-alpha-id",
        "name": "alpha",
        "profile": "alpha-profile",
    }]), data / f"{stem}_decoders.parquet")
    # block_failure is intentionally wrong: the reader must calculate logical
    # errors from validity and logical mismatch instead of using this field.
    pq.write_table(pa.Table.from_pylist([
        {"condition_id": condition_id, "decoder_id": "decoder-alpha-id",
         "syndrome_valid": True, "logical_mismatch": False, "block_failure": False,
         "service_cpu_ns": 900_000, "service_wall_ns": 1_000_000},
        {"condition_id": condition_id, "decoder_id": "decoder-alpha-id",
         "syndrome_valid": True, "logical_mismatch": True, "block_failure": False,
         "service_cpu_ns": 1_900_000, "service_wall_ns": 2_000_000},
        {"condition_id": condition_id, "decoder_id": "decoder-alpha-id",
         "syndrome_valid": False, "logical_mismatch": None, "block_failure": False,
         "service_cpu_ns": 2_900_000, "service_wall_ns": 3_000_000},
    ]), data / f"{stem}_logicalerror.parquet")


@pytest.fixture
def minimal_run(tmp_path):
    run = tmp_path / "run"
    data = run / "data"
    data.mkdir(parents=True)
    (run / "config_resolved.json").write_text(json.dumps({"test": True}))
    _write_condition(data, "bb72", 6, 0.01)
    _write_condition(data, "surface", 5, 0.01)
    return run


def test_logical_error_plot_reads_labels_and_separates_code_families(minimal_run):
    figures = plot_logical_error_rate(minimal_run, log_scale=False)
    try:
        assert len(figures) == 2
        assert {figure.axes[0].get_title() for figure in figures} == {"bb72", "surface"}
        for figure in figures:
            assert tuple(figure.get_size_inches()) == pytest.approx((3.4, 2.55))
            assert figure.dpi == 300
            assert figure.axes[0].lines[0].get_ydata().tolist() == pytest.approx([2 / 3])
            assert len(figure.axes[0].collections) == 1  # Wilson shaded band
    finally:
        for figure in figures:
            plt.close(figure)


def test_plot_filters_and_mean_time_interval(minimal_run):
    figures = plot_mean_decode_time(
        minimal_run,
        codes="bb72",
        physical_rates=0.01,
        distances=[6],
        decoders="alpha-profile",
        clock="wall",
        log_scale=False,
    )
    try:
        assert len(figures) == 1
        ax = figures[0].axes[0]
        assert ax.lines[0].get_ydata().tolist() == pytest.approx([2.0])
        assert len(ax.collections) == 1  # Student-t shaded band
        assert ax.get_ylabel() == "Mean wall decode time (ms)"
    finally:
        for figure in figures:
            plt.close(figure)

    with pytest.raises(ValueError, match="select no"):
        plot_logical_error_rate(minimal_run, decoders="missing")
    with pytest.raises(ValueError, match="clock"):
        plot_mean_decode_time(minimal_run, clock="gpu")


def test_decode_time_histogram_uses_microseconds_and_tail_lines(minimal_run):
    figure = plot_decode_time_histogram(
        minimal_run, code="bb72", physical_rate=0.01, distance=6, bins=3,
    )
    try:
        assert len(figure.axes) == 1
        ax = figure.axes[0]
        assert ax.get_xlabel() == "Wall decode time (μs)"
        assert ax.get_ylabel() == "Frequency"
        assert len(ax.patches) == 3
        assert [line.get_xdata()[0] for line in ax.lines] == pytest.approx(
            [2000.0, 2900.0, 2980.0]
        )
    finally:
        plt.close(figure)

    with pytest.raises(ValueError, match="distance is required"):
        plot_decode_time_histogram(minimal_run, code="surface", physical_rate=0.01)


def test_decoder_event_rate_table_uses_osd_and_nonconvergence_flags(tmp_path):
    run = tmp_path / "run"
    data = run / "data"
    data.mkdir(parents=True)
    (run / "config_resolved.json").write_text(json.dumps({"test": True}))
    stem = "surface_d5_r5_p01_Z"
    condition_id = "surface-condition"
    pq.write_table(pa.Table.from_pylist([{
        "condition_id": condition_id, "family": "surface", "distance": 5,
        "rounds": 5, "physical_rate": 0.01, "memory_basis": "Z",
    }]), data / f"{stem}_condition.parquet")
    profiles = [
        {"decoder_id": "search", "name": "search_bp", "profile": "search_bp",
         "kind": "search_bp"},
        {"decoder_id": "beam", "name": "beam8", "profile": "beam8", "kind": "beam8"},
        {"decoder_id": "other", "name": "bposd", "profile": "bposd_ms30_cs10",
         "kind": "bposd"},
    ]
    pq.write_table(pa.Table.from_pylist(profiles), data / f"{stem}_decoders.parquet")
    rows = []
    for decoder_id in ("search", "beam", "other"):
        for shot in range(4):
            rows.append({
                "condition_id": condition_id, "decoder_id": decoder_id,
                "syndrome_valid": not (decoder_id == "beam" and shot in (0, 2)),
                "osd_entered": shot in (0, 1) if decoder_id == "search" else None,
                "timing_mode": "throughput",
            })
    pq.write_table(pa.Table.from_pylist(rows), data / f"{stem}_logicalerror.parquet")

    table = decoder_event_rate_table(run)
    assert table.index.names == ["code", "distance", "physical_rate"]
    assert table.columns.names == ["decoder", "metric"]
    assert table.loc[("surface", 5, 0.01), ("beam8", "decoding_failure_rate")] == 0.5
    assert table.loc[("surface", 5, 0.01), ("search_bp", "osd_reach_rate")] == 0.5
