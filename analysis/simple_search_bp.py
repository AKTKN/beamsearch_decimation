"""Read one minimal result run, preserving condition and execution boundaries."""
from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq

from qec_bp_benchmark.storage.minimal import (
    LEGACY_SCHEMA, LEGACY_SCHEMA_VERSION, SCHEMA, SCHEMA_VERSION, result_table,
)
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
    """Read current/legacy minimal results and preserve explicit event denominators.

    Returns detached summaries, grouped by file condition and decoder name in a
    single run. Never merges runs or execution contexts. Reads closed partial
    files as available observations, without asserting run completion. Historical
    schemas dispatch explicitly to the legacy reader. ValueError rejects missing,
    duplicate, malformed or unsupported data; OSError propagates file errors.
    """
    run = Path(run_path).expanduser().resolve()
    config = json.loads((run / "config_resolved.json").read_text())
    paths = sorted((run / "data").glob("*_results.parquet"))
    # Earlier minimal-layout and historical wide files remain read-only.
    paths += sorted((run / "data").glob("*_logicalerror.parquet"))
    if not paths:
        raise ValueError("no logical-error data found")
    versions = {(pq.read_schema(path).metadata or {}).get(b"qec_schema") for path in paths}
    minimal_versions = {SCHEMA_VERSION.encode(), LEGACY_SCHEMA_VERSION.encode()}
    if not versions <= minimal_versions:
        from .legacy.search_bp_v1.simple_search_bp import summarize_run as legacy
        return legacy(run, clock=clock, confidence=confidence)
    if len(versions) != 1 or clock != "wall":
        raise ValueError("minimal results require a uniform schema and wall clock")
    current = versions == {SCHEMA_VERSION.encode()}
    expected_schema = SCHEMA if current else LEGACY_SCHEMA
    conditions = {}
    for code in config["experiment"]["instances"]:
        for rate in config["noise"]["expanded_rates"]:
            prefix = condition_prefix(code["family"], code["distance"], code["rounds"],
                                      rate, config["experiment"]["memory_basis"])
            conditions[prefix] = dict(code, physical_rate=rate)
    decoders = {d["name"]: d for d in config["decoders"] if d["enabled"]}
    summaries = []
    seen_conditions = set()
    for path in paths:
        prefix = path.name.removesuffix("_results.parquet").removesuffix("_logicalerror.parquet")
        if prefix in seen_conditions:
            raise ValueError("duplicate files for one result condition")
        seen_conditions.add(prefix)
        if prefix not in conditions:
            raise ValueError(f"unknown result condition: {prefix}")
        if not pq.read_schema(path).equals(expected_schema, check_metadata=True):
            raise ValueError(f"unexpected result schema: {path}")
        rows = pq.read_table(path).to_pylist()
        if current:
            rows = result_table(rows).to_pylist()
        else:
            rows = [{**row, "correction_by_search": None} for row in rows]
        groups = {}
        for row in rows:
            if row["decoder_name"] not in decoders:
                raise ValueError("unknown decoder name in results")
            groups.setdefault(row["decoder_name"], []).append(row)
        for name, values in sorted(groups.items()):
            failures = sum(row["logical_error"] for row in values)
            known = [row["osd_called"] for row in values if row["osd_called"] is not None]
            search_known = [row["correction_by_search"] for row in values
                            if row["correction_by_search"] is not None]
            summaries.append(dict(
                run_id=str(run), run_status="saved", condition_id=prefix,
                **conditions[prefix], decoder_name=name,
                decoder_profile=decoders[name]["profile"], decoder_config=decoders[name],
                timing_context=dict(timing=config["timing"], execution=config["execution"]),
                shots=len(values), block_failures=failures,
                logical_error_rate=_metric(failures, len(values), confidence),
                osd_call_fraction=_metric(sum(known), len(known), confidence),
                osd_unknown=len(values) - len(known), clock="wall",
                correction_by_search_fraction=_metric(
                    sum(search_known), len(search_known), confidence),
                correction_by_search_unknown=len(values) - len(search_known),
                decode_time=timing_statistics([row["latency_ns"] for row in values],
                                             quantiles=(.5, .95, .99)),
            ))
    return summaries


summarize_search_bp_run = summarize_run
