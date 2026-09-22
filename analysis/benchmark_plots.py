"""Direct Parquet readers and paper-sized benchmark comparison figures.

The public plotting functions own the complete workflow: they select a saved run,
read its resolved labels and only the result columns required for one plot, then
return new Matplotlib ``Figure`` objects. They support current six-field files and
historical wider layouts. They do not load telemetry, join runs, bootstrap samples,
write files, or create summary reports.
"""
from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
import json
import math
from pathlib import Path
from statistics import NormalDist
from typing import Literal, TYPE_CHECKING

from matplotlib.figure import Figure
import numpy as np
import pyarrow.parquet as pq
from scipy.stats import t as student_t

from qec_bp_benchmark.storage.minimal import LEGACY_SCHEMA, SCHEMA
from qec_bp_benchmark.storage.results import condition_prefix

if TYPE_CHECKING:
    import pandas as pd


Clock = Literal["cpu", "wall"]
REVTEX_COLUMN_SIZE = (3.4, 2.55)
REVTEX_DOUBLE_COLUMN_WIDTH = 7.0
_MARKERS = ("o", "s", "^", "D", "P", "X", "v", "<", ">")
_LINESTYLES = ("-", "--", "-.", ":")


@dataclass(frozen=True)
class _Point:
    family: str
    distance: int
    rounds: int
    physical_rate: float
    memory_basis: str | None
    decoder_id: str
    decoder_name: str
    decoder_profile: str
    logical_errors: int
    shots: int
    decode_times_ns: np.ndarray


def _values(value, *, name: str) -> tuple | None:
    if value is None:
        return None
    if isinstance(value, (str, bytes)) or not isinstance(value, Collection):
        value = (value,)
    else:
        value = tuple(value)
    if not value:
        raise ValueError(f"{name} must not be empty")
    return tuple(value)


def _selected_condition(
    condition: dict,
    *,
    codes: tuple | None,
    physical_rates: tuple | None,
    distances: tuple | None,
) -> bool:
    if codes is not None and condition["family"] not in codes:
        return False
    if distances is not None and int(condition["distance"]) not in distances:
        return False
    return physical_rates is None or any(
        math.isclose(float(condition["physical_rate"]), float(rate), rel_tol=0.0, abs_tol=1e-15)
        for rate in physical_rates
    )


def _selected_decoder(profile: dict, decoders: tuple | None) -> bool:
    if decoders is None:
        return True
    identities = {profile["decoder_id"], profile["name"], profile["profile"]}
    return any(value in identities for value in decoders)


def _current_context(run: Path) -> tuple[dict[str, dict], dict[str, dict], dict]:
    """Return filename-prefix conditions and enabled decoders from resolved config."""
    config = json.loads((run / "config_resolved.json").read_text())
    conditions = {}
    for code in config["experiment"]["instances"]:
        for rate in config["noise"]["expanded_rates"]:
            prefix = condition_prefix(
                code["family"], code["distance"], code["rounds"], rate,
                config["experiment"]["memory_basis"],
            )
            conditions[prefix] = {
                "family": code["family"], "distance": int(code["distance"]),
                "rounds": int(code["rounds"]), "physical_rate": float(rate),
                "memory_basis": config["experiment"]["memory_basis"],
            }
    decoders = {}
    for decoder in config["decoders"]:
        if decoder.get("enabled", True):
            decoders[decoder["name"]] = {
                "decoder_id": decoder["name"], "name": decoder["name"],
                "profile": decoder["profile"], "kind": decoder.get("kind", decoder["profile"]),
            }
    return conditions, decoders, config


