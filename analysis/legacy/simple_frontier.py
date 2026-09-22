"""Small, column-projected summaries for the minimal simulation-data layout."""
from __future__ import annotations

from pathlib import Path
from typing import Literal, Sequence

import numpy as np
import pyarrow.parquet as pq

from .statistics import timing_statistics, wilson_interval

Clock = Literal["cpu", "wall"]
_DECODE_COLUMNS = (
    "condition_id", "decoder_id", "syndrome_valid",
    "block_failure", "service_cpu_ns", "service_wall_ns",
)


def _metric(failures: int, denominator: int, confidence: float) -> dict:
    low, high = wilson_interval(failures, denominator, confidence)
    return {
        "count": failures,
        "denominator": denominator,
        "rate": failures / denominator if denominator else None,
        "low": low,
        "high": high,
        "confidence": confidence,
    }


def summarize_run(
    run_path: str | Path, *, clock: Clock = "wall", confidence: float = 0.95,
) -> list[dict]:
    """Summarize one minimal-layout run without loading telemetry datasets.

    ``logical_error_rate`` is the rate of ``block_failure`` over all physical
    shots, including decoder failures and logical mismatches. Decode time is
    full adapter service time and includes failed outputs. Partial files from an
    interrupted run are readable after the writer has closed. Raises
    ``ValueError`` for an unsupported clock or missing result data.
    """
    if clock not in ("cpu", "wall"):
        raise ValueError("clock must be 'cpu' or 'wall'")
    run = Path(run_path).expanduser().resolve()
    data = run / "data"
    if not (run / "config_resolved.json").is_file() or not data.is_dir():
        raise ValueError("not a minimal simulation result directory")
    groups: dict[tuple[str, str], dict] = {}
    time_field = "service_cpu_ns" if clock == "cpu" else "service_wall_ns"

    def group_for(condition_id: str, decoder_id: str) -> dict:
        key = (condition_id, decoder_id)
        if key not in groups:
            groups[key] = {"valid": 0, "blocks": 0, "times": []}
        return groups[key]

    conditions = {}
    profiles = {}
    condition_paths = sorted(data.glob("*_condition.parquet"))
    for condition_path in condition_paths:
        stem = condition_path.name.removesuffix("_condition.parquet")
        condition_rows = pq.read_table(condition_path).to_pylist()
        profile_rows = pq.read_table(data / f"{stem}_decoders.parquet").to_pylist()
        if len(condition_rows) != 1:
            raise ValueError(f"condition file must contain one row: {condition_path}")
        condition = condition_rows[0]
        conditions[condition["condition_id"]] = condition
        profiles.update((row["decoder_id"], row) for row in profile_rows)
        path = data / f"{stem}_logicalerror.parquet"
        table = pq.read_table(path, columns=list(_DECODE_COLUMNS))
        condition_ids = table["condition_id"].to_pylist()
        decoder_ids = table["decoder_id"].to_pylist()
        valid = np.asarray(table["syndrome_valid"].to_numpy(), dtype=bool)
        blocks = np.asarray(table["block_failure"].to_numpy(), dtype=bool)
        times = np.asarray(table[time_field].to_numpy(), dtype=np.int64)
        for key in sorted(set(zip(condition_ids, decoder_ids))):
            condition_id, decoder_id = key
            mask = np.fromiter(
                (a == condition_id and b == decoder_id for a, b in zip(condition_ids, decoder_ids)),
                dtype=bool, count=len(condition_ids),
            )
            group = group_for(condition_id, decoder_id)
            group["valid"] += int(valid[mask].sum())
            group["blocks"] += int(blocks[mask].sum())
            group["times"].extend(times[mask].tolist())

    if not condition_paths:
        standard_columns = [
            "run_id", "instance_id", "decoder_id", "decoder_name", "decoder_profile",
            "family", "distance", "rounds", "physical_p", "syndrome_valid",
            "block_failure", "cpu_ns", "wall_ns",
        ]
        standard_time = "cpu_ns" if clock == "cpu" else "wall_ns"
        for path in sorted(data.glob("*_logicalerror.parquet")):
            for row in pq.read_table(path, columns=standard_columns).to_pylist():
                condition_id = row["instance_id"]
                conditions[condition_id] = {
                    "run_id": row["run_id"], "family": row["family"],
                    "distance": row["distance"], "rounds": row["rounds"],
                    "physical_rate": row["physical_p"],
                }
                profiles[row["decoder_id"]] = {
                    "name": row["decoder_name"], "profile": row["decoder_profile"],
                }
                group = group_for(condition_id, row["decoder_id"])
                group["valid"] += int(row["syndrome_valid"])
                group["blocks"] += int(row["block_failure"])
                group["times"].append(row[standard_time])

    rows = []
    for (condition_id, decoder_id), group in sorted(groups.items()):
        condition = conditions[condition_id]
        profile = profiles[decoder_id]
        times = timing_statistics(group["times"], quantiles=(0.5, 0.95))
        valid = group["valid"]
        rows.append({
            "run_id": condition["run_id"],
            "run_status": "saved",
            "condition_id": condition_id,
            "decoder_id": decoder_id,
            "decoder_name": profile["name"],
            "decoder_profile": profile["profile"],
            "family": condition["family"],
            "distance": int(condition["distance"]),
            "physical_rate": condition["physical_rate"],
            "rounds": int(condition["rounds"]),
            "shots": len(group["times"]),
            "valid_outputs": valid,
            "block_failures": group["blocks"],
            "logical_error_rate": _metric(group["blocks"], len(group["times"]), confidence),
            "clock": clock,
            "decode_time": times,
        })
    if not rows:
        raise ValueError("no logical-error data found")
    return rows


