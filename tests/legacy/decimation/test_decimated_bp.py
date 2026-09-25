"""Fork BP API tests; independent scalar exclusion oracle, no search algorithm."""
import itertools
import math

import numpy as np
import pytest
from scipy.sparse import csr_matrix
from ldpc import BpDecoder
from qec_bp_benchmark.bp import verified_hybrid_backend


def session(rows, p, window=3, clip=2., alpha=.75):
    return verified_hybrid_backend().DecimatedMinSumSession(rows, len(p), p, window, clip, alpha)


class Scalar:
    """Literal excluded-edge products/minima and sums on the reduced graph."""
    def __init__(self, rows, p, syndrome, fixed=(), alpha=.75):
        self.rows, self.p, self.alpha = rows, p, alpha
        self.fixed = dict(fixed)
        self.residual = [s ^ (sum(self.fixed.get(j, 0) for j in row) % 2)
                         for row, s in zip(rows, syndrome)]
        self.edges = [(a, j) for a, row in enumerate(rows) for j in row if j not in self.fixed]
        self.weights = [math.log1p(-x) - math.log(x) for x in p]
        self.q = {e: self.weights[e[1]] for e in self.edges}
        self.z = {e: 0. for e in self.edges}
        self.llr = self.weights.copy()
        self.decision = [self.fixed.get(j, int(x <= 0)) for j, x in enumerate(self.llr)]
        self.history = []
        self.syndrome = syndrome

    def valid(self):
        return all(sum(self.decision[j] for j in row) % 2 == s
                   for row, s in zip(self.rows, self.syndrome))

    def step(self):
        if self.valid():
            return 0
        z = {}
        for a, j in self.edges:
            other = [self.q[a, k] for k in self.rows[a] if k != j and k not in self.fixed]
            sign = (-1) ** (self.residual[a] + sum(x <= 0 for x in other))
            z[a, j] = sign * self.alpha * min(map(abs, other), default=np.finfo(float).max)
        self.z = z
        for j in range(len(self.p)):
            if j in self.fixed:
                continue
            self.llr[j] = self.weights[j] + sum(z[e] for e in self.edges if e[1] == j)
            self.decision[j] = int(self.llr[j] <= 0)
        self.q = {e: self.weights[e[1]] + sum(z[f] for f in self.edges if f[1] == e[1] and f != e)
                  for e in self.edges}
        self.history.append(self.llr.copy())
        return 1


@pytest.mark.parametrize('alpha', [.5, .75, 1.])
def test_ordinary_bp_matches_pinned_parallel_min_sum(alpha):
    rows = [[0, 1, 3], [1, 2, 3], [0, 2]]
    p = [.1, .18, .23, .29]
    H = csr_matrix([[int(j in row) for j in range(4)] for row in rows], dtype=np.uint8)
    for syndrome in itertools.product((0, 1), repeat=3):
        for budget in (1, 2, 7):
            bp = session(rows, p, alpha=alpha)
            bp.reset_from_channel(syndrome)
            result = bp.continue_iterations(budget)
            upstream = BpDecoder(H, error_channel=p, max_iter=budget, bp_method='minimum_sum',
                                 schedule='parallel', ms_scaling_factor=alpha, input_vector_type='syndrome')
            expected = upstream.decode(np.array(syndrome, dtype=np.uint8))
            assert bp.decision == expected.tolist()
            assert result.valid == bool(upstream.converge or not any(syndrome))
            if any(syndrome):
                assert result.actual_iterations == upstream.iter
                assert bp.posterior_llr == pytest.approx(upstream.log_prob_ratios, rel=1e-12, abs=1e-12)
            else:
                assert result.actual_iterations == bp.history_count == 0


@pytest.mark.parametrize('window', [1, 2, 5])
def test_scalar_messages_and_rolling_clipped_mean(window):
    # Odd parity triangle is inconsistent globally but has no empty residual row.
    rows, p, syndrome = [[0, 1], [1, 2], [0, 2]], [.1, .19, .27], [1, 0, 0]
    bp = session(rows, p, window=window, clip=.8)
    bp.reset_from_channel(syndrome, shot_id=11)
    oracle = Scalar(rows, p, syndrome)
    assert bp.clipped_mean_llr == pytest.approx(np.clip(oracle.weights, -.8, .8), rel=1e-12, abs=1e-12)
    for iteration in range(19):
        expected = oracle.step()
        result = bp.continue_iterations(1)
        assert result.actual_iterations == expected == 1
        assert result.requested_iterations == 1 and result.total_iterations == iteration + 1
        assert result.status.name == 'BUDGET_EXHAUSTED'
        assert bp.posterior_llr == pytest.approx(oracle.llr, rel=1e-12, abs=1e-12)
        assert bp.snapshot().q == pytest.approx(list(oracle.q.values()), rel=1e-12, abs=1e-12)
        assert bp.check_to_variable == pytest.approx(list(oracle.z.values()), rel=1e-12, abs=1e-12)
        assert bp.snapshot().check_to_variable == pytest.approx(
            list(oracle.z.values()), rel=1e-12, abs=1e-12)
        for j in range(len(p)):
            used = oracle.weights[j] + sum(value for (a, k), value in oracle.z.items() if k == j)
            assert bp.posterior_llr[j] == pytest.approx(used, rel=1e-12, abs=1e-12)
        explicit = np.mean(np.clip(oracle.history[-window:], -.8, .8), axis=0)
        assert bp.clipped_mean_llr == pytest.approx(explicit, rel=1e-12, abs=1e-12)
        assert bp.history_count == min(iteration + 1, window)


