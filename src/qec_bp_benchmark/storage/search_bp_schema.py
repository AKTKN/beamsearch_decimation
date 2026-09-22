"""Explicit Arrow schemas and row checks for the search_bp data contract."""
from __future__ import annotations

import json
import math
from pathlib import Path
from collections.abc import Mapping, Sequence
from typing import Iterable

import pyarrow as pa

SCHEMA_VERSION = "search_bp_parquet/2"
ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = ROOT / "docs/specifications/search_bp_parquet_schema.json"
CONTRACT = json.loads(CONTRACT_PATH.read_text())


def _arrow_type(name: str) -> pa.DataType:
    scalar = {
        "utf8": pa.string(), "uint64": pa.uint64(), "uint32": pa.uint32(),
        "int64": pa.int64(), "float64": pa.float64(), "bool": pa.bool_(),
        "binary": pa.binary(),
    }
    if name in scalar:
        return scalar[name]
    if name == "list<uint32 not null>":
        return pa.list_(pa.field("element", pa.uint32(), nullable=False))
    raise ValueError(f"unsupported Arrow contract type: {name}")


def _schema(name: str, definition: dict) -> pa.Schema:
    fields = [pa.field(item["name"], _arrow_type(item["arrow_type"]), nullable=item["nullable"])
              for item in definition["fields"]]
    metadata = {b"qec_schema": f"{SCHEMA_VERSION}/{name}".encode(), b"bit_order": b"little"}
    return pa.schema(fields, metadata=metadata)


SCHEMAS = {name: _schema(name, definition) for name, definition in CONTRACT["datasets"].items()}
ENUMS = {name: {item["name"]: set(item.get("enum", ())) for item in definition["fields"] if item.get("enum")}
         for name, definition in CONTRACT["datasets"].items()}
PRIMARY_KEYS = {name: tuple(definition["primary_key"]) for name, definition in CONTRACT["datasets"].items()}
PARTITIONS = {name: tuple(definition["partition_columns"]) for name, definition in CONTRACT["datasets"].items()}


def pack_bits(bits: Iterable[int | bool], length: int | None = None) -> bytes:
    """Pack canonical bits little-endian, rejecting nonbinary values and bad lengths."""
    values = [int(value) for value in bits]
    if length is not None and len(values) != length:
        raise ValueError(f"bit-vector length {len(values)} != {length}")
    if any(value not in (0, 1) for value in values):
        raise ValueError("bit vector must be binary")
    out = bytearray((len(values) + 7) // 8)
    for index, value in enumerate(values):
        if value:
            out[index // 8] |= 1 << (index % 8)
    return bytes(out)


def unpack_bits(payload: bytes, length: int) -> list[bool]:
    """Unpack exactly ``length`` bits and reject nonzero high padding."""
    if len(payload) != (length + 7) // 8:
        raise ValueError("packed vector byte length mismatch")
    if length % 8 and payload and payload[-1] >> (length % 8):
        raise ValueError("packed vector has nonzero high padding")
    return [bool((payload[index // 8] >> (index % 8)) & 1) for index in range(length)]


def empty_columns(name: str) -> dict[str, list]:
    """Return an exact mutable column accumulator for one dataset."""
    return {field.name: [] for field in SCHEMAS[name]}


def column_count(columns: Mapping[str, Sequence]) -> int:
    """Validate equal column lengths and return the row count."""
    lengths = {len(values) for values in columns.values()}
    if len(lengths) > 1:
        raise ValueError("column lengths differ")
    return next(iter(lengths), 0)


def table(name: str, rows: list[dict] | Mapping[str, Sequence]) -> pa.Table:
    """Build a strictly typed table from rows or Arrow-compatible columns."""
    schema = SCHEMAS[name]
    names = set(schema.names)
    enums = ENUMS[name]
    keys: set[tuple] = set()
    if isinstance(rows, Mapping):
        if set(rows) != names:
            raise ValueError(f"{name} fields differ: {set(rows) ^ names}")
        count = column_count(rows)
        materialized = ({field: rows[field][index] for field in schema.names}
                        for index in range(count))
    else:
        materialized = iter(rows)
    checked = [] if not isinstance(rows, Mapping) else None
    for row in materialized:
        if set(row) != names:
            raise ValueError(f"{name} fields differ: {set(row) ^ names}")
        for field in schema:
            value = row[field.name]
            if value is None and not field.nullable:
                raise ValueError(f"{name}.{field.name} is required")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"{name}.{field.name} must be finite")
            if value is not None and field.name in enums and value not in enums[field.name]:
                raise ValueError(f"invalid {name}.{field.name}: {value}")
        key = tuple(row[field] for field in PRIMARY_KEYS[name])
        if key in keys:
            raise ValueError(f"duplicate {name} primary key: {key}")
        keys.add(key)
        if checked is not None:
            checked.append(row)
    result = (pa.Table.from_pydict(rows, schema=schema) if isinstance(rows, Mapping)
              else pa.Table.from_pylist(checked, schema=schema))
    result.validate(full=True)
    return result


def schema_inventory() -> dict:
    """Return serializable schema identities and contract digests for manifests."""
    import hashlib
    return {
        name: {"schema": schema.to_string(), "qec_schema": schema.metadata[b"qec_schema"].decode()}
        for name, schema in SCHEMAS.items()
    } | {"contract_sha256": hashlib.sha256(CONTRACT_PATH.read_bytes()).hexdigest()}
