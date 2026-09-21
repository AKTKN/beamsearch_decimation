"""Canonical undecomposed DEM conversion with instruction-level Bernoulli semantics."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import numpy as np
from numpy.typing import NDArray
from scipy.sparse import csc_matrix
import stim
from qec_bp_benchmark.identity import content_hash


def sparse_hash(matrix: csc_matrix) -> str:
    """Hash canonical CSC shape/structure/bits with explicit little-endian encodings."""
    digest = hashlib.sha256()
    for array, dtype in ((matrix.shape, "<i8"), (matrix.indptr, "<i8"),
                         (matrix.indices, "<i8"), (matrix.data, "u1")):
        digest.update(np.asarray(array, dtype=dtype).tobytes())
    return digest.hexdigest()


@dataclass(frozen=True)
class DetectorProblem:
    """Canonical immutable-by-contract arrays; methods do not mutate inputs.

    H: (selected_detectors, mechanisms) CSC binary matrix.
    A: (observables, mechanisms) CSC binary matrix.
    probabilities: (mechanisms,) binary64 Bernoulli priors in (0,0.5].
    instruction_to_column: one entry per flattened DEM instruction; None for
        annotations and removed zero mechanisms. original_error_to_column only
        counts errors and supports reconstruction with removed bits zero.
    """
    H: csc_matrix
    A: csc_matrix
    probabilities: NDArray[np.float64]
    instruction_to_column: tuple[int | None, ...]
    original_error_to_column: tuple[int | None, ...]
    column_to_instruction: tuple[int, ...]
    hashes: dict[str, str]
    extraction_options: dict

    def reconstruct(self, correction: NDArray) -> NDArray[np.uint8]:
        """Restore exactly removed zero mechanisms; input (n,), output (original errors,)."""
        correction = np.asarray(correction)
        if correction.shape != (self.H.shape[1],) or not np.isin(correction, [0, 1]).all():
            raise ValueError("correction must be a binary canonical mechanism vector")
        return np.array([0 if c is None else correction[c] for c in self.original_error_to_column], dtype=np.uint8)


def convert_dem(dem: stim.DetectorErrorModel, *, selected_detectors: tuple[int, ...] | None = None,
                extraction_options: dict | None = None) -> DetectorProblem:
    """Convert undecomposed instructions without separating correlated components.

    Args:
        dem: Stim DEM; flattening expands all repeats and detector offsets.
        selected_detectors: Unique full detector IDs in desired row order, or all.
        extraction_options: Exact extraction configuration retained in identity.
    Returns:
        Owned CSC H/A, priors, normalization maps and content hashes. Each nonzero
        error instruction remains one column, even with zero selected support.
    Raises:
        ValueError: Invalid selection, nonfinite/unsupported probabilities or targets.
        Zero mechanisms are removed exactly; deterministic/complemented priors are
        unsupported and rejected, so no hidden syndrome/observable offset exists.
    """
    selected = tuple(range(dem.num_detectors)) if selected_detectors is None else selected_detectors
    if len(set(selected)) != len(selected) or any(type(d) is not int or d < 0 or d >= dem.num_detectors for d in selected):
        raise ValueError("selected detector IDs must be unique and in range")
    rows = {d: i for i, d in enumerate(selected)}
    h_indices, h_ptr = [], [0]
    a_indices, a_ptr = [], [0]
    probabilities, instruction_map, error_map, inverse = [], [], [], []
    for instruction_id, instruction in enumerate(dem.flattened()):
        if instruction.type != "error":
            instruction_map.append(None)
            continue
        p, = instruction.args_copy()
        if not np.isfinite(p) or not 0 <= p <= .5:
            raise ValueError("DEM probabilities must lie in [0,0.5]; complement/deterministic offsets unsupported")
        if p == 0:
            instruction_map.append(None)
            error_map.append(None)
            continue
        ds, ls = set(), set()
        for target in instruction.targets_copy():
            if target.is_relative_detector_id():
                ds.symmetric_difference_update((target.val,))
            elif target.is_logical_observable_id():
                ls.symmetric_difference_update((target.val,))
            elif not target.is_separator():
                raise ValueError("unsupported DEM target")
        column = len(probabilities)
        instruction_map.append(column)
        error_map.append(column)
        inverse.append(instruction_id)
        probabilities.append(p)
        h_indices.extend(sorted(rows[d] for d in ds if d in rows))
        a_indices.extend(sorted(ls))
        h_ptr.append(len(h_indices))
        a_ptr.append(len(a_indices))
    n = len(probabilities)
    h = csc_matrix((np.ones(len(h_indices), dtype=np.uint8), np.asarray(h_indices, dtype=np.int64),
                    np.asarray(h_ptr, dtype=np.int64)), shape=(len(selected), n))
    a = csc_matrix((np.ones(len(a_indices), dtype=np.uint8), np.asarray(a_indices, dtype=np.int64),
                    np.asarray(a_ptr, dtype=np.int64)), shape=(dem.num_observables, n))
    p_array = np.asarray(probabilities, dtype="<f8")
    options = dict(extraction_options or {})
    hashes = {"H": sparse_hash(h), "A": sparse_hash(a), "p": hashlib.sha256(p_array.tobytes()).hexdigest(),
              "dem": hashlib.sha256(str(dem).encode()).hexdigest(),
              "mappings": content_hash({"selected_detectors": selected, "instructions": instruction_map,
                                        "errors": error_map, "inverse": inverse}),
              "extraction_options": content_hash(options)}
    for matrix in (h, a):
        matrix.data.flags.writeable = False
        matrix.indices.flags.writeable = False
        matrix.indptr.flags.writeable = False
    p_array.flags.writeable = False
    return DetectorProblem(h, a, p_array, tuple(instruction_map), tuple(error_map), tuple(inverse), hashes, options)
