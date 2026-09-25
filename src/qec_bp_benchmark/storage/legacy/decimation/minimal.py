"""Strict minimal per-shot result contracts; no sampled truth or wide telemetry."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pyarrow as pa

from ..search_bp_v2.minimal import (
    SCHEMA as LEGACY_SCHEMA,
    SCHEMA_VERSION as LEGACY_SCHEMA_VERSION,
)

SCHEMA_VERSION = "search_bp_results/2"
SCHEMA = pa.schema([
    pa.field("shot_id", pa.string(), nullable=False),
    pa.field("decoder_name", pa.string(), nullable=False),
    pa.field("logical_error", pa.bool_(), nullable=False),
    pa.field("latency_ns", pa.int64(), nullable=False),
    pa.field("osd_called", pa.bool_(), nullable=True),
    pa.field("correction_by_search", pa.bool_(), nullable=True),
], metadata={b"qec_schema": SCHEMA_VERSION.encode()})
LPM_DP_SCHEMA_VERSION = "lpm_dp_results/1"
LPM_DP_SCHEMA = pa.schema([
    pa.field("shot_id", pa.string(), nullable=False),
    pa.field("decoder_name", pa.string(), nullable=False),
    pa.field("logical_error", pa.bool_(), nullable=False),
    pa.field("latency_ns", pa.int64(), nullable=False),
    pa.field("osd_called", pa.bool_(), nullable=False),
], metadata={b"qec_schema": LPM_DP_SCHEMA_VERSION.encode()})


def schema_for_version(schema_version: str) -> pa.Schema:
    if schema_version == SCHEMA_VERSION:
        return SCHEMA
    if schema_version == LPM_DP_SCHEMA_VERSION:
        return LPM_DP_SCHEMA
    raise ValueError(f"unsupported minimal result schema: {schema_version}")


def minimal_record(record: Mapping[str, Any], *, schema_version: str = SCHEMA_VERSION) -> dict[str, Any]:
    """Project a service row; failure OR mismatch, with failed-shot wall latency.

    Inputs belong to the caller. The returned mapping owns scalar values and has
    exactly the selected schema's fields. Missing fields raise KeyError. Exact
    SEARCH-BP/LPM-DP flags are required and are never inferred.
    """
    osd = record["osd_called"]
    searched = record["correction_by_search"]
    if record["decoder_profile"] == "search_bp" and type(osd) is not bool:
        raise ValueError("search_bp requires an exact boolean osd_called")
    if record["decoder_profile"] == "search_bp" and type(searched) is not bool:
        raise ValueError("search_bp requires an exact boolean correction_by_search")
    if record["decoder_profile"] == "lpm_dp_bp_v1" and type(osd) is not bool:
        raise ValueError("lpm_dp_bp_v1 requires an exact boolean osd_called")
    result = {
        "shot_id": record["shot_id"], "decoder_name": record["decoder_name"],
        "logical_error": bool(record["status"] != "SUCCESS" or
                              not record["syndrome_valid"] or record["valid_logical_mismatch"]),
        "latency_ns": record["wall_ns"], "osd_called": osd,
    }
    if schema_version == SCHEMA_VERSION:
        result["correction_by_search"] = searched
    elif schema_version == LPM_DP_SCHEMA_VERSION:
        if type(osd) is not bool:
            raise ValueError("lpm_dp_results/1 requires exact boolean osd_called values")
    else:
        schema_for_version(schema_version)
    return result


def result_table(rows: Sequence[Mapping[str, Any]] | Mapping[str, Sequence[Any]], *,
                 schema_version: str = SCHEMA_VERSION) -> pa.Table:
    """Build an owned Arrow table from exact rows/columns; reject invalid values.

    latency_ns is nonnegative signed int64; each (shot_id, decoder_name) occurs
    once within this append. Run-wide uniqueness follows the scheduler's unique
    batch plan. Nullable OSD values are reserved for unavailable baseline APIs.
    """
    schema = schema_for_version(schema_version)
    if isinstance(rows, Mapping):
        if set(rows) != set(schema.names) or len({len(v) for v in rows.values()}) != 1:
            raise ValueError("result column names or lengths differ")
        values = [dict(zip(rows, items)) for items in zip(*rows.values())]
    else:
        values = list(rows)
    seen = set()
    for row in values:
        if set(row) != set(schema.names):
            raise ValueError("result fields differ from minimal schema")
        if (not isinstance(row["shot_id"], str) or not row["shot_id"] or
                not isinstance(row["decoder_name"], str) or not row["decoder_name"] or
                type(row["logical_error"]) is not bool or
                type(row["latency_ns"]) is not int or not 0 <= row["latency_ns"] < 2**63 or
                (row["osd_called"] is not None and type(row["osd_called"]) is not bool) or
                ("correction_by_search" in row and row["correction_by_search"] is not None and
                 type(row["correction_by_search"]) is not bool)):
            raise ValueError("invalid minimal result value")
        if schema_version == LPM_DP_SCHEMA_VERSION and type(row["osd_called"]) is not bool:
            raise ValueError("lpm_dp_results/1 OSD indicator cannot be null")
        if row["decoder_name"] == "search_bp" and row["osd_called"] is None:
            raise ValueError("search_bp OSD indicator cannot be null")
        if (row["decoder_name"] == "search_bp" and
                row.get("correction_by_search") is None):
            raise ValueError("search_bp correction-by-search indicator cannot be null")
        key = row["shot_id"], row["decoder_name"]
        if key in seen:
            raise ValueError("duplicate shot/decoder result")
        seen.add(key)
    return pa.Table.from_pylist(values, schema=schema)
