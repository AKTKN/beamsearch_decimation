"""Independent small-graph rules for the opt-in fork BP engines."""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess

import numpy as np
import pytest

from ldpc.af_bp import BPConfig, BPDecoder, QditherDecoder, build_identity
from ldpc.af_bp.source_files import SOURCE_FILES, source_digest


ROOT = Path(__file__).resolve().parents[1]
FORK = ROOT / "external_lib/ldpc"
H = np.array([[1, 1, 0], [0, 1, 1]], dtype=np.uint8)
BASE = np.array([1.1, -0.4, 0.7])
QINIT = np.array([0.2, 0.3, -0.5])


def _oracle_step(rows, base, syndrome, messages, checks, order):
    """Small dense edge oracle; each row/edge is recomputed independently."""
    edges = [(a, v) for a, row in enumerate(rows) for v in row]
    messages = np.array(messages, dtype=float)
    checks = np.array(checks, dtype=float)
    for a in order:
        for i, (check, variable) in enumerate(edges):
            if check != a:
                continue
            others = [messages[j] for j, (b, _) in enumerate(edges) if b == a and j != i]
            checks[i] = ((-1) ** syndrome[a] * np.prod(np.sign(others)) *
                         min(map(abs, others)))
        for variable in rows[a]:
            incident = [i for i, (_, v) in enumerate(edges) if v == variable]
            for i in incident:
                messages[i] = base[variable] + sum(checks[j] for j in incident if j != i)
    llrs = np.array([base[v] + sum(checks[i] for i, (_, u) in enumerate(edges) if u == v)
                     for v in range(len(base))])
    return checks, messages, llrs


def test_parallel_synchronous_and_handoff_prior() -> None:
    result = BPDecoder(H, BASE, BPConfig(max_iterations=1)).decode_detailed(
        [1, 0], q_init=QINIT, diagnostics=True)
    edges = [(0, 0), (0, 1), (1, 1), (1, 2)]
    old = [QINIT[v] for _, v in edges]
    checks = []
    for a, v in edges:
        other = next(u for u in np.flatnonzero(H[a]) if u != v)
        checks.append((-1) ** [1, 0][a] * old[edges.index((a, other))])
    messages = [BASE[v] + sum(checks[j] for j, (_, u) in enumerate(edges)
                              if u == v and j != i) for i, (_, v) in enumerate(edges)]
    llrs = [BASE[v] + sum(checks[i] for i, (_, u) in enumerate(edges) if u == v)
            for v in range(3)]
    step = result.attempts[0].steps[0]
    np.testing.assert_allclose(step.check_to_variable, checks)
    np.testing.assert_allclose(step.variable_to_check, messages)
    np.testing.assert_allclose(result.final_llrs, llrs)
    assert result.total_iterations == 1
    np.testing.assert_allclose(result.trailing_history[-1], llrs)
    # Handoff was only an initial edge state; the immutable base remains unary.
    assert not np.allclose(llrs, QINIT + np.array([checks[0], checks[1] + checks[2], checks[3]]))


def test_serial_immediate_reuse_natural_and_seeded_random() -> None:
    syndrome = [1, 0]
    for order_type in ("natural", "random_per_iteration"):
        config = BPConfig(variant="serial", max_iterations=1, serial_order=order_type, seed=19)
        result = BPDecoder(H, BASE, config).decode_detailed(syndrome, q_init=QINIT, diagnostics=True)
        step = result.attempts[0].steps[0]
        assert sorted(step.order) == [0, 1]
        if order_type == "natural":
            assert step.order == [0, 1]
        expected = _oracle_step([[0, 1], [1, 2]], BASE, syndrome,
                                [QINIT[0], QINIT[1], QINIT[1], QINIT[2]],
                                [0, 0, 0, 0], step.order)
        np.testing.assert_allclose(step.check_to_variable, expected[0])
        np.testing.assert_allclose(step.variable_to_check, expected[1])
        np.testing.assert_allclose(result.final_llrs, expected[2])
        again = BPDecoder(H, BASE, config).decode_detailed(syndrome, q_init=QINIT, diagnostics=True)
        assert again.attempts[0].steps[0].order == step.order
    # With order [0,1], check 1 reads the immediately updated variable 1.
    natural = BPDecoder(H, BASE, BPConfig(variant="serial", max_iterations=1)).decode_detailed(
        syndrome, q_init=QINIT, diagnostics=True)
    parallel = BPDecoder(H, BASE, BPConfig(max_iterations=1)).decode_detailed(
        syndrome, q_init=QINIT, diagnostics=True)
    assert natural.attempts[0].steps[0].check_to_variable != parallel.attempts[0].steps[0].check_to_variable