def _current_points(
    result_path: Path,
    *,
    clock: Clock,
    codes: tuple | None,
    physical_rates: tuple | None,
    distances: tuple | None,
    decoders: tuple | None,
) -> list[_Point]:
    if clock != "wall":
        raise ValueError("minimal search_bp results save wall latency only; clock must be 'wall'")
    if not any(pq.read_schema(result_path).equals(schema, check_metadata=True)
               for schema in (SCHEMA, LEGACY_SCHEMA)):
        raise ValueError(f"unexpected result schema: {result_path}")
    conditions, profiles, _ = _current_context(result_path.parent.parent)
    prefix = result_path.name.removesuffix("_results.parquet")
    if prefix not in conditions:
        raise ValueError(f"unknown result condition: {prefix}")
    condition = conditions[prefix]
    if not _selected_condition(
        condition, codes=codes, physical_rates=physical_rates, distances=distances
    ):
        return []
    selected_profiles = {
        name: profile for name, profile in profiles.items()
        if _selected_decoder(profile, decoders)
    }
    if not selected_profiles:
        return []
    rows = pq.read_table(
        result_path, columns=["decoder_name", "logical_error", "latency_ns"]
    ).to_pylist()
    unknown = sorted({row["decoder_name"] for row in rows} - profiles.keys())
    if unknown:
        raise ValueError(f"unknown decoder names in {result_path}: {unknown}")
    points = []
    for name, profile in sorted(selected_profiles.items()):
        selected = [row for row in rows if row["decoder_name"] == name]
        if not selected:
            continue
        times = np.asarray([row["latency_ns"] for row in selected], dtype=np.int64)
        if np.any(times < 0):
            raise ValueError(f"decode time must be nonnegative: {result_path}")
        points.append(_Point(
            **condition, decoder_id=profile["decoder_id"], decoder_name=name,
            decoder_profile=profile["profile"],
            logical_errors=sum(bool(row["logical_error"]) for row in selected),
            shots=len(selected), decode_times_ns=times,
        ))
    return points


def _logical_errors_from_search(rows: list[dict], path: Path) -> int:
    errors = 0
    for row in rows:
        valid = bool(row["syndrome_valid"])
        mismatch = row["logical_mismatch"]
        if valid and mismatch is None:
            raise ValueError(f"valid decode has null logical_mismatch: {path}")
        errors += int(not valid or bool(mismatch))
    return errors


def _logical_errors_from_standard(rows: list[dict]) -> int:
    return sum(
        int(bool(row["decoding_failure"]) or bool(row["valid_logical_mismatch"]))
        for row in rows
    )


def _search_points(
    logical_path: Path,
    *,
    clock: Clock,
    codes: tuple | None,
    physical_rates: tuple | None,
    distances: tuple | None,
    decoders: tuple | None,
) -> list[_Point]:
    stem = logical_path.name.removesuffix("_logicalerror.parquet")
    condition_path = logical_path.with_name(f"{stem}_condition.parquet")
    decoder_path = logical_path.with_name(f"{stem}_decoders.parquet")
    condition_rows = pq.read_table(
        condition_path,
        columns=["condition_id", "family", "distance", "rounds", "physical_rate", "memory_basis"],
    ).to_pylist()
    if len(condition_rows) != 1:
        raise ValueError(f"condition file must contain exactly one row: {condition_path}")
    condition = condition_rows[0]
    if not _selected_condition(
        condition, codes=codes, physical_rates=physical_rates, distances=distances
    ):
        return []

    profiles = pq.read_table(
        decoder_path, columns=["decoder_id", "name", "profile"]
    ).to_pylist()
    profiles = {
        row["decoder_id"]: row for row in profiles if _selected_decoder(row, decoders)
    }
    if not profiles:
        return []
    time_column = "service_cpu_ns" if clock == "cpu" else "service_wall_ns"
    rows = pq.read_table(
        logical_path,
        columns=["condition_id", "decoder_id", "syndrome_valid", "logical_mismatch", time_column],
    ).to_pylist()
    points = []
    for decoder_id, profile in sorted(profiles.items()):
        selected = [row for row in rows if row["decoder_id"] == decoder_id]
        if not selected:
            continue
        if any(row["condition_id"] != condition["condition_id"] for row in selected):
            raise ValueError(f"logical-error row has the wrong condition_id: {logical_path}")
        times = np.asarray([row[time_column] for row in selected], dtype=np.int64)
        if np.any(times < 0):
            raise ValueError(f"decode time must be nonnegative: {logical_path}")
        points.append(_Point(
            family=condition["family"],
            distance=int(condition["distance"]),
            rounds=int(condition["rounds"]),
            physical_rate=float(condition["physical_rate"]),
            memory_basis=condition["memory_basis"],
            decoder_id=decoder_id,
            decoder_name=profile["name"],
            decoder_profile=profile["profile"],
            logical_errors=_logical_errors_from_search(selected, logical_path),
            shots=len(selected),
            decode_times_ns=times,
        ))
    return points


