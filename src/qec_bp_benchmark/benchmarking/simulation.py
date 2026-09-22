"""Black-box decoder timing decomposition for the simulation pipeline.

The benchmark runs the real scheduler, worker conversion, and Parquet path in an
isolated temporary result root.  Decoder calls are deliberately one indivisible
phase.  The benchmark never writes timing fields into scientific result tables.
"""
from __future__ import annotations

import json
import platform
from pathlib import Path
import statistics
import tempfile
from typing import Any

import yaml

from ..config import load_config
from ..runner.pipeline import run_benchmark


_LEAF_PHASES = (
    "configuration",
    "backend_imports",
    "run_directory_setup",
    "decoder_identity_setup",
    "instance_preparation",
    "worker_worker_model_setup",
    "worker_warmup",
    "worker_physical_sampling",
    "worker_batch_metadata",
    "worker_shot_input_preparation",
    "worker_decoding",
    "worker_telemetry_export",
    "worker_result_normalization",
    "worker_threadpool_verification",
    "worker_worker_unattributed",
    "parquet_writer_open",
    "arrow_table_conversion",
    "parquet_write",
    "parquet_writer_close",
    "parent_batch_bookkeeping",
)

_NON_DECODING_STEADY_PHASES = (
    "worker_physical_sampling",
    "worker_batch_metadata",
    "worker_shot_input_preparation",
    "worker_telemetry_export",
    "worker_result_normalization",
    "worker_threadpool_verification",
    "worker_worker_unattributed",
    "arrow_table_conversion",
    "parquet_write",
    "parent_batch_bookkeeping",
)


def _percent(part: float, whole: float) -> float:
    return 0.0 if whole <= 0 else 100.0 * part / whole


def _derived_config(source: Path, temporary_root: Path, *, shots: int | None,
                    batch_size: int | None) -> tuple[dict[str, Any], int, int]:
    config = load_config(source)
    data = config.model_dump(mode="json")
    if config.config_schema_version is not None:
        data["config_schema_version"] = config.config_schema_version
    data["circuit"]["cache"] = str(config.circuit.cache)
    data["output"]["root"] = str(temporary_root / "runs")
    data["execution"]["workers"] = 1
    data["execution"]["max_pending"] = 2
    data["timing"]["mode"] = "isolated_latency"
    if shots is not None:
        data["sampling"]["shots_per_point"] = shots
    if batch_size is not None:
        data["sampling"]["batch_size"] = min(batch_size, data["sampling"]["shots_per_point"])
    elif data["sampling"]["batch_size"] > data["sampling"]["shots_per_point"]:
        data["sampling"]["batch_size"] = data["sampling"]["shots_per_point"]
    instance_count = sum(len(code["distances"]) for code in data["experiment"]["codes"])
    decoder_count = sum(bool(decoder.get("enabled", True)) for decoder in data["decoders"])
    return data, instance_count, decoder_count