def test_random_serial_draws_fresh_seeded_permutations_per_sweep() -> None:
    h = np.array([[1, 1, 0], [1, 1, 0], [0, 1, 1]], dtype=np.uint8)
    decoder = BPDecoder(h, BASE, BPConfig(variant="serial", max_iterations=5,
                                          serial_order="random_per_iteration", seed=19))
    first = decoder.decode_detailed([0, 1, 0], diagnostics=True)
    replay = decoder.decode_detailed([0, 1, 0], diagnostics=True)
    orders = [tuple(step.order) for step in first.attempts[0].steps]
    assert first.total_iterations == 5
    assert len(set(orders)) > 1
    assert all(sorted(order) == [0, 1, 2] for order in orders)
    assert orders == [tuple(step.order) for step in replay.attempts[0].steps]


def test_qdither_phase_one_matches_parallel_and_paper_rejects_handoff() -> None:
    parallel = BPDecoder(H, BASE, BPConfig(max_iterations=2)).decode_detailed([1, 0])
    dither = QditherDecoder(H, BASE, phase1_iterations=2, num_chains=0).decode_detailed([1, 0])
    assert dither.success == parallel.success
    np.testing.assert_array_equal(dither.correction, parallel.correction)
    np.testing.assert_allclose(dither.final_llrs, parallel.final_llrs)
    np.testing.assert_allclose(dither.trailing_history, parallel.trailing_history)
    assert dither.total_iterations == parallel.total_iterations
    with pytest.raises(ValueError, match="paper"):
        QditherDecoder(H, BASE).decode_detailed([1, 0], q_init=QINIT)
    warm = QditherDecoder(H, BASE, phase1_iterations=1, num_chains=0,
                          handoff="graph_warm").decode_detailed([1, 0], q_init=QINIT)
    ordinary = BPDecoder(H, BASE, BPConfig(max_iterations=1)).decode_detailed([1, 0], q_init=QINIT)
    np.testing.assert_allclose(warm.final_llrs, ordinary.final_llrs)


def test_qdither_mixing_rsf_posterior_inheritance_and_reset() -> None:
    # Contradictory duplicate checks force every phase and chain to finish.
    h = np.array([[1, 1], [1, 1]], dtype=np.uint8)
    decoder = QditherDecoder(h, [1.2, -0.7], phase1_iterations=2,
                             num_chains=2, chain_iterations=3,
                             alpha=0.7, beta=0.7, rho=1, seed=3, history_window=2)
    first = decoder.decode_detailed([0, 1], diagnostics=True)
    second = decoder.decode_detailed([0, 1], diagnostics=True)
    assert not first.success and first.total_iterations == 8
    assert first.phase1_iterations_executed == 2
    assert first.chain_iterations_executed == (3, 3)
    assert len(first.attempts) == 3
    for left, right in zip(first.attempts, second.attempts):
        np.testing.assert_allclose(left.bias, right.bias)
        assert left.rsf_mask == right.rsf_mask
        for x, y in zip(left.steps, right.steps):
            np.testing.assert_allclose(x.variable_to_check, y.variable_to_check)
    phase1, chain1, chain2 = first.attempts
    np.testing.assert_allclose(chain1.bias, [1.2, -0.7])  # q^(0)=base
    np.testing.assert_allclose(chain2.bias,
                               0.3 * np.array([1.2, -0.7]) + 0.7 * np.array(chain1.steps[-1].marginals))
    assert chain1.rsf_mask == [1, 1]
    changed = 0
    for attempt in (chain1, chain2):
        old = np.asarray(attempt.initial_messages)
        for step in attempt.steps:
            provisional = np.asarray(step.provisional_variable_to_check)
            actual = np.asarray(step.variable_to_check)
            for edge, variable in enumerate((0, 1, 0, 1)):
                expected = provisional[edge]
                if attempt.rsf_mask[variable] and np.sign(expected) != np.sign(old[edge]):
                    expected += old[edge]
                    changed += int(old[edge] != 0)
                assert actual[edge] == pytest.approx(expected)
            old = actual
    assert changed > 0
    np.testing.assert_allclose(first.trailing_history,
                               [step.marginals for step in chain2.steps[-2:]])


