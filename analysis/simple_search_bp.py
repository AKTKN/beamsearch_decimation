"""Read one minimal result run, preserving condition and execution boundaries."""
from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq

from qec_bp_benchmark.storage.minimal import SCHEMA, SCHEMA_VERSION, result_table
from qec_bp_benchmark.storage.results import condition_prefix
from .statistics import timing_statistics, wilson_interval


def _metric(count: int, denominator: int, confidence: float) -> dict:
    low, high = wilson_interval(count, denominator, confidence)
    return dict(count=count, denominator=denominator,
                rate=count / denominator if denominator else None,
                low=low, high=high, confidence=confidence,
                zero_event_bound=denominator > 0 and count == 0)


def summarize_run(run_path: str | Path, *, clock: str = "wall",
                  confidence: float = .95) -> list[dict]:
    """Read five-field results, including failed-shot latency and OSD denominator.

    Returns detached summaries, grouped by file condition and decoder name in a
    single run. Never merges runs or execution contexts. Reads closed partial
    files as available observations, without asserting run completion. Historical
    schemas dispatch explicitly to the legacy reader. ValueError rejects missing,
    duplicate, malformed or unsupported data; OSError propagates file errors.
    """
    run = Path(run_path).expanduser().resolve()
    config = json.loads((run / "config_resolved.json").read_text())
    paths = sorted((run / "data").glob("*_logicalerror.parquet"))
    if not paths:
        raise ValueError("no logical-error data found")
    versions = {(pq.read_schema(path).metadata or {}).get(b"qec_schema") for path in paths}
    if SCHEMA_VERSION.encode() not in versions:
        from .legacy.search_bp_v1.simple_search_bp import summarize_run as legacy
        return legacy(run, clock=clock, confidence=confidence)
    if versions != {SCHEMA_VERSION.encode()} or clock != "wall":
        raise ValueError("minimal results require a uniform schema and wall clock")
    conditions = {}
    for code in config["experiment"]["instances"]:
        for rate in config["noise"]["expanded_rates"]:
            prefix = condition_prefix(code["family"], code["distance"], code["rounds"],
                                      rate, config["experiment"]["memory_basis"])
            conditions[prefix] = dict(code, physical_rate=rate)
    decoders = {d["name"]: d for d in config["decoders"] if d["enabled"]}
    summaries = []
    for path in paths:
        prefix = path.name.removesuffix("_logicalerror.parquet")
        if prefix not in conditions:
            raise ValueError(f"unknown result condition: {prefix}")
        if not pq.read_schema(path).equals(SCHEMA, check_metadata=True):
            raise ValueError(f"unexpected result schema: {path}")
        rows = result_table(pq.read_table(path).to_pylist()).to_pylist()
        groups = {}
        for row in rows:
            if row["decoder_name"] not in decoders:
                raise ValueError("unknown decoder name in results")
            groups.setdefault(row["decoder_name"], []).append(row)
        for name, values in sorted(groups.items()):
            failures = sum(row["logical_error"] for row in values)
            known = [row["osd_called"] for row in values if row["osd_called"] is not None]
            summaries.append(dict(
                run_id=str(run), run_status="saved", condition_id=prefix,
                **conditions[prefix], decoder_name=name,
                decoder_profile=decoders[name]["profile"], decoder_config=decoders[name],
                timing_context=dict(timing=config["timing"], execution=config["execution"]),
                shots=len(values), block_failures=failures,
                logical_error_rate=_metric(failures, len(values), confidence),
                osd_call_fraction=_metric(sum(known), len(known), confidence),
                osd_unknown=len(values) - len(known), clock="wall",
                decode_time=timing_statistics([row["latency_ns"] for row in values],
                                             quantiles=(.5, .95)),
            ))
    return summaries


summarize_search_bp_run = summarize_run
