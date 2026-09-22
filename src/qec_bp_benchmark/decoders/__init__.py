"""Complete per-shot decoder services. Truth is deliberately absent from this API."""
from __future__ import annotations
from dataclasses import dataclass, field
from functools import lru_cache
import hashlib
import importlib
import json
import math
from pathlib import Path
from types import ModuleType
import time
import numpy as np
from ..bp import verified_backend, verified_hybrid_backend
from ..config import (Decoder, Screened, Bposd, Beam, Hybrid, SearchBP,
                      HYBRID_PROFILES, require_available_decoder)
from ..dem.model import DetectorProblem
from ..identity import decoder_identity

ROOT = Path(__file__).resolve().parents[3]


@lru_cache(maxsize=1)
def native_search() -> ModuleType:
    """Reject stale project/fork binaries before preparing a screened decoder."""
    verified_backend()
    from .. import _native
    paths = {'search_sha256': 'src/qec_bp_benchmark/native/search.hpp',
             'binding_sha256': 'src/qec_bp_benchmark/native/module.cpp',
             'cmake_sha256': 'CMakeLists.txt',
             'bp_header_sha256': 'external_lib/ldpc/src_cpp/reference_bp.hpp'}
    if _native.source_identity() != {k: hashlib.sha256((ROOT/v).read_bytes()).hexdigest() for k,v in paths.items()}:
        raise RuntimeError('project native source/build mismatch; rebuild the editable package')
    return _native


@lru_cache(maxsize=1)
def native_hybrid() -> ModuleType:
    """Verify project and transitive fork source/build identities before session setup."""
    from ..native_sources import hybrid_project_digest
    backend = verified_hybrid_backend()
    module = native_search()
    expected = {'project_sha256': hybrid_project_digest(ROOT),
                'fork_sha256': backend.build_identity()['source_sha256']}
    if module.hybrid_source_identity() != expected:
        raise RuntimeError('hybrid project source/build mismatch; rebuild the editable package')
    return module


@lru_cache(maxsize=8)
def implementation_identity(kind: str) -> dict:
    """Actual native bytes and pinned upstream identity, shared by rows/provenance."""
    require_available_decoder(kind)
    manifest=json.loads((ROOT/'external_lib/manifest.lock.json').read_text())
    if kind == 'screened_reference':
        module=native_search()
        detail=dict(module.source_identity(), build=module.build_identity())
    elif kind in HYBRID_PROFILES or kind == 'search_bp':
        import platform
        module=native_hybrid()
        detail=dict(module.hybrid_source_identity(), build=module.build_identity(),
                    fork_build=verified_hybrid_backend().build_identity(), libc=platform.libc_ver())
    elif kind in ('bposd_ms30_cs10', 'bposd_ms30_cs0', 'beam8', 'beam32'):
        if kind in ('bposd_ms30_cs10', 'bposd_ms30_cs0'):
            module=importlib.import_module('ldpc.bposd_decoder._bposd_decoder')
            key='ldpc'
        elif kind in ('beam8', 'beam32'):
            module=importlib.import_module('beam_search_decoder._beam_search_decoder')
            key='BeamSearchDecoder'
        expected=ROOT/'external_lib'/key
        if expected.resolve() not in Path(module.__file__).resolve().parents:
            raise RuntimeError(f'unintended native baseline import: {module.__file__}')
        detail={'upstream_commit': manifest['dependencies'][key]['commit']}
    else:
        raise ValueError(f'unsupported implementation identity: {kind}')
    # Path is provenance, not scientific decoder identity: relocation preserves ID.
    return dict(detail, native_sha256=hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),
                adapter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())


@dataclass(frozen=True)
class DecodeResult:
    """Owned canonical correction (n,) and logical prediction (k,), null on failure.

    syndrome_valid reports the candidate parity independently of native flags.
    status is SUCCESS, DECLARED_FAILURE or INVALID_OUTPUT. Costs are physical and
    finite; counters absent from an upstream API are None, never inferred totals.
    """
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
    # Exact invocation flag; None is reserved for opaque future baseline APIs.
    osd_called: bool | None = None
    # Exact only for SEARCH-BP-2.1; false for non-search exits, null for baselines.
    correction_by_search: bool | None = None


