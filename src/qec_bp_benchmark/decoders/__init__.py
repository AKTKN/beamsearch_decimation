"""Active, truth-free baseline decoder services.

AF-BP and Relay-BP names are reserved until their services exist. Historical
decimation services are archived under ``qec_bp_benchmark.legacy.decimation``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import hashlib
import importlib
import json
import math
from pathlib import Path

import numpy as np

from ..config import Bposd, Beam, Decoder, require_available_decoder
from ..dem.model import DetectorProblem
from ..identity import decoder_identity

ROOT = Path(__file__).resolve().parents[3]


@lru_cache(maxsize=2)
def implementation_identity(profile: str) -> dict:
    """Return pinned upstream and actual imported binary identity."""
    require_available_decoder(profile)
    key, module_name = (
        ("ldpc", "ldpc.bposd_decoder._bposd_decoder") if profile == "bposd" else
        ("BeamSearchDecoder", "beam_search_decoder._beam_search_decoder")
    )
    module = importlib.import_module(module_name)
    expected = ROOT / "external_lib" / key
    if expected.resolve() not in Path(module.__file__).resolve().parents:
        raise RuntimeError(f"unintended native baseline import: {module.__file__}")
    manifest = json.loads((ROOT / "external_lib/manifest.lock.json").read_text())
    return {
        "upstream_commit": manifest["dependencies"][key]["commit"],
        "native_sha256": hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),
        "adapter_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }


@dataclass(frozen=True)
class DecodeResult:
    """Owned correction (n,) and prediction (k,), both null on failure."""
    correction: np.ndarray | None
    prediction: np.ndarray | None
    syndrome_valid: bool
    status: str
    native_status: str
    cost: float | None
    counters: dict = field(default_factory=dict)
    diagnostics: dict | None = None
    phases: dict | None = None
    hybrid_summary: dict | None = None
    osd_called: bool | None = None
    correction_by_search: bool | None = None


class DecoderAdapter:
    """Worker-owned upstream baseline; decode takes only a binary syndrome (m,).

    The prepared DetectorProblem is immutable. Each returned array is owned by the
    caller. Invalid input raises ValueError; backend errors propagate. One adapter
    must not be used concurrently on multiple threads.
    """

    def __init__(self, problem: DetectorProblem, config: Decoder, *,
                 diagnostics: bool = False, profiling: bool = False) -> None:
        require_available_decoder(config.profile)
        if diagnostics:
            raise ValueError("active baselines do not export per-shot diagnostics")
        self.problem = problem
        self.config = config
        self.diagnostics = diagnostics
        self.profiling = profiling
        self.implementation = implementation_identity(config.profile)
        self.identity = decoder_identity(config, self.implementation)
        self._weights = [math.log1p(-float(p)) - math.log(float(p)) for p in problem.probabilities]
        self._native = None
        if problem.H.shape[1] == 0:
            return
        options = config.model_dump(exclude={"profile", "name", "enabled"})
        if isinstance(config, Bposd):
            from ldpc import BpOsdDecoder
            self._native = BpOsdDecoder(problem.H.copy(),
                                       error_channel=problem.probabilities.tolist(), **options)
        elif isinstance(config, Beam):
            from beam_search_decoder import BeamSearchDecoder
            self._native = BeamSearchDecoder(problem.H.copy(),
                                             error_channel=problem.probabilities.tolist(), **options)
        else:
            raise TypeError(f"unsupported decoder configuration: {type(config).__name__}")

    def decode(self, syndrome: np.ndarray) -> DecodeResult:
        """Return a complete service result with independent original-H validation."""
        s = np.asarray(syndrome)
        if s.shape != (self.problem.H.shape[0],) or not np.isin(s, [0, 1]).all():
            raise ValueError("syndrome must be binary with shape (m,)")
        s = s.astype(np.uint8, copy=True)
        counters = {}
        osd_called = False
        if self._native is None:
            candidate = np.zeros(0, dtype=np.uint8)
            declared = bool(s.any())
            native_status = "EMPTY_MODEL_CONTRADICTION" if declared else "EMPTY_MODEL_VALID"
            counters["total_iterations"] = 0
        else:
            candidate = np.asarray(self._native.decode(s.copy()))
            converged = bool(self._native.converge)
            if isinstance(self.config, Bposd):
                declared = False  # Upstream OSD may succeed after BP nonconvergence.
                osd_called = bool(s.any()) and not converged
                native_status = "BP_CONVERGED" if converged else "OSD_AFTER_BP_NONCONVERGENCE"
                counters["initial_iterations"] = int(self._native.iter) if s.any() else 0
                counters["total_iterations"] = counters["initial_iterations"]
            else:
                declared = not converged
                native_status = "CONVERGED" if converged else "SEARCH_EXHAUSTED"
                counters["total_iterations"] = int(self._native.total_iterations)
        valid = (candidate is not None and candidate.shape == (self.problem.H.shape[1],)
                 and bool(np.isin(candidate, [0, 1]).all())
                 and bool(np.array_equal((self.problem.H @ candidate) % 2, s)))
        status = "DECLARED_FAILURE" if declared else ("SUCCESS" if valid else "INVALID_OUTPUT")
        correction = prediction = cost = None
        if status == "SUCCESS":
            correction = candidate.astype(np.uint8, copy=True)
            prediction = np.asarray((self.problem.A @ correction) % 2, dtype=np.uint8)
            cost = sum(w for i, w in enumerate(self._weights) if correction[i])
        return DecodeResult(correction, prediction, valid, status, native_status, cost,
                            counters, osd_called=osd_called)
