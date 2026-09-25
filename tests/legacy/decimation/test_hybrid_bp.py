"""Stage 2 numerical oracle, finite-hint, ownership and reset regressions."""
import itertools
import math
import numpy as np
import pytest
from qec_bp_benchmark.bp import verified_hybrid_backend
from min_sum_oracle import Oracle


def compare(session, oracle):
    got = session.snapshot()
    for field in ('fields', 'sums', 'llrs'):
        assert getattr(got, field) == pytest.approx(getattr(oracle, field), abs=1e-13)
    for field in ('q', 'z'):
        assert getattr(got, field) == pytest.approx([getattr(oracle, field)[e] for e in oracle.edges], abs=1e-13)
    assert got.decision == oracle.decision
    assert got.iterations == oracle.iterations


def test_literal_min_sum_oracle():
    backend = verified_hybrid_backend()
    rng = np.random.default_rng(431)
    fixtures = [([], 0), ([[]], 0), ([[0]], 1), ([[0], [0]], 1),
                ([[0, 1], [1, 2]], 3), ([[0, 1], [1, 2], [0, 2]], 3),
                ([[0, 1, 2], [0, 1], [1, 2]], 3)]
    for rows, n in fixtures:
        for syndrome in itertools.product((0, 1), repeat=len(rows)):
            session = backend.StatefulMinSumSession(rows, n, [.1]*n, 3., .75)
            session.reset(syndrome)
            oracle = Oracle(rows, n, syndrome, 3., .75)
            for fields in ([0.]*n, [2.]*n, rng.choice([-50., -2., 0., 2., 50.], n).tolist()):
                assert session.replace_fields(fields) == oracle.replace(fields)
                compare(session, oracle)
                for _ in range(4):
                    expected = oracle.step()
                    out = session.advance(1)
                    assert out.valid == expected
                    compare(session, oracle)


def test_clipping_extrinsic_and_continuation():
    cls = verified_hybrid_backend().StatefulMinSumSession
    a, b = [cls([[0], [0]], 1, [.1], 25., 1.) for _ in range(2)]
    for session in (a, b):
        session.reset([0, 1]); session.replace_fields([50.])
    assert not a.advance(1).valid
    s = a.snapshot()
    assert s.sums == [50.] and s.llrs == [25.] and s.q == [25., 25.]
    assert s.q[0] != max(-25., min(25., s.llrs[0]-s.z[0]))
    a.advance(3); b.advance(4)
    assert a.snapshot().q == b.snapshot().q and a.snapshot().z == b.snapshot().z
    assert a.snapshot().iterations == b.snapshot().iterations == 4


def test_replaced_removed_hints_finite_disagreement_and_reset():
    cls = verified_hybrid_backend().StatefulMinSumSession
    session = cls([[0], [0]], 1, [.1])
    session.reset([1, 1])
    assert not session.replace_hint([(0, 0)], 8.)
    assert session.advance(1).valid
    assert session.snapshot().decision == [1]  # A valid correction violates the zero hint.
    old_z = session.snapshot().z
    session.replace_hint([], 8.)
    assert session.snapshot().z == old_z
    assert session.snapshot().fields == pytest.approx([math.log(9)])
    session.replace_hint([(0, 1)], 3.)
    assert session.snapshot().fields == pytest.approx([-math.log(9)-3])
    session.reset([0, 0]); session.replace_hint([], 8.)
    assert session.snapshot().z == [0, 0] and session.snapshot().iterations == 0
    with pytest.raises(ValueError): session.replace_fields([float('nan')])
    with pytest.raises(RuntimeError): session.advance(1)
    session.reset([1, 1]); session.replace_hint([], 8.)
    assert session.advance(1).valid
    with pytest.raises(ValueError): session.reset([2, 1])
    with pytest.raises(RuntimeError): session.snapshot()


def test_native_input_validation_and_osd_degenerate():
    backend = verified_hybrid_backend()
    for rows, n, p in [([[0, 0]], 1, [.1]), ([[1, 0]], 2, [.1, .2]), ([[1]], 1, [.1]),
                       ([[0]], 1, [0]), ([[0]], 1, [.6]), ([[0]], 1, [float('nan')])]:
        with pytest.raises(ValueError): backend.StatefulMinSumSession(rows, n, p)
    for rows, n, p, s in [([], 0, [], []), ([[]], 0, [], [0]), ([], 2, [.1, .2], [])]:
        osd = backend.Osd0Bridge(rows, n, p)
        assert osd.decode(s, [0.]*n).valid and osd.candidate_count == 0
    osd = backend.Osd0Bridge([[0], [0]], 1, [.1])
    assert not osd.decode([0, 1], [-3.]).valid
    assert osd.decode([1, 1], [-3.]).correction == [1]
    with pytest.raises(ValueError): osd.decode([1, 1], [float('inf')])
    assert osd.decode([0, 0], [3.]).valid