def benchmark_simulation(config_path: str | Path, *, repeats: int = 3,
                         shots: int | None = None,
                         batch_size: int | None = None) -> dict[str, Any]:
    """Measure the actual pipeline while treating every decode as a black box.

    A single worker is mandatory for additive wall-time accounting.  Each repeat
    has a fresh worker cache and temporary output directory; reusable circuit
    artifacts remain in the source configuration's cache.
    """
    if repeats < 1:
        raise ValueError("repeats must be positive")
    if shots is not None and shots < 1:
        raise ValueError("shots must be positive")
    if batch_size is not None and batch_size < 1:
        raise ValueError("batch_size must be positive")
    source = Path(config_path).resolve()
    runs: list[dict[str, int]] = []
    instance_count = decoder_count = 0
    effective_shots = 0
    effective_batch_size = 0
    with tempfile.TemporaryDirectory(prefix="qec-simulation-benchmark-") as temporary:
        temporary_root = Path(temporary)
        for repeat in range(repeats):
            repeat_root = temporary_root / f"repeat-{repeat}"
            repeat_root.mkdir()
            data, instance_count, decoder_count = _derived_config(
                source, repeat_root, shots=shots, batch_size=batch_size
            )
            effective_shots = data["sampling"]["shots_per_point"]
            effective_batch_size = data["sampling"]["batch_size"]
            derived = repeat_root / "benchmark.yaml"
            derived.write_text(yaml.safe_dump(data, sort_keys=False))
            timings: dict[str, int] = {}
            run_benchmark(derived, _simulation_timings=timings)
            leaf_total = sum(timings.get(name, 0) for name in _LEAF_PHASES)
            timings["pipeline_unattributed"] = max(0, timings["end_to_end"] - leaf_total)
            runs.append(timings)

    names = sorted({name for run in runs for name in run})
    medians = {name: int(statistics.median(run.get(name, 0) for run in runs)) for name in names}
    end_to_end = medians["end_to_end"]
    phases = [
        {
            "name": name,
            "median_ns": medians.get(name, 0),
            "median_ms": medians.get(name, 0) / 1e6,
            "end_to_end_percent": _percent(medians.get(name, 0), end_to_end),
        }
        for name in (*_LEAF_PHASES, "pipeline_unattributed")
    ]
    phases.sort(key=lambda item: item["median_ns"], reverse=True)
    non_decoding = sorted(
        ((name, medians.get(name, 0)) for name in _NON_DECODING_STEADY_PHASES),
        key=lambda item: item[1], reverse=True,
    )
    non_decoding_total = sum(value for _, value in non_decoding)
    findings = [
        {
            "rank": rank,
            "phase": name,
            "median_ms": value / 1e6,
            "non_decoding_percent": _percent(value, non_decoding_total),
            "end_to_end_percent": _percent(value, end_to_end),
        }
        for rank, (name, value) in enumerate(non_decoding[:5], 1)
    ]
    return {
        "schema_version": "simulation_timing_benchmark/1",
        "source_config": str(source),
        "method": {
            "decoder_boundary": "DecoderAdapter.decode inclusive; no internal decomposition",
            "clock": "time.perf_counter_ns",
            "aggregation": "median of complete repeats",
            "workers": 1,
            "timing_mode": "isolated_latency",
            "temporary_scientific_outputs_removed": True,
            "notes": [
                "Circuit artifacts use the configured cache.",
                "Worker model setup and configured warmup are reported separately.",
                "Instrumentation is enabled only for this benchmark entry point.",
            ],
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor(),
        },
        "workload": {
            "repeats": repeats,
            "instances": instance_count,
            "shots_per_instance": effective_shots,
            "batch_size": effective_batch_size,
            "enabled_decoders": decoder_count,
            "decode_calls_per_repeat": instance_count * effective_shots * decoder_count,
        },
        "median_end_to_end_ms": end_to_end / 1e6,
        "median_decoding_ms": medians.get("worker_decoding", 0) / 1e6,
        "median_non_decoding_steady_ms": non_decoding_total / 1e6,
        "phases": phases,
        "non_decoding_bottlenecks": findings,
        "raw_repeats_ns": runs,
    }


def format_report(report: dict[str, Any]) -> str:
    """Render a compact, stable text report suitable for terminals and CI logs."""
    workload = report["workload"]
    lines = [
        "Simulation timing benchmark",
        (f"workload: {workload['instances']} instances, "
         f"{workload['shots_per_instance']} shots/instance, "
         f"{workload['enabled_decoders']} decoders, {workload['repeats']} repeats"),
        f"median end-to-end: {report['median_end_to_end_ms']:.3f} ms",
        f"median decoding (black box): {report['median_decoding_ms']:.3f} ms",
        f"median measured non-decoding steady work: {report['median_non_decoding_steady_ms']:.3f} ms",
        "non-decoding bottlenecks:",
    ]
    for item in report["non_decoding_bottlenecks"]:
        lines.append(
            f"  {item['rank']}. {item['phase']}: {item['median_ms']:.3f} ms "
            f"({item['non_decoding_percent']:.1f}% of measured non-decoding steady work)"
        )
    return "\n".join(lines)


def write_report(report: dict[str, Any], path: str | Path) -> Path:
    """Write one reproducible JSON report outside simulation result directories."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return target
