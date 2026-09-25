"""Minimal Parquet result layout for simulation runs.

The run directory deliberately contains only ``config_resolved.json`` and the
``data`` directory.  Circuit, matrix, provenance, inventory, log, and summary
artifacts are execution inputs or derivable data and are not copied here.
"""
from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
import time
from typing import Callable, MutableMapping


def physical_rate_tag(rate: float) -> str:
    """Return the compact, decimal-preserving rate tag used in filenames.

    Examples are ``0.003 -> p003``, ``0.01 -> p01``, and ``0.5 -> p5``.
    Configuration validation already restricts rates to finite values in
    ``[0, 0.5]``.
    """
    value = format(Decimal(str(rate)), "f")
    if "." in value:
        value = value.rstrip("0").rstrip(".")
    if value.startswith("0."):
        value = value[2:]
    elif value == "0":
        return "p0"
    return "p" + value


def condition_prefix(family: str, distance: int, rounds: int, rate: float, basis: str) -> str:
    """Build ``code_distance_rounds_rate_basis`` without lossy rate rounding."""
    return f"{family}_d{distance}_r{rounds}_{physical_rate_tag(rate)}_{basis}"


class ShotChunkBuffer:
    """Coalesce complete per-shot dataset columns into bounded shot groups.

    The buffer owns copies of every supplied column list.  Each condition is
    counted independently, and ``sink`` receives one message after exactly
    ``shots_per_flush`` appended shots, except for the final partial group sent
    by :meth:`flush_all`.  Dataset and column shapes must remain identical for a
    condition.  The sink is synchronous; a failed sink leaves the group owned by
    this object so the original exception can propagate without silent reuse.
    """

    def __init__(self, shots_per_flush: int, sink: Callable[[dict], None]):
        if shots_per_flush < 1:
            raise ValueError("shots_per_flush must be positive")
        self._shots_per_flush = shots_per_flush
        self._sink = sink
        self._counts: dict[str, int] = {}
        self._tables: dict[str, dict[str, dict[str, list]]] = {}

    def append(self, message: dict) -> None:
        """Take ownership of one completed shot and flush a full group."""
        condition_id = message.get("condition_id")
        tables = message.get("tables")
        if not isinstance(condition_id, str) or not isinstance(tables, Mapping):
            raise ValueError("shot chunk requires a string condition_id and table mapping")
        if condition_id not in self._tables:
            owned: dict[str, dict[str, list]] = {}
            for dataset, columns in tables.items():
                if not isinstance(dataset, str) or not isinstance(columns, Mapping):
                    raise ValueError("shot chunk datasets and columns must be mappings")
                owned[dataset] = {name: list(values) for name, values in columns.items()}
            self._tables[condition_id] = owned
            self._counts[condition_id] = 1
        else:
            owned = self._tables[condition_id]
            if set(tables) != set(owned):
                raise ValueError("shot chunk dataset set changed within a condition")
            for dataset, columns in tables.items():
                if not isinstance(columns, Mapping) or set(columns) != set(owned[dataset]):
                    raise ValueError("shot chunk column set changed within a condition")
                for name, values in columns.items():
                    owned[dataset][name].extend(values)
            self._counts[condition_id] += 1
        if self._counts[condition_id] == self._shots_per_flush:
            self.flush(condition_id)

    def flush(self, condition_id: str) -> None:
        """Write and release one condition's pending group, if present."""
        if condition_id not in self._tables:
            return
        message = {"condition_id": condition_id, "tables": self._tables[condition_id]}
        self._sink(message)
        del self._tables[condition_id]
        del self._counts[condition_id]

    def flush_all(self) -> None:
        """Write every final partial group in deterministic insertion order."""
        for condition_id in tuple(self._tables):
            self.flush(condition_id)


class ResultStore:
    """Append one configured minimal schema to one Parquet file per condition.

    Writers stay open for the run and are closed even after an execution error,
    so a failed run contains only readable partial simulation data.  No final
    read-back validation or manifest generation is performed.
    """

    def __init__(self, run_directory: Path, prefixes: dict[str, str], *,
                 benchmark_timings: MutableMapping[str, int] | None = None,
                 schema_version: str = "benchmark_results/2"):
        import pyarrow.parquet as pq

        self.run_directory = Path(run_directory)
        self.data_directory = self.run_directory / "data"
        self.data_directory.mkdir(exist_ok=True)
        self._prefixes = dict(prefixes)
        self._writers: dict[str, pq.ParquetWriter] = {}
        self._benchmark_timings = benchmark_timings
        self._schema_version = schema_version

    def _add_timing(self, name: str, started_ns: int) -> None:
        if self._benchmark_timings is not None:
            self._benchmark_timings[name] = (
                self._benchmark_timings.get(name, 0) + time.perf_counter_ns() - started_ns
            )

    def path(self, condition_id: str) -> Path:
        try:
            prefix = self._prefixes[condition_id]
        except KeyError as error:
            raise ValueError(f"unknown simulation condition: {condition_id}") from error
        return self.data_directory / f"{prefix}_results.parquet"

    def ensure(self, condition_id: str, *, compression: str,
               compression_level: int | None = None) -> None:
        """Create a dataset once; closing it without rows yields typed empty data."""
        import pyarrow.parquet as pq

        from .minimal import schema_for_version

        if condition_id in self._writers:
            return
        path = self.path(condition_id)
        if path.exists():
            raise FileExistsError(path)
        options = {"compression": None if compression == "none" else compression}
        if compression == "zstd" and compression_level is not None:
            options["compression_level"] = compression_level
        started = time.perf_counter_ns()
        self._writers[condition_id] = pq.ParquetWriter(
            path, schema_for_version(self._schema_version), **options)
        self._add_timing("parquet_writer_open", started)

    def append(self, condition_id: str, rows, *, compression: str,
               compression_level: int | None = None) -> None:
        from .minimal import result_table

        self.ensure(condition_id, compression=compression,
                    compression_level=compression_level)
        has_rows = (any(len(values) for values in rows.values())
                    if isinstance(rows, Mapping) else bool(rows))
        if has_rows:
            started = time.perf_counter_ns()
            table = result_table(rows, schema_version=self._schema_version)
            self._add_timing("arrow_table_conversion", started)
            started = time.perf_counter_ns()
            # Every append is one deliberate row group.  The runner
            # coalesces a configured number of complete shots before arriving
            # here, so row-group boundaries never split a shot flush group.
            self._writers[condition_id].write_table(
                table, row_group_size=table.num_rows
            )
            self._add_timing("parquet_write", started)

    def close(self) -> None:
        errors = []
        started = time.perf_counter_ns()
        for writer in self._writers.values():
            try:
                writer.close()
            except BaseException as error:  # preserve every close attempt
                errors.append(error)
        self._writers.clear()
        self._add_timing("parquet_writer_close", started)
        if errors:
            raise errors[0]

    def __enter__(self) -> "ResultStore":
        return self

    def __exit__(self, error_type, error, traceback) -> bool:
        self.close()
        return False
