"""Fixed one-round experiment grid and deterministic batch identities."""
from dataclasses import asdict, dataclass
from pathlib import Path
import hashlib
import json
import math
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DISTANCES = (5, 7, 9, 11, 13, 15)
NEAR_THRESHOLD_PS = (0.082, 0.084, 0.085, 0.086, 0.087, 0.088)
SUBTHRESHOLD_PS = (0.02, 0.03, 0.04, 0.05)
GRID_PROVENANCE = {
    "status": "project approximation: explicit prompt fallback",
    "original_near_threshold_grid": None,
    "original_subthreshold_grid": None,
    "inspection": "Lee Sec. 3.1/Fig. 3; current and historical 53b60e9 getting_started.ipynb; exact original grid not recovered",
    "paper": "https://quantum-journal.org/papers/q-2025-01-27-1609/",
}
FORCED_GAP_SOURCE = "existing color-code-stim comparative-decoding logical gap"
HISTORICAL_NOTE = ("The paper's ~8.2% crossing used historical double bit-flip injection. "
                   "The corrected repository documents ~8.6% and roughly halved LER. "
                   "This study uses corrected code, T=1, and targets coarse agreement.")


@dataclass(frozen=True)
class Phase2ATestConfig:
    """Configure the fixed corrected-code experiment, with counts in shots.

    Args:
        distances: Unique odd distances from 3 through 15; independent of the default grid.
        near_threshold_ps: Probabilities used for LOWESS crossing analysis.
        subthreshold_ps: Probabilities used for log-linear scaling analysis.
        shots_per_point: Positive fixed count per deduplicated (d,p).
        batch_size: Maximum shots returned by a worker at once.
        num_workers: CPU process count; pending work is bounded to twice this.
        master_seed: Nonnegative seed for the NumPy SeedSequence recipe.
        output_root: Parent directory of timestamped runs.
        verbose: Emit batch-completion progress via logging.

    Raises:
        ValueError: Invalid, duplicated, or unsupported parameters.
    """
    distances: tuple[int, ...] = DISTANCES
    near_threshold_ps: tuple[float, ...] = NEAR_THRESHOLD_PS
    subthreshold_ps: tuple[float, ...] = SUBTHRESHOLD_PS
    shots_per_point: int = 100_000
    batch_size: int = 5_000
    num_workers: int = 4
    master_seed: int = 20260912
    output_root: Path = PROJECT_ROOT / "results"
    verbose: bool = True

    def __post_init__(self):
        for name in ("distances", "near_threshold_ps", "subthreshold_ps"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        object.__setattr__(self, "output_root", Path(self.output_root))
        if not self.distances or any(type(d) is not int or d not in range(3, 16, 2) for d in self.distances):
            raise ValueError("Distances must be odd integers from 3 through 15")
        for values in (self.distances, self.near_threshold_ps, self.subthreshold_ps):
            if len(set(values)) != len(values):
                raise ValueError("Duplicate grid entries")
        if not self.probabilities or any(not math.isfinite(p) or not 0 < p < .5 for p in self.probabilities):
            raise ValueError("Physical probabilities must be finite and in (0,0.5)")
        for name in ("shots_per_point", "batch_size", "num_workers"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if type(self.master_seed) is not int or self.master_seed < 0:
            raise ValueError("master_seed must be a nonnegative integer")

    @property
    def probabilities(self) -> tuple[float, ...]:
        """Return sorted, deduplicated physical probabilities across both sweeps."""
        return tuple(sorted(set(self.near_threshold_ps + self.subthreshold_ps)))

    def resolved(self) -> dict:
        """Return a JSON-compatible complete configuration with absolute output path."""
        result = asdict(self)
        result["output_root"] = str(self.output_root.resolve())
        return result

    @property
    def config_hash(self) -> str:
        """Return SHA256 of all resolved configuration values, including infrastructure."""
        return hashlib.sha256(json.dumps(self.resolved(), sort_keys=True).encode()).hexdigest()


def config_id(distance: int, physical_error_rate: float) -> str:
    """Return a deterministic parameter identity independent of scheduling order."""
    return f"d{distance}_p{physical_error_rate:.12g}"


def batch_seed(master_seed: int, configuration_id: str, batch_id: int) -> int:
    """Derive a uint64 Stim seed from SHA256(config ID) and SeedSequence.

    Args:
        master_seed: Nonnegative integer.
        configuration_id: Stable ASCII parameter identity.
        batch_id: Nonnegative batch index within that configuration.
    Returns:
        Python integer representable as an unsigned 64-bit seed.
    """
    digest = hashlib.sha256(configuration_id.encode()).digest()
    words = np.frombuffer(digest, dtype="<u4").tolist()
    return int(np.random.SeedSequence([master_seed, *words, batch_id]).generate_state(1, dtype=np.uint64)[0])


@dataclass(frozen=True)
class BatchTask:
    """Immutable worker input; shot_index starts at offset within a configuration."""
    experiment_id: str
    config_id: str
    distance: int
    physical_error_rate: float
    batch_id: int
    offset: int
    shots: int
    seed: int


def batch_tasks(config: Phase2ATestConfig, experiment_id: str):
    """Yield deterministic bounded-size tasks; no shot arrays are allocated."""
    for distance in config.distances:
        for probability in config.probabilities:
            identity = config_id(distance, probability)
            for batch_id, offset in enumerate(range(0, config.shots_per_point, config.batch_size)):
                yield BatchTask(experiment_id, identity, distance, probability, batch_id, offset,
                                min(config.batch_size, config.shots_per_point-offset),
                                batch_seed(config.master_seed, identity, batch_id))