class DecoderAdapter:
    """Worker-owned prepared decoder; decode resets native state between shots.

    Inputs are immutable-by-contract DetectorProblem and a binary syndrome (m,).
    No sampler/truth arguments. This service includes input copying, native decode,
    full H validation and A prediction. Do not call a baseline concurrently on one
    object. Screened native calls themselves are const and reentrant.
    """
    def __init__(self, problem: DetectorProblem, config: Decoder, *, diagnostics: bool=False, profiling: bool=False) -> None:
        require_available_decoder(config.profile)
        if isinstance(config,Hybrid) and diagnostics:
            raise ValueError("hybrid per-node traces are unsupported; use profiling and export_telemetry after decode")
        if isinstance(config,SearchBP) and (diagnostics or profiling):
            raise ValueError("SEARCH-BP-2.1 exposes no diagnostic or phase telemetry")
        if not isinstance(config, (Screened, Bposd, Beam, Hybrid, SearchBP)):
            raise TypeError(f'unsupported decoder configuration: {type(config).__name__}')
        self.problem=problem
        self.config=config
        self.diagnostics=diagnostics
        self.profiling=profiling
        self.implementation=implementation_identity(config.profile)
        self.identity=decoder_identity(config,self.implementation)
        self._weights=[math.log1p(-float(p))-math.log(float(p)) for p in problem.probabilities]
        self._native=None
        n=problem.H.shape[1]
        if isinstance(config,SearchBP):
            native=native_hybrid()
            settings=native.SearchBP2Settings()
            for key,value in {
                'initial_iterations':config.bp.initial_iterations,
                'candidate_iterations':config.bp.candidate_iterations,
                'history_window':config.bp.history_window,
                'history_clip':config.bp.average_llr_clip,
                'scaling_factor':config.bp.scaling_factor,
                'selected_checks':config.search.selected_checks,
                'local_variables':config.search.local_variables,
                'local_variable_policy':config.search.local_variable_policy,
                'max_fixations':config.search.max_fixations,
                'max_cycles':config.search.max_cycles,
                'beta':config.search.beta,
                'guidance_strength':config.search.guidance_strength,
                'k_run':config.admission.k_run,'k_keep':config.admission.k_keep,
                'osd_fallback':config.osd_fallback,
            }.items():
                setattr(settings,key,value)
            def rows(matrix):
                csr=matrix.tocsr()
                return [csr.indices[csr.indptr[a]:csr.indptr[a+1]].tolist() for a in range(csr.shape[0])]
            self._native=native.SearchBP2Decoder(rows(problem.H),n,problem.probabilities.tolist(),rows(problem.A),settings)
            return
        # The exactly normalized empty model has a unique length-zero correction.
        # No native baseline accepts every empty shape, so handle it algebraically.
        if isinstance(config,Hybrid):
            native=native_hybrid(); settings=native.HybridSettings()
            for key,value in {'max_depth':config.search.max_depth,
                'expansions':list(config.search.expansions_per_cycle), 'iterations':list(config.bp.iterations_per_cycle),
                'max_generated_nodes':config.search.max_generated_nodes,
                'prefix_cpu_budget_ns':config.search.prefix_cpu_budget_ns or 0,
                'alpha':config.bp.scaling_factor,'clip':config.bp.llr_clip,'margin':config.bp.hint_margin_llr,
                'bp_enabled':config.bp.enabled,'warm':config.bp.warm_start}.items():
                setattr(settings,key,value)
            def rows(matrix):
                csr=matrix.tocsr()
                return [csr.indices[csr.indptr[a]:csr.indptr[a+1]].tolist() for a in range(csr.shape[0])]
            self._native=native.HybridDecoder(rows(problem.H),n,problem.probabilities.tolist(),rows(problem.A),settings)
            return
        if n==0: return
        if isinstance(config,Screened):
            native=native_search()
            settings=native.Settings()
            for key,value in {'T0':config.T0,'Tpost':config.Tpost,'window':config.history_window,
                              'M':config.M,'q':config.q,'K':config.K,'limit':config.Lmax}.items():
                setattr(settings,key,value)
            csr=problem.H.tocsr()
            rows=[csr.indices[csr.indptr[a]:csr.indptr[a+1]].tolist() for a in range(csr.shape[0])]
            self._native=native.ScreenedDecoder(rows,n,problem.probabilities.tolist(),settings)
        elif isinstance(config,Bposd):
            from ldpc import BpOsdDecoder
            self._native=BpOsdDecoder(problem.H.copy(),error_channel=problem.probabilities.tolist(),
                **config.model_dump(exclude={'profile','name','enabled'}))
        elif isinstance(config,Beam):
            from beam_search_decoder import BeamSearchDecoder
            self._native=BeamSearchDecoder(problem.H.copy(),error_channel=problem.probabilities.tolist(),
                **config.model_dump(exclude={'profile','name','enabled'}))

    def decode(self, syndrome: np.ndarray) -> DecodeResult:
        """Return a complete result; unexpected backend errors propagate to the runner."""
        phase_start=time.perf_counter_ns() if self.profiling else 0
        s=np.asarray(syndrome)
        if s.shape!=(self.problem.H.shape[0],) or not np.isin(s,[0,1]).all():
            raise ValueError('syndrome must be binary with shape (m,)')
        s=s.astype(np.uint8,copy=True)
        counters={}
        diagnostics=None
        hybrid_summary=None
        osd_called=False
        correction_by_search=None
        phases={} if self.profiling else None
        if self.profiling:
            now=time.perf_counter_ns(); phases['input_wall_ns']=now-phase_start; phase_start=now
        if self._native is None:
            candidate=np.zeros(0,dtype=np.uint8)
            declared=bool(s.any())
            native_status='EMPTY_MODEL_CONTRADICTION' if declared else 'EMPTY_MODEL_VALID'
        elif isinstance(self.config,SearchBP):
            r=self._native.decode(s.tolist())
            candidate=np.asarray(r.correction) if r.valid else None
            declared=not r.valid
            native_status='VALID' if r.valid else 'DECLARED_FAILURE'
            if type(r.osd_called) is not bool:
                raise ValueError('SEARCH-BP-2.1 must expose an exact boolean osd_called')
            osd_called=r.osd_called
            if type(r.correction_by_search) is not bool:
                raise ValueError('SEARCH-BP-2.1 must expose an exact boolean correction_by_search')
            correction_by_search=r.correction_by_search
        elif isinstance(self.config,Hybrid):
            r=self._native.decode(s.tolist(),self.profiling)
            candidate=np.asarray(r.correction,dtype=np.uint8) if r.valid else None
            declared=not r.valid
            hybrid_summary=r.summary
            native_status=hybrid_summary['exit_reason']
            osd_called=bool(hybrid_summary['osd_entered'])
        elif isinstance(self.config,Screened):
            r=self._native.decode(s.tolist(),self.diagnostics,self.profiling)
            candidate=np.asarray(r.correction,dtype=np.uint8) if r.valid else None
            declared=not r.valid
            native_status=r.status
            counters=dict(initial_success=r.initial_success, initial_iterations=r.initial_iterations,
                post_iterations=r.post_iterations, candidates=r.screening.enumerated,
                rejected=r.screening.rejected, retained=len(r.screening.retained),
                bp_completions=r.completions, successful_completions=r.successes,
                selected_pattern=r.selected_pattern or None)
            if self.diagnostics:
                diagnostics=r.diagnostics()
            if self.profiling: phases.update(r.phases)
        elif isinstance(self.config,(Bposd,Beam)):
            candidate=np.asarray(self._native.decode(s.copy()))
            converged=bool(self._native.converge)
            if isinstance(self.config,Bposd):
                declared=False # converge only describes the BP stage, not OSD.
                osd_called=bool(s.any()) and not converged
                native_status='BP_CONVERGED' if converged else 'OSD_AFTER_BP_NONCONVERGENCE'
                counters['initial_iterations']=int(self._native.iter) if s.any() else 0
            elif isinstance(self.config,Beam):
                declared=not converged
                native_status='CONVERGED' if converged else 'SEARCH_EXHAUSTED'
                # Upstream iter counts only the last BP call; no total is exposed.
        else:
            raise TypeError(f'unsupported decoder configuration: {type(self.config).__name__}')
        if self.profiling:
            now=time.perf_counter_ns(); phases['backend_wall_ns']=now-phase_start; phase_start=now
        valid=(candidate is not None and candidate.shape==(self.problem.H.shape[1],)
               and bool(np.isin(candidate,[0,1]).all())
               and bool(np.array_equal((self.problem.H@candidate)%2,s)))
        status='DECLARED_FAILURE' if declared else ('SUCCESS' if valid else 'INVALID_OUTPUT')
        correction=prediction=cost=None
        if status=='SUCCESS':
            correction=candidate.astype(np.uint8,copy=True)
            prediction=np.asarray((self.problem.A@correction)%2,dtype=np.uint8)
            cost=sum(w for i,w in enumerate(self._weights) if correction[i])
        if self.profiling: phases['validation_prediction_cost_wall_ns']=time.perf_counter_ns()-phase_start
        return DecodeResult(correction,prediction,valid,status,native_status,cost,counters,diagnostics,phases,
                            hybrid_summary,osd_called,correction_by_search)


    def export_telemetry(self) -> dict:
        """Copy native hybrid events after timed decode and before the next shot.

        Returned dictionaries/lists own their contents. No truth labels are present.
        profiling=none yields empty event lists. Non-hybrid calls raise TypeError.
        Session use, including export, is non-reentrant.
        """
        if not isinstance(self.config,Hybrid):
            raise TypeError('native event export requires a hybrid decoder')
        return self._native.export_telemetry()
