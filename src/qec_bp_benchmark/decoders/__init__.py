"""Active, truth-free comparison decoder services.

Historical
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

from ..config import AFBP, Bposd, Beam, RelayBP, Decoder, require_available_decoder
from ..dem.model import DetectorProblem
from ..identity import decoder_identity

ROOT = Path(__file__).resolve().parents[3]


@lru_cache(maxsize=4)
def implementation_identity(profile: str) -> dict:
    """Return pinned upstream and actual imported binary identity."""
    require_available_decoder(profile)
    if profile == "af_bp":
        from .. import _af_bp_service
        from ..af_bp_service import source_digest
        built = _af_bp_service.build_identity()
        if built["source_sha256"] != source_digest():
            raise RuntimeError("stale AF-BP service binary; rebuild the project extension")
        return {
            "algorithm_version": built["algorithm_version"],
            "source_sha256": built["source_sha256"],
            "native_sha256": hashlib.sha256(Path(_af_bp_service.__file__).read_bytes()).hexdigest(),
            "adapter_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        }
    key, module_name = {
        "bposd": ("ldpc", "ldpc.bposd_decoder._bposd_decoder"),
        "beam8": ("BeamSearchDecoder", "beam_search_decoder._beam_search_decoder"),
        "relay_bp": ("relay", "relay_bp._relay_bp"),
    }[profile]
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
    """Truth-free result with owned (n,) correction and (k,) prediction on success."""
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

    @property
    def total_iterations(self) -> int:
        """Actual BP iterations over the complete decoder service."""
        return self.counters["total_iterations"]

    @property
    def declared_failure(self) -> bool:
        return self.status == "DECLARED_FAILURE"


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
        options = config.model_dump(exclude={"profile", "kind", "name", "enabled"})
        if isinstance(config, Bposd):
            from ldpc import BpOsdDecoder
            self._native = BpOsdDecoder(problem.H.copy(),
                                       error_channel=problem.probabilities.tolist(), **options)
        elif isinstance(config, Beam):
            from beam_search_decoder import BeamSearchDecoder
            self._native = BeamSearchDecoder(problem.H.copy(),
                                             error_channel=problem.probabilities.tolist(), **options)
        elif isinstance(config, RelayBP):
            from relay_bp import RelayDecoderF64
            self._native = RelayDecoderF64(
                problem.H.copy(), np.asarray(problem.probabilities, dtype=np.float64).copy(),
                **options, stopping_criterion="nconv", logging=False)
        elif isinstance(config, AFBP):
            from ..af_bp_service import AFBPConfig, AFBPDecoder, FailureOptions
            failure = FailureOptions(
                residual_radius=config.residual_radius,
                distance_decay=config.distance_decay,
                uncertainty_weight=config.uncertainty_weight,
                oscillation_weight=config.oscillation_weight,
                selection=config.U_selection,
                top_k=config.U_top_k,
                threshold=config.U_threshold,
            )
            self._native = AFBPDecoder(problem.H, problem.A, problem.probabilities,
                AFBPConfig(initial_parallel=config.initial_parallel,
                    initial_iteration_budget=config.initial_iteration_budget,
                    transformed_iteration_budget=config.transformed_iteration_budget,
                    bp_variant=config.bp_variant, serial_order=config.serial_order,
                    scaling_factor=config.ms_scaling_factor,
                    history_window=config.history_window, graph_rounds=config.graph_rounds,
                    n_fact=config.n_fact, factorization_policy=config.factorization_policy,
                    failure=failure, atanh_epsilon=config.atanh_epsilon,
                    phase1_iterations=config.qdither_phase1_iterations,
                    num_chains=config.qdither_chains,
                    chain_iterations=config.qdither_iterations_per_chain,
                    alpha=config.qdither_alpha, beta=config.qdither_beta,
                    rho=config.qdither_rho, seed=config.seed,
                    seed_policy=config.seed_policy,
                    qdither_handoff=config.qdither_handoff))
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
        elif isinstance(self.config, RelayBP):
            detailed = self._native.decode_detailed(s.copy())
            candidate = np.asarray(detailed.decoding)
            declared = not bool(detailed.success)
            native_status = "CONVERGED" if detailed.success else "RELAY_EXHAUSTED"
            counters["total_iterations"] = int(detailed.iterations)
        elif isinstance(self.config, AFBP):
            detailed = self._native.decode(s.copy())
            candidate = detailed.correction
            declared = not detailed.valid
            native_status = detailed.status
            counters["total_iterations"] = detailed.total_iterations
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