def test_fixations_residual_and_disabled_edges_against_reduced_oracle():
    rows = [[0, 1, 2], [1, 2, 3], [0, 2, 3]]
    p, syndrome, fixed = [.13, .17, .21, .29], [0, 1, 1], [(0, 1)]
    bp = session(rows, p)
    bp.reset_from_channel(syndrome, fixed)
    oracle = Scalar(rows, p, syndrome, fixed)
    assert bp.residual_syndrome == [1, 1, 0]
    all_edges = [(a, j) for a, row in enumerate(rows) for j in row]
    for _ in range(9):
        expected = oracle.step()
        assert bp.continue_iterations(1).actual_iterations == expected
        assert bp.decision == oracle.decision and bp.decision[0] == 1
        assert bp.posterior_llr[0] == -math.inf
        assert bp.clipped_mean_llr[0] == -2.
        snap = bp.snapshot()
        for e, q in zip(all_edges, snap.q):
            assert q == (0 if e[1] == 0 else pytest.approx(oracle.q[e], rel=1e-12, abs=1e-12))
        assert bp.posterior_llr[1:] == pytest.approx(oracle.llr[1:], rel=1e-12, abs=1e-12)
    bp.reset_from_channel([0, 0, 0], [(0, 0), (2, 1)])
    assert bp.residual_syndrome == [1, 1, 1]
    bp.continue_iterations(6)
    assert bp.decision[0] == 0 and bp.decision[2] == 1


def test_continuation_restore_and_snapshot_ownership():
    rows, p, syndrome = [[0, 1], [1, 2], [0, 2]], [.1, .19, .27], [1, 0, 0]
    split, whole = session(rows, p), session(rows, p)
    for bp in (split, whole): bp.reset_from_channel(syndrome, shot_id=7)
    split.continue_iterations(2)
    snapshot = split.snapshot()
    old_q = snapshot.q
    old_z = snapshot.check_to_variable
    detached = snapshot.q; detached[0] = 1000
    detached_z = snapshot.check_to_variable; detached_z[0] = 1000
    assert snapshot.q == old_q
    assert snapshot.check_to_variable == old_z
    split.continue_iterations(9); whole.continue_iterations(11)
    assert split.snapshot().q == whole.snapshot().q
    assert split.posterior_llr == whole.posterior_llr
    assert split.clipped_mean_llr == whole.clipped_mean_llr
    split.restore(snapshot); assert split.total_iterations == 2
    assert split.check_to_variable == old_z
    split.continue_iterations(9)
    assert split.clipped_mean_llr == whole.clipped_mean_llr
    assert snapshot.q == old_q and snapshot.check_to_variable == old_z
    assert snapshot.total_iterations == 2
    # E=6,N=3,W=3,M=3; payload omits graph, decision and residual.
    assert snapshot.payload_bytes == split.snapshot_payload_bytes == 8*(2*6+2*3+3*3)+3+3


