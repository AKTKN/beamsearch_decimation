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
from ..bp import verified_backend
from ..config import Decoder, Screened, Bposd
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


@lru_cache(maxsize=3)
def implementation_identity(kind: str) -> dict:
    """Actual native bytes and pinned upstream identity, shared by rows/provenance."""
    manifest=json.loads((ROOT/'external_lib/manifest.lock.json').read_text())
    if kind == 'screened_reference':
        module=native_search()
        detail=dict(module.source_identity(), build=module.build_identity())
    else:
        module=importlib.import_module('ldpc.bposd_decoder._bposd_decoder' if kind=='bposd_ms30_cs10'
                                       else 'beam_search_decoder._beam_search_decoder')
        key='ldpc' if kind=='bposd_ms30_cs10' else 'BeamSearchDecoder'
        expected=ROOT/'external_lib'/key
        if expected.resolve() not in Path(module.__file__).resolve().parents:
            raise RuntimeError(f'unintended native baseline import: {module.__file__}')
        detail={'upstream_commit': manifest['dependencies'][key]['commit']}
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


class DecoderAdapter:
    """Worker-owned prepared decoder; decode resets/cold-starts native shot state.

    Inputs are immutable-by-contract DetectorProblem and a binary syndrome (m,).
    No sampler/truth arguments. This service includes input copying, native decode,
    full H validation and A prediction. Do not call a baseline concurrently on one
    object. Screened native calls themselves are const and reentrant.
    """
    def __init__(self, problem: DetectorProblem, config: Decoder, *, diagnostics: bool=False, profiling: bool=False) -> None:
        self.problem=problem
        self.config=config
        self.diagnostics=diagnostics
        self.profiling=profiling
        self.implementation=implementation_identity(config.profile)
        self.identity=decoder_identity(config,self.implementation)
        self._weights=[math.log1p(-float(p))-math.log(float(p)) for p in problem.probabilities]
        self._native=None
        n=problem.H.shape[1]
        # The exactly normalized empty model has a unique length-zero correction.
        # No native baseline accepts every empty shape, so handle it algebraically.
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
        else:
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
        phases={} if self.profiling else None
        if self.profiling:
            now=time.perf_counter_ns(); phases['input_wall_ns']=now-phase_start; phase_start=now
        if self._native is None:
            candidate=np.zeros(0,dtype=np.uint8)
            declared=bool(s.any())
            native_status='EMPTY_MODEL_CONTRADICTION' if declared else 'EMPTY_MODEL_VALID'
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
        else:
            candidate=np.asarray(self._native.decode(s.copy()))
            converged=bool(self._native.converge)
            if isinstance(self.config,Bposd):
                declared=False # converge only describes the BP stage, not OSD.
                native_status='BP_CONVERGED' if converged else 'OSD_AFTER_BP_NONCONVERGENCE'
                counters['initial_iterations']=int(self._native.iter) if s.any() else 0
            else:
                declared=not converged
                native_status='CONVERGED' if converged else 'SEARCH_EXHAUSTED'
                # Upstream iter counts only the last BP call; no total is exposed.
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
        return DecodeResult(correction,prediction,valid,status,native_status,cost,counters,diagnostics,phases)
