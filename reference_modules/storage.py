"""Strict per-shot Arrow schema, semantic checks, and atomic Parquet writes."""
from pathlib import Path
import os
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

_TYPES = {
    "experiment_id": pa.string(), "config_id": pa.string(), "batch_id": pa.int32(),
    "shot_index": pa.int64(), "batch_seed": pa.uint64(), "distance": pa.int16(),
    "physical_error_rate": pa.float64(), "actual_observable": pa.bool_(),
    "ordinary_prediction": pa.bool_(), "ordinary_logical_error": pa.bool_(),
    "ordinary_selected_color": pa.string(), "ordinary_solution_weight": pa.float64(),
    "comparative_prediction": pa.bool_(), "comparative_logical_error": pa.bool_(),
    "selected_swim_distance": pa.float64(), "forced_gap": pa.float64(),
    "comparative_logical_gap": pa.float64(),
    **{f"{prefix}_{c}": pa.float64() for prefix in ("stage2_weight", "swim_distance") for c in "rgb"},
}
SHOT_SCHEMA = pa.schema([pa.field(name, dtype, nullable=False) for name, dtype in _TYPES.items()])


def validate_shots(frame: pd.DataFrame) -> None:
    """Reject incomplete, nonfinite, or semantically inconsistent shot rows.

    Args:
        frame: Nonempty batch or projected full-schema shot table.
    Raises:
        ValueError: Missing fields, nulls, duplicate IDs, or invalid invariants.
    """
    if not set(_TYPES).issubset(frame.columns) or frame.empty or frame[list(_TYPES)].isna().any().any():
        raise ValueError("Shot table must be nonempty with the complete nonnull schema")
    if frame.duplicated(["config_id", "batch_id", "shot_index"]).any():
        raise ValueError("Duplicate shot identity")
    for name, dtype in _TYPES.items():
        if pa.types.is_floating(dtype):
            if not np.isfinite(frame[name]).all() or (frame[name] < 0).any():
                raise ValueError(f"Invalid nonnegative finite quantity: {name}")
        if pa.types.is_boolean(dtype) and frame[name].dtype != bool:
            raise ValueError(f"Expected boolean labels: {name}")
    if not frame.ordinary_selected_color.isin(list("rgb")).all():
        raise ValueError("Unknown selected color")
    indices = frame.ordinary_selected_color.map({c:i for i,c in enumerate("rgb")}).to_numpy()
    scores = frame[[f"swim_distance_{c}" for c in "rgb"]].to_numpy()
    if not np.array_equal(scores[np.arange(len(frame)),indices], frame.selected_swim_distance):
        raise ValueError("Selected swim does not equal the ordinary selected-color score")
    for decoder in ("ordinary", "comparative"):
        if not np.array_equal(frame[f"{decoder}_prediction"] != frame.actual_observable,
                              frame[f"{decoder}_logical_error"]):
            raise ValueError(f"Incorrect {decoder} failure label")
    if not np.array_equal(frame.forced_gap, frame.comparative_logical_gap):
        raise ValueError("forced_gap must equal the stored comparative logical gap")


def write_shard(frame: pd.DataFrame, path: Path, config_hash: str, *,
                schema: pa.Schema = SHOT_SCHEMA, validator=validate_shots) -> None:
    """Validate and atomically write one compressed Parquet shard, without overwrite.

    Args:
        frame: One batch with all required columns.
        path: Collision-free deterministic destination.
        config_hash: SHA256 of the resolved run configuration.
        schema: Explicit experiment schema; defaults preserve code-capacity files.
        validator: Semantic batch validator for that schema.
    Raises:
        ValueError: Invalid rows or unsafe dtype conversion.
        FileExistsError: Destination already exists.
    """
    validator(frame)
    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    table = pa.Table.from_pandas(frame, schema=schema, preserve_index=False, safe=True)
    table = table.replace_schema_metadata({b"config_hash":config_hash.encode(), b"schema_version":b"1"})
    temporary = path.with_suffix(".parquet.tmp")
    pq.write_table(table, temporary, compression="zstd")
    os.replace(temporary, path)