def test_descendant_preserves_parent_messages_and_resets_history():
    rows, p, syndrome = [[0, 1, 3], [1, 2, 3], [0, 2]], [.1, .19, .27, .31], [1, 0, 0]
    parent = session(rows, p); parent.reset_from_channel(syndrome, [(3, 0)], shot_id=12)
    parent.continue_iterations(2); snapshot = parent.snapshot()
    child = session(rows, p); child.reset_from_channel(syndrome, shot_id=12)
    child.inherit_descendant(snapshot, [(0, 1)])
    assert child.fixed == [1, -1, -1, 0]
    assert child.history_count == child.total_iterations == 0
    all_edges = [(a, j) for a, row in enumerate(rows) for j in row]
    for e, q, z in zip(all_edges, child.snapshot().q, child.check_to_variable):
        if e[1] in (0, 3):
            assert q == z == 0
    oracle = Scalar(rows, p, syndrome, [(0, 1), (3, 0)])
    edge_values = dict(zip([(a, j) for a, row in enumerate(rows) for j in row], snapshot.q))
    oracle.q = {e: edge_values[e] for e in oracle.edges}
    for j in (1, 2):
        oracle.llr[j] = snapshot.posterior_llr[j]
        oracle.decision[j] = int(oracle.llr[j] <= 0)
    for _ in range(4):
        expected = oracle.step()
        assert child.continue_iterations(1).actual_iterations == expected
        assert child.decision == oracle.decision
        assert [child.posterior_llr[j] for j in (1, 2)] == pytest.approx([oracle.llr[j] for j in (1, 2)], rel=1e-12, abs=1e-12)
        for e, q, z in zip(all_edges, child.snapshot().q, child.check_to_variable):
            if e[1] in (0, 3):
                assert q == z == 0
    assert parent.snapshot().q == snapshot.q and parent.fixed == [-1, -1, -1, 0]
    for additional in ([], [(3, 0)], [(3, 1)], [(0, 0), (0, 1)], [(2, 0), (1, 1)]):
        child.reset_from_channel(syndrome, shot_id=12)
        with pytest.raises(ValueError): child.inherit_descendant(snapshot, additional)
        with pytest.raises(RuntimeError): child.continue_iterations(1)


def test_statuses_zero_budget_early_valid_and_contradiction():
    bp = session([[0, 1], [0]], [.1, .2])
    bp.reset_from_channel([1, 1], [(0, 0), (1, 0)])
    result = bp.continue_iterations(10)
    assert result.status.name == 'LOCAL_CONTRADICTION'
    assert result.requested_iterations == 10 and result.actual_iterations == result.total_iterations == 0
    bp.reset_from_channel([1, 1], [(0, 1), (1, 0)])
    assert bp.continue_iterations(10).status.name == 'CONVERGED' and bp.history_count == 0
    bp.reset_from_channel([1, 1])
    assert bp.continue_iterations(0).status.name == 'BUDGET_EXHAUSTED'
    result = bp.continue_iterations(10)
    assert result.valid and result.actual_iterations == 2
    assert bp.continue_iterations(10).actual_iterations == 0 and bp.total_iterations == 2
    bp.reset_from_channel([0, 0]); assert bp.continue_iterations(10).actual_iterations == 0
    assert bp.decision == [0, 0]
    empty = session([[]], [])
    empty.reset_from_channel([1]); assert empty.status.name == 'LOCAL_CONTRADICTION'
    empty.reset_from_channel([0]); assert empty.continue_iterations(3).valid


def test_reset_repeatability_extreme_checks_and_checked_boundaries():
    bp = session([[0], [0], [0]], [.1], alpha=1.)
    for _ in range(3):
        bp.reset_from_channel([0, 1, 0], shot_id=5)
        first = bp.continue_iterations(4)
        assert first.actual_iterations == 4 and bp.history_count == 3
        assert all(math.isfinite(x) for x in bp.posterior_llr + bp.snapshot().q)
        saved = bp.snapshot()
        bp.reset_from_channel([0, 0, 0], shot_id=6)
        assert bp.continue_iterations(4).actual_iterations == 0 and bp.history_count == 0
        with pytest.raises(ValueError): bp.restore(saved)
        bp.reset_from_channel([0, 1, 0], shot_id=5)
        bp.continue_iterations(4)
        assert bp.snapshot().q == saved.q
    for fixed in ([(0, 2)], [(-1, 0)], [(1, 0)], [(0, -1)]):
        with pytest.raises(ValueError): bp.reset_from_channel([0, 0, 0], fixed)
        with pytest.raises(RuntimeError): bp.snapshot()
    with pytest.raises(ValueError): bp.reset_from_channel([0, 2, 0])
    for kwargs in ({'window': 0}, {'clip': math.inf}, {'clip': 0.}, {'alpha': 0.}, {'alpha': 1.1}):
        with pytest.raises(ValueError): session([[0]], [.1], **kwargs)
    for other in (session([[0], [0], [0]], [.2]), session([[0], [0], [0]], [.1], window=2)):
        other.reset_from_channel([0, 1, 0], shot_id=5)
        with pytest.raises(ValueError): other.restore(saved)
    bp.reset_from_channel([0, 1, 0])
    with pytest.raises(ValueError): bp.continue_iterations(-1)


def test_zero_llr_tie_and_history_clip_does_not_clip_messages():
    bp = session([[0, 1]], [.5, .5])
    bp.reset_from_channel([0]); assert bp.decision == [1, 1]
    assert bp.continue_iterations(2).actual_iterations == 0
    bp = session([[0]], [.1], clip=.01)
    bp.reset_from_channel([1]); result = bp.continue_iterations(10)
    assert result.actual_iterations == 1 and bp.posterior_llr[0] < -1e300
    assert bp.clipped_mean_llr == [-.01]