def _standard_points(
    logical_path: Path,
    *,
    clock: Clock,
    codes: tuple | None,
    physical_rates: tuple | None,
    distances: tuple | None,
    decoders: tuple | None,
) -> list[_Point]:
    time_column = "cpu_ns" if clock == "cpu" else "wall_ns"
    columns = [
        "instance_id", "decoder_id", "decoder_name", "decoder_profile", "family",
        "distance", "rounds", "physical_p", "decoding_failure",
        "valid_logical_mismatch", time_column,
    ]
    rows = pq.read_table(logical_path, columns=columns).to_pylist()
    grouped: dict[tuple, list[dict]] = {}
    for row in rows:
        condition = {
            "family": row["family"], "distance": row["distance"],
            "physical_rate": row["physical_p"],
        }
        profile = {
            "decoder_id": row["decoder_id"], "name": row["decoder_name"],
            "profile": row["decoder_profile"],
        }
        if not _selected_condition(
            condition, codes=codes, physical_rates=physical_rates, distances=distances
        ) or not _selected_decoder(profile, decoders):
            continue
        key = (
            row["instance_id"], row["decoder_id"], row["family"], int(row["distance"]),
            int(row["rounds"]), float(row["physical_p"]), row["decoder_name"],
            row["decoder_profile"],
        )
        grouped.setdefault(key, []).append(row)

    points = []
    for key, selected in sorted(grouped.items(), key=lambda item: repr(item[0])):
        _, decoder_id, family, distance, rounds, rate, decoder_name, decoder_profile = key
        times = np.asarray([row[time_column] for row in selected], dtype=np.int64)
        if np.any(times < 0):
            raise ValueError(f"decode time must be nonnegative: {logical_path}")
        points.append(_Point(
            family=family, distance=distance, rounds=rounds, physical_rate=rate,
            memory_basis=None, decoder_id=decoder_id, decoder_name=decoder_name,
            decoder_profile=decoder_profile,
            logical_errors=_logical_errors_from_standard(selected), shots=len(selected),
            decode_times_ns=times,
        ))
    return points


def _read_points(
    run_path: str | Path,
    *,
    clock: Clock,
    codes: str | Sequence[str] | None,
    physical_rates: float | Sequence[float] | None,
    distances: int | Sequence[int] | None,
    decoders: str | Sequence[str] | None,
) -> list[_Point]:
    if clock not in ("cpu", "wall"):
        raise ValueError("clock must be 'cpu' or 'wall'")
    run = Path(run_path).expanduser().resolve()
    data = run / "data"
    if not (run / "config_resolved.json").is_file() or not data.is_dir():
        raise ValueError(f"not a minimal simulation result directory: {run}")
    selections = {
        "codes": _values(codes, name="codes"),
        "physical_rates": _values(physical_rates, name="physical_rates"),
        "distances": _values(distances, name="distances"),
        "decoders": _values(decoders, name="decoders"),
    }
    points = []
    paths = sorted(data.glob("*_results.parquet"))
    if paths:
        for result_path in paths:
            points.extend(_current_points(result_path, clock=clock, **selections))
    else:
        paths = sorted(data.glob("*_logicalerror.parquet"))
        for logical_path in paths:
            stem = logical_path.name.removesuffix("_logicalerror.parquet")
            reader = (_search_points if logical_path.with_name(f"{stem}_condition.parquet").is_file()
                      else _standard_points)
            points.extend(reader(logical_path, clock=clock, **selections))
    if not paths:
        raise ValueError(f"no result Parquet files found in {data}")
    if not points:
        raise ValueError("the requested filters select no logical-error rows")

    seen = set()
    for point in points:
        key = (
            point.family, point.distance, point.rounds, point.memory_basis,
            point.decoder_id, point.physical_rate,
        )
        if key in seen:
            raise ValueError(
                "multiple saved conditions map to the same plotted point; select a single run/context"
            )
        seen.add(key)
    return points


def _validate_confidence(confidence: float) -> None:
    if not math.isfinite(confidence) or not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be finite and in (0, 1)")


def _wilson(errors: int, shots: int, confidence: float) -> tuple[float, float]:
    z = NormalDist().inv_cdf((1.0 + confidence) / 2.0)
    estimate = errors / shots
    denominator = 1.0 + z * z / shots
    center = (estimate + z * z / (2.0 * shots)) / denominator
    half = z * math.sqrt(
        estimate * (1.0 - estimate) / shots + z * z / (4.0 * shots * shots)
    ) / denominator
    return (
        0.0 if errors == 0 else max(0.0, center - half),
        1.0 if errors == shots else min(1.0, center + half),
    )


