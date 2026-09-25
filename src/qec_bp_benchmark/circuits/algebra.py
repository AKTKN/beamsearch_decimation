"""Independent binary linear algebra validation of pinned BB providers."""
from __future__ import annotations
import numpy as np
from numpy.typing import NDArray


def gf2_rank(matrix: NDArray) -> int:
    """Return GF(2) rank of a binary (m,n) array; own a copy, never mutate input."""
    values = np.asarray(matrix)
    if values.ndim != 2 or not np.isin(values, [0, 1]).all():
        raise ValueError("expected a binary matrix")
    a = np.array(values, dtype=np.uint8, copy=True)
    rank = 0
    for col in range(a.shape[1]):
        pivots = np.flatnonzero(a[rank:, col])
        if not len(pivots):
            continue
        pivot = rank + int(pivots[0])
        a[[rank, pivot]] = a[[pivot, rank]]
        for row in range(rank + 1, len(a)):
            if a[row, col]:
                a[row] ^= a[rank]
        rank += 1
    return rank


def validate_bb(code, order_x: int, order_y: int) -> dict[str, NDArray]:
    """Check a supported BB provider against independent GF(2) expectations.

    Args:
        code: Pinned qLDPC BBCode object; no mutation by this function except the
            provider's own lazy logical-basis cache.
        order_x: Cyclic order of x.
        order_y: Cyclic order of y.
    Returns:
        Owned uint8 Hx, Hz, Lx, Lz arrays with 12 logical rows.
    Raises:
        ValueError: Wrong construction, rank, commutation or logical pairing.
    """
    from qldpc.objects import Pauli
    if type(order_x) is not int or type(order_y) is not int or order_x < 1 or order_y < 1:
        raise ValueError("BB cyclic orders must be positive integers")
    eye_x = np.eye(order_x, dtype=np.uint8)
    eye_y = np.eye(order_y, dtype=np.uint8)
    x = np.kron(np.roll(eye_x, 1, axis=1), eye_y)
    y = np.kron(eye_x, np.roll(eye_y, 1, axis=1))
    a = (np.linalg.matrix_power(x, 3) + y + y @ y) % 2
    b = (np.linalg.matrix_power(y, 3) + x + x @ x) % 2
    hx, hz = np.asarray(code.matrix_x, dtype=np.uint8), np.asarray(code.matrix_z, dtype=np.uint8)
    lx = np.asarray(code.get_logical_ops(Pauli.X), dtype=np.uint8)
    lz = np.asarray(code.get_logical_ops(Pauli.Z), dtype=np.uint8)
    n = 2 * order_x * order_y
    rank = (n - 12) // 2
    checks = [len(code) == n, code.dimension == 12,
              np.array_equal(hx, np.hstack((a, b))), np.array_equal(hz, np.hstack((b.T, a.T))),
              gf2_rank(hx) == rank, gf2_rank(hz) == rank, not np.any(hx @ hz.T % 2),
              lx.shape == (12, n), lz.shape == (12, n),
              not np.any(hx @ lz.T % 2), not np.any(hz @ lx.T % 2),
              np.array_equal(lx @ lz.T % 2, np.eye(12, dtype=np.uint8)),
              gf2_rank(np.vstack((hx, lx))) == rank + 12,
              gf2_rank(np.vstack((hz, lz))) == rank + 12]
    if not all(checks):
        raise ValueError(f"BB{n} construction or independent logical-basis validation failed")
    return {key: value.copy() for key, value in zip(("Hx", "Hz", "Lx", "Lz"), (hx, hz, lx, lz))}


def validate_bb72(code) -> dict[str, NDArray]:
    """Preserve the named BB72 validation entry point."""
    return validate_bb(code, 6, 6)


def validate_bb144(code) -> dict[str, NDArray]:
    """Validate the qLDPC ``[[144,12,12]]`` construction."""
    return validate_bb(code, 12, 6)
