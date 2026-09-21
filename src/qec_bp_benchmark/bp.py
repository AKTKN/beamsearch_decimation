"""Typed one-call interface to the audited opt-in ldpc flooding kernel."""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import numpy as np
from numpy.typing import NDArray
from scipy import sparse


@lru_cache(maxsize=1)
def verified_backend():
    """Load intended fork only; reject mismatched source/build identity with RuntimeError.

    Verification reads the repository manifest and computes the same source hash
    embedded at compilation. Cached once per process; rebuild/restart after edits.
    """
    import ldpc
    from ldpc import reference_bp
    from ldpc.reference_bp import _reference_bp
    root = Path(__file__).resolve().parents[2]
    fork = root / "external_lib/ldpc"
    for module in (ldpc, reference_bp, _reference_bp):
        if fork.resolve() not in Path(module.__file__).resolve().parents:
            raise RuntimeError("unrelated ldpc installation loaded; install the pinned local fork")
    expected = json.loads((root / "external_lib/manifest.lock.json").read_text())["dependencies"]["ldpc"]["commit"]
    identity = reference_bp.build_identity()
    digest = hashlib.sha256()
    for name in ('src_cpp/reference_bp.hpp', 'src_python/ldpc/reference_bp/bindings.cpp',
                 'src_python/ldpc/reference_bp/__init__.py', 'setup_reference.py'):
        digest.update(name.encode() + b'\0' + (fork / name).read_bytes())
    if identity["upstream_commit"] != expected or identity["source_sha256"] != digest.hexdigest():
        raise RuntimeError("ldpc reference BP build/source identity mismatch; rebuild the fork extension")
    return reference_bp


@dataclass(frozen=True)
class BPResult:
    """Owned result arrays. Beliefs/history columns correspond to free_ids.

    correction is length-n uint8 or None on failure. last_decision is diagnostic,
    never implicitly treated as valid. History is (retained iterations, free n),
    excluding iteration zero. Native optional trace also includes initialization.
    """
    status: str
    iterations: int
    correction: NDArray[np.uint8] | None
    last_decision: NDArray[np.uint8]
    free_ids: NDArray[np.int64]
    beliefs: NDArray[np.float64]
    history: NDArray[np.float64]
    mean_llr: NDArray[np.float64]
    reliability: NDArray[np.float64]
    flips: NDArray[np.int64]
    trace: tuple


class FloodingBP:
    """Immutable owned graph/prior decoder; each decode independently cold-starts."""

    def __init__(self, H, probabilities: NDArray) -> None:
        """Copy canonical binary H (m,n) and finite priors (n,) in (0,0.5].

        Sparse inputs must have no duplicate entries; explicit zeros are removed.
        Raises ValueError for shape/content errors, RuntimeError for a wrong build.
        Caller buffers can be changed after construction; no borrowed memory remains.
        """
        if sparse.issparse(H):
            if not H.has_canonical_format or not np.isin(H.data, [0,1]).all():
                raise ValueError("H must have canonical binary sparse entries")
            matrix = H.tocsr(copy=True)
            matrix.eliminate_zeros()
        else:
            values = np.asarray(H)
            if values.ndim != 2 or not np.isin(values,[0,1]).all():
                raise ValueError("H must be a binary matrix")
            matrix = sparse.csr_matrix(values, dtype=np.uint8)
        matrix.sort_indices()
        p = np.asarray(probabilities, dtype=np.float64)
        if p.shape != (matrix.shape[1],):
            raise ValueError("probabilities must have shape (n,)")
        rows = [matrix.indices[matrix.indptr[a]:matrix.indptr[a+1]].tolist() for a in range(matrix.shape[0])]
        self._backend = verified_backend()
        self._native = self._backend.ReferenceBp(rows, matrix.shape[1], p.tolist())
        self.shape = matrix.shape

    def decode(self, syndrome: NDArray, *, max_iterations: int = 30, llr_max: float = 25,
               history_window: int = 8, fixed: NDArray | None = None,
               diagnostics: bool = False) -> BPResult:
        """Decode one binary syndrome (m,); optional fixed mask (n,) uses -1/0/1.

        Native execution owns all per-call buffers and releases the GIL; concurrent
        calls do not share mutable BP state. Python has no per-iteration callbacks.
        Return BPResult with status and copied arrays; ValueError on invalid inputs.
        max_iterations >=1; history_window >=0; 0<llr_max<=30. Fixed bits have no LLR.
        """
        s = np.asarray(syndrome)
        if s.shape != (self.shape[0],) or not np.isin(s,[0,1]).all():
            raise ValueError("syndrome must be a binary vector with shape (m,)")
        if type(max_iterations) is not int or type(history_window) is not int or type(diagnostics) is not bool:
            raise ValueError("iteration/history budgets must be integers; diagnostics must be boolean")
        mask = []
        if fixed is not None:
            fixed = np.asarray(fixed)
            if fixed.shape != (self.shape[1],) or not np.isin(fixed,[-1,0,1]).all():
                raise ValueError("fixed mask must have shape (n,) and values -1,0,1")
            mask = fixed.astype(int).tolist()
        r = self._native.decode(s.astype(int).tolist(), max_iterations, llr_max, history_window, mask, diagnostics)
        decision = np.asarray(r.last_decision,dtype=np.uint8)
        free = np.asarray(r.free_ids,dtype=np.int64)
        return BPResult(r.status.name, r.iterations,
                        decision.copy() if r.status == self._backend.Status.CONVERGED else None,
                        decision, free, np.asarray(r.beliefs),
                        np.asarray(r.history,dtype=float).reshape((len(r.history),len(free))),
                        np.asarray(r.mean_llr),np.asarray(r.reliability),np.asarray(r.flips,dtype=np.int64),
                        tuple(r.trace))