def _mean_interval(values: np.ndarray, confidence: float) -> tuple[float, float, float]:
    mean = float(np.mean(values))
    if len(values) < 2:
        return mean, math.nan, math.nan
    standard_error = float(np.std(values, ddof=1)) / math.sqrt(len(values))
    half = float(student_t.ppf((1.0 + confidence) / 2.0, len(values) - 1)) * standard_error
    return mean, max(0.0, mean - half), mean + half


def _series(points: list[_Point]) -> list[list[_Point]]:
    grouped: dict[tuple, list[_Point]] = {}
    for point in points:
        key = (
            point.decoder_id, point.distance, point.rounds, point.memory_basis,
            point.decoder_name, point.decoder_profile,
        )
        grouped.setdefault(key, []).append(point)
    output = []
    for key, values in sorted(grouped.items(), key=lambda item: repr(item[0])):
        ordered = sorted(values, key=lambda point: point.physical_rate)
        rates = [point.physical_rate for point in ordered]
        if len(rates) != len(set(rates)):
            raise ValueError(f"duplicate physical error rate in one plot series: {key}")
        output.append(ordered)
    return output


def _label(series: list[_Point], *, multiple_distances: bool, multiple_bases: bool) -> str:
    first = series[0]
    parts = [first.decoder_name]
    if multiple_distances:
        parts.append(f"d={first.distance}")
    if multiple_bases and first.memory_basis is not None:
        parts.append(first.memory_basis)
    return ", ".join(parts)


def _new_figure(figsize: tuple[float, float], dpi: int):
    if dpi <= 0:
        raise ValueError("dpi must be positive")
    if len(figsize) != 2 or any(not math.isfinite(value) or value <= 0 for value in figsize):
        raise ValueError("figsize must contain two positive finite values")
    import matplotlib.pyplot as plt
    return plt.subplots(figsize=figsize, dpi=dpi, layout="constrained")


def plot_decode_time_histogram(
    run_path: str | Path,
    *,
    code: str,
    physical_rate: float,
    distance: int | None = None,
    decoders: str | Sequence[str] | None = None,
    clock: Clock = "wall",
    bins: int | str | Sequence[float] = 50,
    dpi: int = 300,
) -> Figure:
    """Return decoder-specific decode-time histograms for one saved condition.

    ``code`` and ``physical_rate`` are required. ``distance`` is also required for
    the topological ``surface`` family and whenever the other selectors would leave
    more than one saved condition. Times include failed decodes and are converted
    from saved nanoseconds to microseconds. Every decoder owns one subplot with
    vertical lines at the arithmetic mean, 95th percentile, and 99th percentile.
    The caller owns the returned figure and may edit its axes or save it.
    """
    if code == "surface" and distance is None:
        raise ValueError("distance is required for the topological surface code")
    points = _read_points(
        run_path, clock=clock, codes=code, physical_rates=physical_rate,
        distances=distance, decoders=decoders,
    )
    conditions = {
        (point.family, point.distance, point.rounds, point.physical_rate, point.memory_basis)
        for point in points
    }
    if len(conditions) != 1:
        raise ValueError("histogram selection must identify exactly one saved condition")
    if isinstance(bins, int) and bins < 1:
        raise ValueError("bins must be positive")

    import matplotlib.pyplot as plt

    ordered = sorted(points, key=lambda point: (point.decoder_name, point.decoder_id))
    columns = min(2, len(ordered))
    rows = math.ceil(len(ordered) / columns)
    figsize = (REVTEX_COLUMN_SIZE[0], REVTEX_COLUMN_SIZE[1]) if len(ordered) == 1 else (
        REVTEX_DOUBLE_COLUMN_WIDTH, 2.35 * rows,
    )
    if dpi <= 0:
        raise ValueError("dpi must be positive")
    figure, axes = plt.subplots(
        rows, columns, figsize=figsize, dpi=dpi, squeeze=False, layout="constrained"
    )
    for ax, point in zip(axes.flat, ordered):
        values_us = point.decode_times_ns.astype(np.float64) / 1e3
        mean = float(np.mean(values_us))
        p95, p99 = np.quantile(values_us, (0.95, 0.99), method="linear")
        ax.hist(values_us, bins=bins, color="C0", alpha=0.72, edgecolor="white", linewidth=0.3)
        ax.axvline(mean, color="C1", linewidth=1.0, label=f"mean = {mean:.3g} μs")
        ax.axvline(p95, color="C2", linestyle="--", linewidth=1.0,
                   label=f"p95 = {p95:.3g} μs")
        ax.axvline(p99, color="C3", linestyle=":", linewidth=1.2,
                   label=f"p99 = {p99:.3g} μs")
        ax.set_title(point.decoder_name)
        ax.set_xlabel(f"{clock.capitalize()} decode time (μs)")
        ax.set_ylabel("Frequency")
        ax.grid(True, axis="y", alpha=0.2, linewidth=0.5)
        ax.legend(fontsize=6.5, frameon=False)
    for ax in axes.flat[len(ordered):]:
        ax.remove()
    family, selected_distance, rounds, rate, basis = next(iter(conditions))
    distance_text = f", d={selected_distance}" if distance is not None or family == "surface" else ""
    basis_text = f", {basis} memory" if basis is not None else ""
    figure.suptitle(
        f"{family}{distance_text}, R={rounds}, p={rate:g}{basis_text}", fontsize=10
    )
    return figure


