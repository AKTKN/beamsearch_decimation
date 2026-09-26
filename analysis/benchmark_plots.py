"""Direct Parquet readers and paper-sized benchmark comparison figures.

The public plotting functions own the complete workflow: they select a saved run,
read its resolved labels and only the result columns required for one plot, then
return new Matplotlib ``Figure`` objects. They support active benchmark_results/2
and benchmark_results/3 files. Historical readers live
under analysis.legacy. They do not load
telemetry, join runs, bootstrap samples, write files, or create summary reports.
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

from qec_bp_benchmark.storage.minimal import (
    SCHEMA, SCHEMA_VERSION, LEGACY_SCHEMA, LEGACY_SCHEMA_VERSION, result_table,
)
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
    converged: int | None
    shots: int
    decode_times_ns: np.ndarray
    total_iterations: np.ndarray


@dataclass(frozen=True)
class RunCondition:
    """One saved condition and its result file within an active run."""

    result_path: Path
    family: str
    distance: int
    rounds: int
    physical_rate: float
    memory_basis: str | None
    schema_version: str


def _result_version(path: Path) -> str:
    saved = pq.read_schema(path)
    if saved.equals(SCHEMA, check_metadata=True):
        return SCHEMA_VERSION
    if saved.equals(LEGACY_SCHEMA, check_metadata=True):
        return LEGACY_SCHEMA_VERSION
    raise ValueError(f"unexpected result schema: {path}")


def list_run_conditions(run_path: str | Path) -> list[RunCondition]:
    """Discover saved active result files using the resolved run configuration.

    Only files that match a configured condition and the exact current schema are
    returned. This lets notebook consumers enumerate every saved condition without
    guessing rates or distances from a filename or configuration sweep.
    """
    run = Path(run_path).expanduser().resolve()
    data = run / "data"
    if not (run / "config_resolved.json").is_file() or not data.is_dir():
        raise ValueError(f"not a minimal simulation result directory: {run}")
    conditions, _, _ = _current_context(run)
    paths = sorted(data.glob("*_results.parquet"))
    if not paths:
        raise ValueError(f"no active result Parquet files found in {data}")
    saved = []
    for path in paths:
        prefix = path.name.removesuffix("_results.parquet")
        if prefix not in conditions:
            raise ValueError(f"unknown result condition: {prefix}")
        saved.append(RunCondition(result_path=path,
                                  schema_version=_result_version(path),
                                  **conditions[prefix]))
    return saved


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
    rounds: tuple | None,
) -> bool:
    if codes is not None and condition["family"] not in codes:
        return False
    if distances is not None and int(condition["distance"]) not in distances:
        return False
    if rounds is not None and int(condition["rounds"]) not in rounds:
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
    rounds: tuple | None,
    decoders: tuple | None,
) -> list[_Point]:
    if clock != "wall":
        raise ValueError("minimal results save wall latency only; clock must be 'wall'")
    version = _result_version(result_path)
    conditions, profiles, _ = _current_context(result_path.parent.parent)
    prefix = result_path.name.removesuffix("_results.parquet")
    if prefix not in conditions:
        raise ValueError(f"unknown result condition: {prefix}")
    condition = conditions[prefix]
    if not _selected_condition(
        condition, codes=codes, physical_rates=physical_rates,
        distances=distances, rounds=rounds,
    ):
        return []
    selected_profiles = {
        name: profile for name, profile in profiles.items()
        if _selected_decoder(profile, decoders)
    }
    if not selected_profiles:
        return []
    rows = result_table(pq.read_table(result_path).to_pylist(),
                        schema_version=version).to_pylist()
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
            converged=(sum(row["converged"] for row in selected)
                       if version == SCHEMA_VERSION else None),
            shots=len(selected), decode_times_ns=times,
            total_iterations=np.asarray([row["total_iterations"] for row in selected], dtype=np.int64),
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
    rounds: int | Sequence[int] | None = None,
) -> list[_Point]:
    if clock != "wall":
        raise ValueError("minimal results save wall latency only; clock must be 'wall'")
    conditions = list_run_conditions(run_path)
    selections = {
        "codes": _values(codes, name="codes"),
        "physical_rates": _values(physical_rates, name="physical_rates"),
        "distances": _values(distances, name="distances"),
        "rounds": _values(rounds, name="rounds"),
        "decoders": _values(decoders, name="decoders"),
    }
    points = []
    for condition in conditions:
        points.extend(_current_points(condition.result_path, clock=clock, **selections))
    if not points:
        raise ValueError("the requested filters select no logical-error rows")
    seen = set()
    for point in points:
        key = (point.family, point.distance, point.rounds, point.memory_basis,
               point.decoder_id, point.physical_rate)
        if key in seen:
            raise ValueError("multiple saved conditions map to the same plotted point")
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


def _label(series: list[_Point], *, multiple_distances: bool, multiple_rounds: bool,
           multiple_bases: bool) -> str:
    first = series[0]
    parts = [first.decoder_name]
    if multiple_distances:
        parts.append(f"d={first.distance}")
    if multiple_rounds:
        parts.append(f"R={first.rounds}")
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
    rounds: int | None = None,
    decoders: str | Sequence[str] | None = None,
    clock: Clock = "wall",
    bins: int | str | Sequence[float] = 50,
    dpi: int = 300,
) -> Figure:
    """Return decoder-specific decode-time histograms for one saved condition.

    ``code`` and ``physical_rate`` are required. ``distance`` is also required for
    the topological ``surface`` family and whenever the other selectors would leave
    more than one saved condition. Use ``rounds`` to distinguish conditions with
    the same code, rate, and distance. Times include failed decodes and are converted
    from saved nanoseconds to microseconds. Every decoder owns one subplot with
    vertical lines at the arithmetic mean, 95th percentile, and 99th percentile.
    The caller owns the returned figure and may edit its axes or save it.
    """
    if code == "surface" and distance is None:
        raise ValueError("distance is required for the topological surface code")
    points = _read_points(
        run_path, clock=clock, codes=code, physical_rates=physical_rate,
        distances=distance, rounds=rounds, decoders=decoders,
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
        multiple_rounds = len({point.rounds for point in selected}) > 1
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
                             multiple_rounds=multiple_rounds,
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


def plot_convergence_rate(
    run_path: str | Path,
    *,
    codes: str | Sequence[str] | None = None,
    physical_rates: float | Sequence[float] | None = None,
    distances: int | Sequence[int] | None = None,
    decoders: str | Sequence[str] | None = None,
    confidence: float = 0.95,
    figsize: tuple[float, float] = REVTEX_COLUMN_SIZE,
    dpi: int = 300,
) -> list[Figure]:
    """Plot syndrome-valid convergence from new result files, one family per figure.

    BP-OSD's value is BP-stage convergence before OSD. The point denominator is
    every physical shot; Wilson intervals are shown on a linear probability axis.
    """
    _validate_confidence(confidence)
    points = _read_points(run_path, clock="wall", codes=codes,
                          physical_rates=physical_rates, distances=distances,
                          decoders=decoders)
    if any(point.converged is None for point in points):
        raise ValueError("convergence was not saved by benchmark_results/2")
    figures = []
    decoder_ids = sorted({point.decoder_id for point in points})
    colors = {name: f"C{index % 10}" for index, name in enumerate(decoder_ids)}
    for family in sorted({point.family for point in points}):
        selected = [point for point in points if point.family == family]
        multiple_distances = len({point.distance for point in selected}) > 1
        multiple_rounds = len({point.rounds for point in selected}) > 1
        multiple_bases = len({point.memory_basis for point in selected}) > 1
        figure, ax = _new_figure(figsize, dpi)
        for index, values in enumerate(_series(selected)):
            x = np.asarray([point.physical_rate for point in values], dtype=float)
            y = np.asarray([point.converged / point.shots for point in values])
            intervals = [_wilson(point.converged, point.shots, confidence)
                         for point in values]
            low = np.asarray([interval[0] for interval in intervals])
            high = np.asarray([interval[1] for interval in intervals])
            first = values[0]
            ax.plot(x, y, marker=_MARKERS[index % len(_MARKERS)],
                    linestyle=_LINESTYLES[(index // len(_MARKERS)) % len(_LINESTYLES)],
                    color=colors[first.decoder_id], markersize=3.5, linewidth=1.0,
                    label=_label(values, multiple_distances=multiple_distances,
                                 multiple_rounds=multiple_rounds,
                                 multiple_bases=multiple_bases))
            ax.fill_between(x, low, high, color=colors[first.decoder_id],
                            alpha=0.18, linewidth=0)
        ax.set_xlabel("Physical error rate")
        ax.set_ylabel("Convergence rate")
        ax.set_ylim(0.0, 1.0)
        ax.set_title(family)
        if all(point.physical_rate > 0 for point in selected):
            ax.set_xscale("log")
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
        multiple_rounds = len({point.rounds for point in selected}) > 1
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
                             multiple_rounds=multiple_rounds,
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


def plot_mean_total_iterations(
    run_path: str | Path,
    *,
    codes: str | Sequence[str] | None = None,
    physical_rates: float | Sequence[float] | None = None,
    distances: int | Sequence[int] | None = None,
    decoders: str | Sequence[str] | None = None,
    confidence: float = 0.95,
    log_scale: bool = False,
    figsize: tuple[float, float] = REVTEX_COLUMN_SIZE,
    dpi: int = 300,
) -> list[Figure]:
    """Return mean completed BP iterations, including failed shots, by code family."""
    _validate_confidence(confidence)
    points = _read_points(run_path, clock="wall", codes=codes,
                          physical_rates=physical_rates, distances=distances,
                          decoders=decoders)
    figures = []
    decoder_ids = sorted({point.decoder_id for point in points})
    colors = {decoder_id: f"C{index % 10}" for index, decoder_id in enumerate(decoder_ids)}
    for family in sorted({point.family for point in points}):
        selected = [point for point in points if point.family == family]
        series = _series(selected)
        multiple_distances = len({point.distance for point in selected}) > 1
        multiple_rounds = len({point.rounds for point in selected}) > 1
        multiple_bases = len({point.memory_basis for point in selected}) > 1
        figure, ax = _new_figure(figsize, dpi)
        for index, values in enumerate(series):
            x = np.asarray([point.physical_rate for point in values], dtype=float)
            intervals = [_mean_interval(point.total_iterations.astype(np.float64), confidence)
                         for point in values]
            mean = np.asarray([interval[0] for interval in intervals])
            low = np.asarray([interval[1] for interval in intervals])
            high = np.asarray([interval[2] for interval in intervals])
            first = values[0]
            color = colors[first.decoder_id]
            marker = _MARKERS[index % len(_MARKERS)]
            linestyle = _LINESTYLES[(index // len(_MARKERS)) % len(_LINESTYLES)]
            ax.plot(x, mean, marker=marker, linestyle=linestyle, color=color,
                    markersize=3.5, linewidth=1.0,
                    label=_label(values, multiple_distances=multiple_distances,
                                 multiple_rounds=multiple_rounds,
                                 multiple_bases=multiple_bases))
            ax.fill_between(x, low, high, color=color, alpha=0.18, linewidth=0)
        ax.set_xlabel("Physical error rate")
        ax.set_ylabel("Mean total BP iterations")
        ax.set_title(family)
        if log_scale:
            if all(point.physical_rate > 0 for point in selected):
                ax.set_xscale("log")
            if all(np.all(point.total_iterations > 0) for point in selected):
                ax.set_yscale("log")
        ax.grid(True, which="both", alpha=0.2, linewidth=0.5)
        ax.legend(fontsize=6.5, frameon=False)
        figures.append(figure)
    return figures


__all__ = [
    "Clock", "RunCondition", "list_run_conditions", "REVTEX_COLUMN_SIZE", "REVTEX_DOUBLE_COLUMN_WIDTH",
    "plot_logical_error_rate", "plot_convergence_rate", "plot_mean_decode_time", "plot_mean_total_iterations",
    "plot_decode_time_histogram",
]
