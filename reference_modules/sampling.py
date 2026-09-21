"""Sample each physical batch once and decode its two paired representations."""
from functools import lru_cache
import numpy as np
import pandas as pd
from color_code_stim import ColorCode
from color_code_stim.noise_model import NoiseModel
from .config import BatchTask
from .pairing import validate_pairing


@lru_cache(maxsize=2)
def _code_pair(distance: int, physical_error_rate: float):
    options = dict(d=distance, rounds=1, circuit_type="tri", cnot_schedule="tri_optimal",
                   noise_model=NoiseModel(bitflip=physical_error_rate))
    ordinary = ColorCode(**options)
    comparative = ColorCode(**options, comparative_decoding=True)
    validate_pairing(ordinary.circuit, comparative.circuit)
    return ordinary, comparative


def select_swim(swim_by_color: np.ndarray, selected_colors: np.ndarray,
                color_order: tuple[str, ...]) -> np.ndarray:
    """Select decoder-chosen color scores, never minimum-over-colors aggregation.

    Args:
        swim_by_color: Float array of shape (shots, colors), in color_order.
        selected_colors: Integer canonical rgb indices, shape (shots,).
        color_order: Explicit labels of the supplied score columns.
    Returns:
        Selected swim distance in ordinary edge-weight units, shape (shots,).
    Raises:
        ValueError: Invalid color labels or shapes.
    """
    if set(color_order) != set("rgb") or len(color_order) != 3:
        raise ValueError("The fixed experiment requires all three color branches")
    selected_colors = np.asarray(selected_colors)
    if swim_by_color.shape != (len(selected_colors), 3) or not np.isin(selected_colors, [0,1,2]).all():
        raise ValueError("Invalid score shape or selected color")
    indices = np.array([color_order.index(c) for c in "rgb"])[selected_colors.astype(int)]
    return swim_by_color[np.arange(len(indices)), indices]


def sample_batch(task: BatchTask) -> pd.DataFrame:
    """Return one paired batch table; sample physical shots exactly once.

    Args:
        task: Stable parameters, count and uint64 seed.
    Returns:
        DataFrame with task.shots rows; metric-specific failure labels and
        redundant source logical gap retained for auditing the alias.
    Raises:
        AssertionError: Selected-color, validity, or hard-decision invariants fail.

    Notes:
        A small prefix is decoded without SO to audit the read-only SO contract.
        Comparative decoding overwrites the appended parity with forced inputs.
    """
    ordinary, comparative = _code_pair(task.distance, task.physical_error_rate)
    detectors, actual = ordinary.sample(task.shots, seed=task.seed)
    prediction, extra = ordinary.decode(detectors, full_output=True, compute_swim_distance=True)
    prefix = min(16, task.shots)
    off_prediction, off = ordinary.decode(detectors[:prefix], full_output=True)
    np.testing.assert_array_equal(prediction[:prefix], off_prediction)
    for key in ("weights", "best_colors"):
        np.testing.assert_array_equal(extra[key][:prefix], off[key])
    comparative_input = np.concatenate((detectors, np.asarray(actual).reshape(-1,1)), axis=1)
    comparative_prediction, comparative_extra = comparative.decode(comparative_input, full_output=True)
    selected = select_swim(extra["swim_distances_by_color"], extra["best_colors"], tuple(extra["color_order"]))
    np.testing.assert_array_equal(selected, extra["selected_swim_distance"])
    records = dict(
        experiment_id=task.experiment_id, config_id=task.config_id,
        batch_id=task.batch_id, shot_index=np.arange(task.offset, task.offset+task.shots),
        batch_seed=np.full(task.shots, task.seed, dtype=np.uint64),
        distance=task.distance, physical_error_rate=task.physical_error_rate,
        actual_observable=np.asarray(actual, dtype=bool), ordinary_prediction=np.asarray(prediction, dtype=bool),
        ordinary_logical_error=prediction != actual,
        ordinary_selected_color=np.array(list("rgb"))[extra["best_colors"]],
        ordinary_solution_weight=extra["weights"], selected_swim_distance=selected,
        comparative_prediction=np.asarray(comparative_prediction, dtype=bool),
        comparative_logical_error=comparative_prediction != actual,
        forced_gap=comparative_extra["logical_gaps"],
        comparative_logical_gap=comparative_extra["logical_gaps"],
    )
    for index, color in enumerate(extra["color_order"]):
        records[f"stage2_weight_{color}"] = extra["stage2_weights_by_color"][:,index]
        records[f"swim_distance_{color}"] = extra["swim_distances_by_color"][:,index]
    return pd.DataFrame(records)