def _profile_metric(profile: dict) -> str | None:
    identities = {
        str(profile.get("name", "")).lower(),
        str(profile.get("profile", "")).lower(),
        str(profile.get("kind", "")).lower(),
    }
    if "search_bp" in identities:
        return "osd_reach_rate"
    if any(identity.startswith("beam") for identity in identities):
        return "decoding_failure_rate"
    return None


def _search_rate_rows(
    logical_path: Path,
    *,
    codes: tuple | None,
    physical_rates: tuple | None,
    distances: tuple | None,
    decoders: tuple | None,
) -> list[dict]:
    stem = logical_path.name.removesuffix("_logicalerror.parquet")
    condition = pq.read_table(
        logical_path.with_name(f"{stem}_condition.parquet"),
        columns=["condition_id", "family", "distance", "rounds", "physical_rate", "memory_basis"],
    ).to_pylist()
    if len(condition) != 1:
        raise ValueError(f"condition file must contain exactly one row: {logical_path}")
    condition = condition[0]
    if not _selected_condition(
        condition, codes=codes, physical_rates=physical_rates, distances=distances
    ):
        return []
    profiles = pq.read_table(
        logical_path.with_name(f"{stem}_decoders.parquet"),
        columns=["decoder_id", "name", "profile", "kind"],
    ).to_pylist()
    profiles = {
        row["decoder_id"]: row for row in profiles
        if _selected_decoder(row, decoders) and _profile_metric(row) is not None
    }
    if not profiles:
        return []
    records = pq.read_table(
        logical_path,
        columns=["condition_id", "decoder_id", "syndrome_valid", "osd_entered", "timing_mode"],
    ).to_pylist()
    output = []
    for decoder_id, profile in sorted(profiles.items()):
        selected = [row for row in records if row["decoder_id"] == decoder_id]
        if not selected:
            continue
        if any(row["condition_id"] != condition["condition_id"] for row in selected):
            raise ValueError(f"logical-error row has the wrong condition_id: {logical_path}")
        timing_modes = {row["timing_mode"] for row in selected}
        if len(timing_modes) != 1:
            raise ValueError(f"decoder rows mix timing modes: {logical_path}")
        metric = _profile_metric(profile)
        if metric == "osd_reach_rate":
            if any(row["osd_entered"] is None for row in selected):
                raise ValueError(f"search_bp row has null osd_entered: {logical_path}")
            events = sum(bool(row["osd_entered"]) for row in selected)
        else:
            events = sum(not bool(row["syndrome_valid"]) for row in selected)
        shots = len(selected)
        rate = events / shots
        output.append({
            "condition_id": condition["condition_id"], "code": condition["family"],
            "distance": int(condition["distance"]), "rounds": int(condition["rounds"]),
            "physical_rate": float(condition["physical_rate"]),
            "memory_basis": condition["memory_basis"], "timing_mode": next(iter(timing_modes)),
            "decoder_id": decoder_id, "decoder": profile["name"],
            "decoder_profile": profile["profile"], "metric": metric,
            "events": events, "shots": shots, "rate": rate, "percent": 100.0 * rate,
        })
    return output


