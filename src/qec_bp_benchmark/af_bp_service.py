"""Thin truth-free Python boundary for the standalone native AF-BP-1.0 service.

Construction copies binary H/A and physical probabilities. Each decode makes
one native call; all BP, graph and iteration work remains in C++. The active
decoder adapter registers this service without passing logical truth.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import sparse

from . import _af_bp_service as native
from .native_sources import af_bp_service_digest

ROOT = Path(__file__).resolve().parents[2]


def source_digest() -> str:
    """Match the ordered CMake source digest; source checkout required."""
    return af_bp_service_digest(ROOT)


@dataclass(frozen=True)
class FailureOptions:
    residual_radius: int = 2
    distance_decay: float = 0.5
    uncertainty_weight: float = 1.0
    oscillation_weight: float = 1.0
    selection: Literal["top_k", "threshold"] = "top_k"
    top_k: int = 32
    threshold: float = 0.5


@dataclass(frozen=True)
class AFBPConfig:
    initial_parallel: bool = True
    initial_iteration_budget: int = 50
    transformed_iteration_budget: int = 50
    bp_variant: Literal["parallel", "serial", "qdither"] = "parallel"
    serial_order: Literal["natural", "random_per_iteration"] = "random_per_iteration"
    scaling_factor: float = 1.0
    history_window: int = 8
    graph_rounds: int = 4
    n_fact: int = 1
    factorization_policy: Literal["adaptive_cycle", "shen_cycle_count"] = "adaptive_cycle"
    failure: FailureOptions = field(default_factory=FailureOptions)
    atanh_epsilon: float = 1e-12
    phase1_iterations: int = 30
    num_chains: int = 0
    chain_iterations: int = 20
    alpha: float = 0.0
    beta: float = 1.0
    rho: float = 0.0
    seed: int = 0
    seed_policy: Literal["fixed", "syndrome_derived"] = "syndrome_derived"
    qdither_handoff: Literal["paper", "graph_warm"] = "graph_warm"


@dataclass(frozen=True)
class AFBPResult:
    valid: bool
    initial_bp_converged: bool
    first_transform_converged: bool | None
    correction: NDArray[np.uint8] | None
    prediction: NDArray[np.uint8] | None
    total_iterations: int
    graph_instances: int
    factorizations: int
    status: str
    last_physical_hard: NDArray[np.uint8]
    calls: tuple[object, ...] = ()
    transforms: tuple[object, ...] = ()


def _rows(matrix: ArrayLike | sparse.spmatrix, n: int | None = None) -> tuple[list[list[int]], int]:
    csr = sparse.csr_matrix(matrix)
    if csr.ndim != 2 or (n is not None and csr.shape[1] != n):
        raise ValueError("binary matrix has unexpected shape")
    csr.sum_duplicates()
    if np.any(csr.data != 1):
        raise ValueError("matrix entries must be binary")
    csr.sort_indices()
    return ([csr.indices[csr.indptr[i]:csr.indptr[i + 1]].tolist()
             for i in range(csr.shape[0])], csr.shape[1])


class AFBPDecoder:
    """Immutable prepared native decoder; decode accepts syndrome (m,) only.

    H/A are binary matrices with n physical columns; probabilities are finite
    (n,) in (0,1). Returned arrays are owned. Invalid input raises ValueError;
    native construction or decode errors propagate. Logical truth is never input.
    """
    kind = "af_bp"
    profile = "af_bp_v1"
    name = "af_bp_v1"
    algorithm_version = "AF-BP-1.0"

    def __init__(self, h: ArrayLike | sparse.spmatrix,
                 a: ArrayLike | sparse.spmatrix,
                 probabilities: ArrayLike,
                 config: AFBPConfig = AFBPConfig()) -> None:
        if not isinstance(config, AFBPConfig):
            raise TypeError("config must be AFBPConfig")
        h_rows, n = _rows(h)
        a_rows, _ = _rows(a, n)
        p = np.asarray(probabilities, dtype=np.float64)
        if p.shape != (n,) or not np.isfinite(p).all() or np.any((p <= 0) | (p >= 1)):
            raise ValueError("probabilities must have shape (n,) and be in (0,1)")
        if native.build_identity()["source_sha256"] != source_digest():
            raise RuntimeError("stale AF-BP service binary; rebuild the project extension")
        settings = native.DecoderSettings()
        for name in AFBPConfig.__dataclass_fields__:
            if name != "failure":
                setattr(settings, name, getattr(config, name))
        failure = native.FailureSettings()
        for name in FailureOptions.__dataclass_fields__:
            setattr(failure, name, getattr(config.failure, name))
        settings.failure = failure
        self._native = native.Decoder(h_rows, a_rows, p.tolist(), settings)
        self.config = config
        self.shape = (len(h_rows), n)
        self.observable_count = len(a_rows)

    def decode(self, syndrome: ArrayLike, *, diagnostics: bool = False) -> AFBPResult:
        """Run one complete native AF-BP service on a binary syndrome (m,)."""
        bits = np.asarray(syndrome)
        if bits.shape != (self.shape[0],) or not np.isin(bits, (0, 1)).all():
            raise ValueError("syndrome must be binary with shape (m,)")
        result = self._native.decode(bits.astype(np.int32).tolist(), diagnostics)
        correction = np.asarray(result.correction, dtype=np.uint8) if result.valid else None
        prediction = np.asarray(result.prediction, dtype=np.uint8) if result.valid else None
        return AFBPResult(bool(result.valid), bool(result.initial_bp_converged),
                          result.first_transform_converged, correction, prediction,
                          int(result.total_iterations), int(result.graph_instances),
                          int(result.factorizations), str(result.status),
                          np.asarray(result.last_physical_hard, dtype=np.uint8),
                          tuple(result.calls), tuple(result.transforms))


build_identity = native.build_identity
__all__ = ["AFBPConfig", "AFBPDecoder", "AFBPResult", "FailureOptions", "build_identity"]