def test_qdither_bernoulli_mask_and_budget_truncation() -> None:
    h = np.array([[1, 1], [1, 1]], dtype=np.uint8)
    zero = QditherDecoder(h, [1.2, -0.7], phase1_iterations=1,
                          num_chains=1, chain_iterations=2, rho=0, seed=11)
    one = QditherDecoder(h, [1.2, -0.7], phase1_iterations=1,
                         num_chains=1, chain_iterations=2, rho=1, seed=11)
    assert zero.decode_detailed([0, 1], diagnostics=True).attempts[1].rsf_mask == [0, 0]
    assert one.decode_detailed([0, 1], diagnostics=True).attempts[1].rsf_mask == [1, 1]
    capped = QditherDecoder(h, [1.2, -0.7], phase1_iterations=2,
                            num_chains=3, chain_iterations=4, rho=1,
                            max_total_iterations=3).decode_detailed([0, 1])
    assert capped.total_iterations == 3
    assert capped.phase1_iterations_executed == 2
    assert capped.chain_iterations_executed == (1,)
    assert capped.budget_truncated
    uncapped = QditherDecoder(h, [1.2, -0.7], phase1_iterations=2,
                              num_chains=3, chain_iterations=4).decode_detailed([0, 1])
    assert uncapped.total_iterations == 14 and not uncapped.budget_truncated
    early = QditherDecoder(np.array([[1, 1]], dtype=np.uint8), [1.2, -0.7],
                           phase1_iterations=4, num_chains=3, chain_iterations=4,
                           max_total_iterations=1).decode_detailed([1])
    assert early.success and not early.budget_truncated


def test_qdither_seeded_nonconstant_chi_and_once_per_chain_mask() -> None:
    h = np.array([[1, 1], [1, 1]], dtype=np.uint8)
    decoder = QditherDecoder(h, [1.2, -0.7], phase1_iterations=1, num_chains=2,
                             chain_iterations=2, alpha=0.2, beta=0.8, rho=0.5, seed=71)
    first = decoder.decode_detailed([0, 1], diagnostics=True)
    replay = decoder.decode_detailed([0, 1], diagnostics=True)
    prior = np.array([1.2, -0.7])
    for attempt, copy in zip(first.attempts[1:], replay.attempts[1:]):
        chi = np.asarray(attempt.chi)
        assert np.all((0.2 <= chi) & (chi <= 0.8))
        np.testing.assert_allclose(attempt.bias, (1 - chi) * np.array([1.2, -0.7]) + chi * prior)
        np.testing.assert_allclose(chi, copy.chi)
        assert attempt.rsf_mask == copy.rsf_mask
        assert len(attempt.rsf_mask) == 2  # one draw per variable, held for every edge/sweep
        prior = np.asarray(attempt.steps[-1].marginals)
    assert not np.allclose(first.attempts[1].chi, first.attempts[2].chi)


def test_fork_identity_and_patch_restoration(tmp_path: Path) -> None:
    assert build_identity()["source_sha256"] == source_digest(FORK)
    manifest = __import__("json").loads((ROOT / "external_lib/manifest.lock.json").read_text())
    record = manifest["dependencies"]["ldpc"]
    for name in SOURCE_FILES:
        assert hashlib.sha256((FORK / name).read_bytes()).hexdigest() == record["source_hashes"][name]
    patch = ROOT / record["patch_file"]
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record["patch_sha256"]
    worktree = tmp_path / "pristine"
    subprocess.run(["git", "clone", "--quiet", "--no-local", str(FORK), str(worktree)], check=True)
    subprocess.run(["git", "-C", str(worktree), "apply", str(patch)], check=True)
    for name in SOURCE_FILES:
        assert (worktree / name).read_bytes() == (FORK / name).read_bytes()