def _standard_rate_rows(
    logical_path: Path,
    *,
    codes: tuple | None,
    physical_rates: tuple | None,
    distances: tuple | None,
    decoders: tuple | None,
) -> list[dict]:
    columns = [
        "instance_id", "decoder_id", "decoder_name", "decoder_profile", "family",
        "distance", "rounds", "physical_p", "syndrome_valid", "timing_mode",
    ]
    records = pq.read_table(logical_path, columns=columns).to_pylist()
    grouped: dict[tuple, list[dict]] = {}
    for row in records:
        condition = {
            "family": row["family"], "distance": row["distance"],
            "physical_rate": row["physical_p"],
        }
        profile = {
            "decoder_id": row["decoder_id"], "name": row["decoder_name"],
            "profile": row["decoder_profile"],
        }
        if (_profile_metric(profile) != "decoding_failure_rate"
                or not _selected_condition(condition, codes=codes,
                                           physical_rates=physical_rates,
                                           distances=distances)
                or not _selected_decoder(profile, decoders)):
            continue
        key = (
            row["instance_id"], row["family"], int(row["distance"]), int(row["rounds"]),
            float(row["physical_p"]), row["timing_mode"], row["decoder_id"],
            row["decoder_name"], row["decoder_profile"],
        )
        grouped.setdefault(key, []).append(row)
    output = []
    for key, selected in sorted(grouped.items(), key=lambda item: repr(item[0])):
        condition_id, family, distance, rounds, rate_value, timing_mode, decoder_id, name, profile = key
        events = sum(not bool(row["syndrome_valid"]) for row in selected)
        shots = len(selected)
        rate = events / shots
        output.append({
            "condition_id": condition_id, "code": family, "distance": distance,
            "rounds": rounds, "physical_rate": rate_value, "memory_basis": None,
            "timing_mode": timing_mode, "decoder_id": decoder_id, "decoder": name,
            "decoder_profile": profile, "metric": "decoding_failure_rate",
            "events": events, "shots": shots, "rate": rate, "percent": 100.0 * rate,
        })
    return output


def _current_rate_rows(
    result_path: Path,
    *,
    codes: tuple | None,
    physical_rates: tuple | None,
    distances: tuple | None,
    decoders: tuple | None,
) -> list[dict]:
    schema = pq.read_schema(result_path)
    if not any(schema.equals(candidate, check_metadata=True)
               for candidate in (SCHEMA, LEGACY_SCHEMA)):
        raise ValueError(f"unexpected result schema: {result_path}")
    conditions, profiles, config = _current_context(result_path.parent.parent)
    prefix = result_path.name.removesuffix("_results.parquet")
    if prefix not in conditions:
        raise ValueError(f"unknown result condition: {prefix}")
    condition = conditions[prefix]
    if not _selected_condition(
        condition, codes=codes, physical_rates=physical_rates, distances=distances
    ):
        return []
    profiles = {
        name: profile for name, profile in profiles.items()
        if _selected_decoder(profile, decoders)
    }
    columns = ["decoder_name", "osd_called"]
    current = schema.equals(SCHEMA, check_metadata=True)
    if current:
        columns.append("correction_by_search")
    rows = pq.read_table(result_path, columns=columns).to_pylist()
    output = []
    for name, profile in sorted(profiles.items()):
        selected = [row["osd_called"] for row in rows if row["decoder_name"] == name]
        if not selected:
            continue
        known = [value for value in selected if value is not None]
        if not known:
            continue
        events = sum(known)
        output.append({
            "condition_id": prefix, "code": condition["family"],
            "distance": condition["distance"], "rounds": condition["rounds"],
            "physical_rate": condition["physical_rate"],
            "memory_basis": condition["memory_basis"],
            "timing_mode": config["timing"]["mode"],
            "decoder_id": profile["decoder_id"], "decoder": name,
            "decoder_profile": profile["profile"], "metric": "osd_call_rate",
            "events": events, "shots": len(known), "unknown": len(selected) - len(known),
            "rate": events / len(known), "percent": 100.0 * events / len(known),
        })
        if current and profile["profile"] == "search_bp":
            search_flags = [row["correction_by_search"] for row in rows
                            if row["decoder_name"] == name]
            search_known = [value for value in search_flags if value is not None]
            if search_known:
                search_events = sum(search_known)
                output.append({
                    "condition_id": prefix, "code": condition["family"],
                    "distance": condition["distance"], "rounds": condition["rounds"],
                    "physical_rate": condition["physical_rate"],
                    "memory_basis": condition["memory_basis"],
                    "timing_mode": config["timing"]["mode"],
                    "decoder_id": profile["decoder_id"], "decoder": name,
                    "decoder_profile": profile["profile"],
                    "metric": "correction_by_search_rate",
                    "events": search_events, "shots": len(search_known),
                    "unknown": len(search_flags) - len(search_known),
                    "rate": search_events / len(search_known),
                    "percent": 100.0 * search_events / len(search_known),
                })
    return output