# Kept as a source-compatible name for notebooks created during HSBP-FB work.
summarize_frontier_run = summarize_run


def plot_frontier_comparison(
    rows: Sequence[dict], *, title: str | None = None,
) -> list[object]:
    """Build one in-memory Matplotlib figure per code family/distance."""
    import matplotlib.pyplot as plt

    contexts = sorted({(row["family"], row["distance"]) for row in rows})
    decoders = sorted({row["decoder_id"]: row["decoder_name"] for row in rows}.items())
    colors = {decoder_id: f"C{i % 10}" for i, (decoder_id, _) in enumerate(decoders)}
    figures = []
    for family, distance in contexts:
        context_rows = [row for row in rows if row["family"] == family and row["distance"] == distance]
        fig, (rate_ax, time_ax) = plt.subplots(1, 2, figsize=(14, 5.5))
        for decoder_id, decoder_name in decoders:
            points = sorted(
                (row for row in context_rows if row["decoder_id"] == decoder_id),
                key=lambda row: row["physical_rate"],
            )
            if not points:
                continue
            color = colors[decoder_id]
            label = decoder_name
            x = [row["physical_rate"] for row in points]
            rate = [row["logical_error_rate"]["rate"] for row in points]
            low = [row["logical_error_rate"]["low"] for row in points]
            high = [row["logical_error_rate"]["high"] for row in points]
            positive = [value is not None and value > 0 for value in rate]
            if any(positive):
                indices = [i for i, value in enumerate(positive) if value]
                rate_ax.errorbar(
                    [x[i] for i in indices], [rate[i] for i in indices],
                    yerr=[[rate[i] - low[i] for i in indices], [high[i] - rate[i] for i in indices]],
                    marker="o", linestyle="-", color=color, label=label,
                )
            else:
                rate_ax.plot([], [], marker="o", color=color, label=label)
            for i, value in enumerate(rate):
                if value == 0:
                    rate_ax.plot(x[i], high[i], marker="v", mfc="none", color=color)
            means = [point["decode_time"]["mean_ns"] / 1e6 for point in points]
            p95 = [point["decode_time"]["p95_ns"] / 1e6 for point in points]
            time_ax.plot(x, means, marker="o", color=color, label=label)
            time_ax.plot(x, p95, marker="+", linestyle="--", color=color, alpha=0.75)

        rate_ax.set_title("Logical error rate")
        rate_ax.set_ylabel("Block failure / all physical shots")
        rate_ax.set_xlabel("Physical error rate")
        rate_ax.set_xscale("log"); rate_ax.set_yscale("log")
        rate_ax.grid(True, which="both", alpha=0.2)
        time_ax.set_title("Decode time")
        time_ax.set_ylabel("Service time (ms); circle=mean, +=p95")
        time_ax.set_xlabel("Physical error rate")
        time_ax.set_xscale("log"); time_ax.set_yscale("log")
        time_ax.grid(True, which="both", alpha=0.2)
        clock = context_rows[0]["clock"]
        comparison = title or f"Logical error rate vs {clock} decode time"
        fig.suptitle(f"{family} d={distance} — {comparison} ({context_rows[0]['run_status']})")
        handles, labels = rate_ax.get_legend_handles_labels()
        fig.legend(handles, labels, loc="outside lower center", fontsize=8)
        fig.tight_layout(rect=(0, 0.12, 1, 0.94))
        figures.append(fig)
    return figures