def decoder_event_rate_table(
    run_path: str | Path,
    *,
    codes: str | Sequence[str] | None = None,
    physical_rates: float | Sequence[float] | None = None,
    distances: int | Sequence[int] | None = None,
    decoders: str | Sequence[str] | None = None,
) -> "pd.DataFrame":
    """Return condition-level decoder event rates available in the saved schema.

    Current ``search_bp_results/2`` rows report ``osd_call_rate`` and the exact
    ``correction_by_search_rate`` for SEARCH-BP. Historical minimal v1 rows report
    only OSD calls; historical wide SEARCH-BP rows report ``osd_reach_rate`` and
    beam rows report ``decoding_failure_rate``. The returned pandas table uses
    ``(code, distance, physical_rate)`` as its row
    MultiIndex and ``(decoder, metric)`` as its column MultiIndex. Cells contain
    rates in ``[0, 1]``. Storage IDs, profiles, timing metadata, counts, and other
    implementation metadata are not exposed in the displayed table.
    """
    run = Path(run_path).expanduser().resolve()
    data = run / "data"
    if not (run / "config_resolved.json").is_file() or not data.is_dir():
        raise ValueError(f"not a minimal simulation result directory: {run}")
    selections = {
        "codes": _values(codes, name="codes"),
        "physical_rates": _values(physical_rates, name="physical_rates"),
        "distances": _values(distances, name="distances"),
        "decoders": _values(decoders, name="decoders"),
    }
    output = []
    paths = sorted(data.glob("*_results.parquet"))
    if paths:
        for result_path in paths:
            output.extend(_current_rate_rows(result_path, **selections))
    else:
        paths = sorted(data.glob("*_logicalerror.parquet"))
        for logical_path in paths:
            stem = logical_path.name.removesuffix("_logicalerror.parquet")
            reader = (_search_rate_rows
                      if logical_path.with_name(f"{stem}_condition.parquet").is_file()
                      else _standard_rate_rows)
            output.extend(reader(logical_path, **selections))
    if not paths:
        raise ValueError(f"no result Parquet files found in {data}")
    if not output:
        raise ValueError("the requested filters select no rows with a known event flag")
    import pandas as pd

    frame = pd.DataFrame.from_records(output)
    table = frame.pivot(
        index=["code", "distance", "physical_rate"],
        columns=["decoder", "metric"],
        values="rate",
    )
    return table.sort_index().sort_index(axis="columns")


def plot_logical_error_rate(
    run_path: str | Path,
    *,
    codes: str | Sequence[str] | None = None,
    physical_rates: float | Sequence[float] | None = None,
    distances: int | Sequence[int] | None = None,
    decoders: str | Sequence[str] | None = None,
    confidence: float = 0.95,
    log_scale: bool = True,
    figsize: tuple[float, float] = REVTEX_COLUMN_SIZE,
    dpi: int = 300,
) -> list[Figure]:
    """Return one logical-error-rate figure per selected code family.

    Current minimal files use their contract-defined ``logical_error`` value.
    Historical files calculate decoder failure OR logical mismatch. Each shaded band is the
    two-sided Wilson score interval over physical shots.  Decoder filters match an
    exact decoder ID, name, or profile.  The caller owns the returned figures and
    may style or save them through ``figure.axes`` and ``figure.savefig``.
    """
    _validate_confidence(confidence)
    points = _read_points(
        run_path, clock="wall", codes=codes, physical_rates=physical_rates,
        distances=distances, decoders=decoders,
    )
    figures = []
    decoder_ids = sorted({point.decoder_id for point in points})
    colors = {decoder_id: f"C{index % 10}" for index, decoder_id in enumerate(decoder_ids)}
    for family in sorted({point.family for point in points}):
        selected = [point for point in points if point.family == family]
        series = _series(selected)
        multiple_distances = len({point.distance for point in selected}) > 1
        multiple_bases = len({point.memory_basis for point in selected}) > 1
        figure, ax = _new_figure(figsize, dpi)
        for index, values in enumerate(series):
            x = np.asarray([point.physical_rate for point in values], dtype=float)
            y = np.asarray([point.logical_errors / point.shots for point in values])
            intervals = [_wilson(point.logical_errors, point.shots, confidence) for point in values]
            low = np.asarray([interval[0] for interval in intervals])
            high = np.asarray([interval[1] for interval in intervals])
            first = values[0]
            color = colors[first.decoder_id]
            marker = _MARKERS[index % len(_MARKERS)]
            linestyle = _LINESTYLES[(index // len(_MARKERS)) % len(_LINESTYLES)]
            ax.plot(
                x, y, marker=marker, linestyle=linestyle, color=color, markersize=3.5,
                linewidth=1.0,
                label=_label(values, multiple_distances=multiple_distances,
                             multiple_bases=multiple_bases),
            )
            ax.fill_between(x, low, high, color=color, alpha=0.18, linewidth=0)
            if log_scale:
                zero = y == 0.0
                if np.any(zero):
                    ax.scatter(x[zero], high[zero], marker="v", facecolors="none",
                               edgecolors=color, s=18, linewidths=0.8, zorder=3)
        ax.set_xlabel("Physical error rate")
        ax.set_ylabel("Logical error rate")
        ax.set_title(family)
        if log_scale:
            if all(point.physical_rate > 0 for point in selected):
                ax.set_xscale("log")
            ax.set_yscale("log")
        ax.grid(True, which="both", alpha=0.2, linewidth=0.5)
        ax.legend(fontsize=6.5, frameon=False)
        figures.append(figure)
    return figures


def plot_mean_decode_time(
    run_path: str | Path,
    *,
    codes: str | Sequence[str] | None = None,
    physical_rates: float | Sequence[float] | None = None,
    distances: int | Sequence[int] | None = None,
    decoders: str | Sequence[str] | None = None,
    clock: Clock = "wall",
    confidence: float = 0.95,
    log_scale: bool = True,
    figsize: tuple[float, float] = REVTEX_COLUMN_SIZE,
    dpi: int = 300,
) -> list[Figure]:
    """Return one mean decode-time figure per selected code family.

    Times include every selected shot, including decoder failures, and are shown in
    milliseconds.  Since Wilson intervals apply only to binomial proportions, each
    shaded timing band is instead a two-sided Student-t confidence interval for the
    arithmetic mean.  The caller owns the returned figures.
    """
    _validate_confidence(confidence)
    points = _read_points(
        run_path, clock=clock, codes=codes, physical_rates=physical_rates,
        distances=distances, decoders=decoders,
    )
    figures = []
    decoder_ids = sorted({point.decoder_id for point in points})
    colors = {decoder_id: f"C{index % 10}" for index, decoder_id in enumerate(decoder_ids)}
    for family in sorted({point.family for point in points}):
        selected = [point for point in points if point.family == family]
        series = _series(selected)
        multiple_distances = len({point.distance for point in selected}) > 1
        multiple_bases = len({point.memory_basis for point in selected}) > 1
        figure, ax = _new_figure(figsize, dpi)
        for index, values in enumerate(series):
            x = np.asarray([point.physical_rate for point in values], dtype=float)
            intervals = [
                _mean_interval(point.decode_times_ns.astype(np.float64), confidence)
                for point in values
            ]
            mean = np.asarray([interval[0] for interval in intervals]) / 1e6
            low = np.asarray([interval[1] for interval in intervals]) / 1e6
            high = np.asarray([interval[2] for interval in intervals]) / 1e6
            first = values[0]
            color = colors[first.decoder_id]
            marker = _MARKERS[index % len(_MARKERS)]
            linestyle = _LINESTYLES[(index // len(_MARKERS)) % len(_LINESTYLES)]
            ax.plot(
                x, mean, marker=marker, linestyle=linestyle, color=color,
                markersize=3.5, linewidth=1.0,
                label=_label(values, multiple_distances=multiple_distances,
                             multiple_bases=multiple_bases),
            )
            ax.fill_between(x, low, high, color=color, alpha=0.18, linewidth=0)
        ax.set_xlabel("Physical error rate")
        ax.set_ylabel(f"Mean {clock} decode time (ms)")
        ax.set_title(family)
        if log_scale:
            if all(point.physical_rate > 0 for point in selected):
                ax.set_xscale("log")
            if all(np.all(point.decode_times_ns > 0) for point in selected):
                ax.set_yscale("log")
        ax.grid(True, which="both", alpha=0.2, linewidth=0.5)
        ax.legend(fontsize=6.5, frameon=False)
        figures.append(figure)
    return figures


__all__ = [
    "Clock", "REVTEX_COLUMN_SIZE", "REVTEX_DOUBLE_COLUMN_WIDTH",
    "plot_logical_error_rate", "plot_mean_decode_time", "plot_decode_time_histogram",
    "decoder_event_rate_table",
]
