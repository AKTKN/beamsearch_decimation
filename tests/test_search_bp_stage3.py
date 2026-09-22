"""Independent scalar SEARCH-BP-2.0 Steps 1--4 equations and bounded trees."""
import heapq
import itertools
import math
import random

import pytest
from ldpc.hybrid_bp import DecimatedMinSumSession
from qec_bp_benchmark import _native as native


def settings(**values):
    out = native.SearchBPStage3Settings()
    for key, value in values.items():
        setattr(out, key, value)
    return out


def service(rows, p, **values):
    return native.SearchBPStage3(rows, len(p), p, [], settings(**values))


def reference(rows, p, syndrome, fixed, mean, beta=1., delta=(), strength=1.):
    """Recompute every check from scratch, with no touched-check optimization."""
    ancestor = dict(fixed)
    child = dict(ancestor)
    child.update(delta)
    confidence = [1. if j in ancestor else abs(math.tanh(x/2)) for j, x in enumerate(mean)]
    free = [j for j in range(len(p)) if j not in ancestor]

    def parity_state(pattern):
        residual = [s ^ (sum(pattern.get(j, 0) for j in row) % 2) for s, row in zip(syndrome, rows)]
        probability = [.5 * (1 + (-1)**s * math.prod(math.tanh(mean[j]/2) for j in row if j not in pattern))
                       for s, row in zip(residual, rows)]
        return residual, probability

    residual, probability = parity_state(ancestor)
    new_residual, hypothetical = parity_state(child)
    variable = sum(1-confidence[j] for j in free)/len(free) if free else 0.
    objective = variable + beta * sum(1-x for x in probability)/len(rows) if rows else variable
    result = dict(confidence=confidence, probability=probability, ambiguity=[1-x for x in probability],
                  residual=residual, objective=objective, hypothetical=hypothetical, new_residual=new_residual)
    if not delta:
        return result
    j_var = sum(max(0., (2*b-1)*mean[j]) + math.log1p(math.exp(-abs(mean[j]))) for j, b in delta)/len(delta)
    new_variable = sum(1-confidence[j] for j in free if j not in child)/len(free)
    new_objective = new_variable + (beta * sum(1-x for x in hypothetical)/len(rows) if rows else 0.)
    gain = (objective-new_objective)/len(delta)
    weights = [math.log((1-x)/x) for x in p]
    g = sum(weights[j] for j, b in child.items() if b)
    unsatisfied = [a for a, s in enumerate(new_residual) if s]
    coverage = {j: sum(j in rows[a] for a in unsatisfied) for j in range(len(p)) if j not in child}
    h = sum(min((weights[j]/coverage[j] for j in rows[a] if j not in child), default=math.inf) for a in unsatisfied)
    result.update(g=g, h=h, f_solve=g+h, j_var=j_var, g_amb=gain, f_guide=j_var-strength*gain)
    return result


def fingerprint(pool):
    return [(x.parent_id, tuple(x.delta), x.depth, x.f_solve, x.f_guide) for x in pool]


def reference_tree(rows, p, syndrome, fixed, mean, selected, m, q, beta, strength, policy='refresh_descendant'):
    parent = reference(rows, p, syndrome, fixed, mean, beta)
    checks = sorted(range(len(rows)), key=lambda a: (-parent['ambiguity'][a], a))[:selected]
    candidates = []
    solution = None
    weights = [math.log((1-x)/x) for x in p]
    for anchor in checks:
        local = sorted((j for j in rows[anchor] if j not in dict(fixed)), key=lambda j: (parent['confidence'][j], j))[:m]
        if not parent['residual'][anchor]:
            # Independent combinations/product enumeration; order compared as a set.
            for depth in range(1, min(q, len(local))+1):
                for subset in itertools.combinations(sorted(local), depth):
                    for bits in itertools.product((0, 1), repeat=depth):
                        delta = tuple(zip(subset, bits))
                        score = reference(rows, p, syndrome, fixed, mean, beta, delta, strength)
                        candidates.append((delta, None, score['f_guide']))
            continue
        local.sort(key=lambda j: (weights[j], j))
        frontier = []
        seen = set()

        def branch(check, base, eligible):
            nonlocal solution
            prefix = dict(base)
            for j in eligible:
                if j in dict(base) or j not in rows[check]:
                    continue
                if len(prefix) == q:
                    break
                prefix[j] = 1
                delta = tuple(sorted(prefix.items()))
                if delta in seen:
                    prefix[j] = 0
                    continue
                seen.add(delta)
                score = reference(rows, p, syndrome, fixed, mean, beta, delta, strength)
                candidates.append((delta, score['f_solve'], score['f_guide']))
                if not any(score['new_residual']):
                    full = dict(fixed); full.update(delta)
                    solution = [full.get(j, 0) for j in range(len(p))]
                    return
                if len(delta) < q and math.isfinite(score['f_solve']):
                    heapq.heappush(frontier, (score['f_solve'], delta))
                prefix[j] = 0

        branch(anchor, (), local)
        while frontier and solution is None:
            _, delta = heapq.heappop(frontier)
            state = reference(rows, p, syndrome, fixed, mean, beta, delta, strength)
            residual = state['new_residual']
            if policy == 'fixed_root':
                branch(residual.index(1), delta, local)
            else:
                check = min((a for a,s in enumerate(residual) if s), key=lambda a: (state['hypothetical'][a], a))
                free = [j for j in rows[check] if j not in dict(fixed) and j not in dict(delta)]
                chosen = sorted(free, key=lambda j: (parent['confidence'][j], j))[:m]
                branch(check, delta, sorted(chosen, key=lambda j: (weights[j], j)))
        if solution is not None:
            break
    return candidates, solution


def test_confidence_check_scores_selection_and_all_formula_terms():
    rows = [[0, 1, 2], [1, 3], [0, 4], [], [2, 3, 4]]
    p = [.07, .13, .23, .31, .41]
    mean = [-1.7, .3, 0., 2.4, -.9]
    syndrome, fixed = [1, 0, 0, 1, 1], [(4, 1)]
    decoder = service(rows, p, beta=1.6)
    parent = decoder.summarize(syndrome, fixed, mean)
    ref = reference(rows, p, syndrome, fixed, mean, 1.6)
    assert parent.residual == ref['residual']
    for name in ('confidence', 'probability', 'ambiguity', 'objective'):
        assert getattr(parent, name) == pytest.approx(ref[name], rel=1e-12, abs=1e-14)
    assert parent.select_checks(100) == sorted(range(len(rows)), key=lambda a: (-ref['ambiguity'][a], a))
    for a, row in enumerate(rows):
        assert parent.select_variables(a, 2) == sorted((j for j in row if j != 4), key=lambda j: (ref['confidence'][j], j))[:2]
    original = (parent.mean, parent.fixed, parent.residual, parent.probability, parent.objective)
    for depth in (1, 2, 3, 4):
        for subset in itertools.combinations(range(4), depth):
            for bits in itertools.product((0, 1), repeat=depth):
                delta = list(zip(subset, bits))
                score, residual, hypothetical = parent.inspect_pattern(delta, .7)
                ref = reference(rows, p, syndrome, fixed, mean, 1.6, delta, .7)
                assert residual == ref['new_residual']
                assert hypothetical == pytest.approx(ref['hypothetical'], rel=1e-12, abs=1e-14)
                for name in ('g', 'h', 'f_solve', 'j_var', 'g_amb', 'f_guide'):
                    assert getattr(score, name) == pytest.approx(ref[name], rel=1e-12, abs=1e-13)
    assert (parent.mean, parent.fixed, parent.residual, parent.probability, parent.objective) == original


def test_random_scalar_scores_exact_parity_and_tight_float_tolerances():
    """Vary masks/graph shapes and repeatedly replace scratch patterns on a parent."""
    rng = random.Random(20260922)
    for _ in range(32):
        n = rng.randrange(2, 9)
        rows = [sorted(rng.sample(range(n), rng.randrange(n+1))) for _ in range(rng.randrange(1, 8))]
        p = [rng.uniform(.01, .49) for _ in range(n)]
        mean = [rng.choice([-25., -2.7, -.001, 0., .001, 1.3, 25.]) for _ in range(n)]
        fixed = [(j, rng.randrange(2)) for j in range(n-1) if rng.random() < .3]
        free = [j for j in range(n) if j not in dict(fixed)]
        syndrome = [rng.randrange(2) for _ in rows]
        beta, strength = rng.random()*3, rng.random()*3
        parent = service(rows, p, beta=beta).summarize(syndrome, fixed, mean)
        expected = reference(rows, p, syndrome, fixed, mean, beta)
        assert parent.residual == expected['residual']  # exact GF(2)
        for name in ('confidence', 'probability', 'ambiguity', 'objective'):
            assert getattr(parent, name) == pytest.approx(expected[name], rel=1e-12, abs=2e-14)
        for count in (1, 3, 99):
            assert parent.select_checks(count) == sorted(range(len(rows)), key=lambda a: (-expected['ambiguity'][a], a))[:count]
            for a, row in enumerate(rows):
                assert parent.select_variables(a, count) == sorted((j for j in row if j in free), key=lambda j: (expected['confidence'][j], j))[:count]
        for _ in range(16):
            delta = [(j, rng.randrange(2)) for j in sorted(rng.sample(free, rng.randrange(1, len(free)+1)))]
            score, residual, hypothetical = parent.inspect_pattern(delta, strength)
            expected = reference(rows, p, syndrome, fixed, mean, beta, delta, strength)
            assert residual == expected['new_residual']
            assert hypothetical == pytest.approx(expected['hypothetical'], rel=1e-12, abs=2e-14)
            for name in ('g', 'h', 'f_solve', 'j_var', 'g_amb', 'f_guide'):
                assert getattr(score, name) == pytest.approx(expected[name], rel=1e-12, abs=2e-14)


def test_satisfied_enumeration_count_parity_changes_and_ties():
    rows, p, mean = [[0, 1, 2, 3]], [.1]*4, [0.]*4
    for m in range(1, 5):
        for q in range(1, m+1):
            decoder = service(rows, p, selected_checks=1, local_variables=m, max_fixations=q)
            parent = decoder.summarize([0], [], mean)
            result = decoder.expand(parent, 17)
            expected, _ = reference_tree(rows, p, [0], [], mean, 1, m, q, 1., 1.)
            assert len(result.candidates) == native.search_bp_pattern_bound(m, q) == sum(math.comb(m,d)*2**d for d in range(1,q+1))
            assert sorted(tuple(c.delta) for c in result.candidates) == sorted(d for d, _, _ in expected)
            assert all(c.f_solve is None and c.parent_id == 17 and c.depth <= q for c in result.candidates)
            assert any(c.delta == [(0,1)] for c in result.candidates)  # temporary parity change survives
            assert not result.valid
            assert fingerprint(result.candidates) == fingerprint(decoder.expand(parent, 17).candidates)
            assert parent.select_variables(0, m) == list(range(m))
            for c in result.candidates:
                assert c.tie_key == (c.delta, 17)
    parent = service([[0], [1], [2]], [.1]*3).summarize([0,1,0], [], [0.]*3)
    assert parent.select_checks(2) == [0,1]  # includes satisfied check 0
    assert native.search_bp_pattern_bound(0,3) == 0
    with pytest.raises((ValueError, OverflowError)):
        native.search_bp_pattern_bound(100,100)


def test_unsatisfied_canonical_exclusions_depth_and_physical_order():
    rows, p = [[0, 1, 2], [0, 1, 2]], [.1, .3, .2]
    decoder = service(rows, p, selected_checks=1, local_variables=3, max_fixations=3)
    parent = decoder.summarize([1,0], [], [0.,0.,0.])
    pool = decoder.expand(parent).candidates
    # Physical order 1,2,0; canonical zeros count as fixations and remain sorted.
    assert [c.delta for c in pool[:3]] == [[(1,1)], [(1,0),(2,1)], [(0,1),(1,0),(2,0)]]
    assert all(c.depth <= 3 for c in pool)
    assert len(pool) <= native.search_bp_pattern_bound(3,3)
    shallow = service(rows, p, selected_checks=1, local_variables=3, max_fixations=1)
    assert [c.delta for c in shallow.expand(shallow.summarize([1,0], [], [0.]*3)).candidates] == [[(1,1)]]


@pytest.mark.parametrize('policy', ['fixed_root', 'refresh_descendant'])
@pytest.mark.parametrize('seed', range(12))
def test_random_bounded_search_against_independent_tree(seed, policy):
    rng = random.Random(seed)
    n = 6
    rows = [sorted(rng.sample(range(n), rng.randint(1,n))) for _ in range(5)]
    p = [.06+.05*j for j in range(n)]
    syndrome = [rng.randrange(2) for _ in rows]
    fixed = [(5,rng.randrange(2))]
    mean = [rng.choice([-1.8, -.2, 0., .4, 1.3]) for _ in range(n)]
    decoder = service(rows, p, selected_checks=4, local_variables=4, max_fixations=3, beta=1.4, guidance_strength=.8, local_variable_policy=policy)
    parent = decoder.summarize(syndrome, fixed, mean)
    result = decoder.expand(parent, seed)
    expected, solution = reference_tree(rows, p, syndrome, fixed, mean, 4, 4, 3, 1.4, .8, policy)
    sort_key = lambda item: (item[0], item[1] is None)
    actual = sorted(((tuple(c.delta), c.f_solve, c.f_guide) for c in result.candidates), key=sort_key)
    expected.sort(key=sort_key)
    assert len(actual) == len(expected)
    for a, b in zip(actual, expected):
        assert a[0] == b[0]
        assert a[1] == pytest.approx(b[1], rel=1e-12, abs=1e-13) if b[1] is not None else a[1] is None
        assert a[2] == pytest.approx(b[2], rel=1e-12, abs=1e-13)
    assert result.valid == (solution is not None)
    if solution is not None:
        assert result.correction == solution
        assert [sum(solution[j] for j in row)%2 for row in rows] == syndrome
        assert solution[5] == fixed[0][1]


def test_fractional_cover_uses_all_free_variables_not_only_local_set():
    rows, p = [[0,1,3], [1,2], [2,3]], [.1,.2,.3,.4]
    decoder = service(rows, p, local_variables=1, max_fixations=1)
    parent = decoder.summarize([1,1,1], [], [0.,1.,2.,3.])
    score, _, _ = parent.inspect_pattern([(0,0)], 1.)
    ref = reference(rows,p,[1,1,1],[],[0.,1.,2.,3.],delta=[(0,0)])
    assert math.isfinite(score.h) and score.h == pytest.approx(ref['h'], rel=1e-12, abs=1e-13)


def test_initial_bp_mean_snapshot_immutability_reset_and_full_validation():
    rows, p, syndrome = [[0,1], [1,2], [0,2]], [.1,.19,.27], [1,0,0]
    opts = dict(initial_iterations=5, history_window=3, history_clip=.8, scaling_factor=.75)
    decoder = service(rows, p, **opts)
    result = decoder.run_initial(syndrome, 29)
    bp = DecimatedMinSumSession(rows, 3, p, 3, .8, .75)
    bp.reset_from_channel(syndrome, [], 29); bp.continue_iterations(5)
    assert not result.valid and result.bp.actual_iterations == 5
    assert result.parent_scores.mean == bp.clipped_mean_llr
    assert result.parent_scores.confidence == pytest.approx([abs(math.tanh(x/2)) for x in bp.clipped_mean_llr], rel=1e-12, abs=1e-14)
    assert result.parent_scores.confidence != pytest.approx([abs(math.tanh(x/2)) for x in bp.posterior_llr])
    saved = result.parent_state
    before = (saved.q, saved.posterior_llr, saved.fixed, saved.total_iterations, saved.history_count)
    assert fingerprint(decoder.expand_parent(saved, 29).candidates) == fingerprint(result.candidates)
    assert (saved.q, saved.posterior_llr, saved.fixed, saved.total_iterations, saved.history_count) == before
    # Prior successful shot must not leak into a later failed shot.
    zero = decoder.run_initial([0,0,0], 30)
    assert zero.valid and zero.initial_success and zero.bp.actual_iterations == 0
    assert zero.candidates == [] and zero.parent_state is None and zero.parent_scores is None
    repeated = decoder.run_initial(syndrome, 31)
    assert repeated.parent_scores.mean == result.parent_scores.mean
    assert repeated.parent_state.q == saved.q
    # Nonzero BP success is independently H-validated and A-projected.
    easy = native.SearchBPStage3([[0]], 1, [.1], [[0]], settings())
    success = easy.run_initial([1])
    assert success.valid and success.initial_success and success.correction == success.prediction == [1]
    assert success.bp.actual_iterations == 1 and success.candidates == []


def test_direct_solution_immediate_validation_and_ancestor_preservation():
    decoder = service([[0,1],[1,2]], [.1,.2,.3], selected_checks=2)
    parent = decoder.summarize([1,1], [(2,0)], [1.,0.,1.])
    result = decoder.expand(parent, 9)
    assert result.valid and result.correction == [0,1,0]
    assert len(result.candidates) == 1  # physical cheapest branch, immediate return
    assert result.candidates[0].f_solve == pytest.approx(math.log(4), rel=1e-12, abs=1e-13)


def test_numerical_extremes_empty_sets_and_checked_boundaries():
    decoder = service([[0],[]], [.1])
    parent = decoder.summarize([1,1], [], [1e300])
    score, residual, probability = parent.inspect_pattern([(0,1)], 1.)
    assert score.j_var == 1e300 and score.h == math.inf and math.isfinite(score.f_guide)
    assert residual == [0,1] and probability == [1.,0.]
    terminal = decoder.run_initial([0,1])
    assert not terminal.valid and terminal.bp.actual_iterations == 0 and not terminal.candidates
    empty = service([], []).run_initial([])
    assert empty.valid and empty.correction == []
    full = decoder.summarize([1,0], [(0,1)], [math.nan])
    assert full.confidence == [1.] and full.objective == 0 and decoder.expand(full).candidates == []
    for delta in ([], [(0,2)], [(-1,0)], [(1,0)], [(0,0),(0,1)]):
        with pytest.raises(ValueError): parent.inspect_pattern(delta, 1.)
    with pytest.raises(ValueError): full.inspect_pattern([(0,1)],1.)
    for values in ({'initial_iterations':1}, {'max_fixations':5, 'local_variable_policy':'fixed_root'}, {'local_variable_policy':'unknown'}, {'beta':math.nan}, {'scaling_factor':0.}):
        with pytest.raises(ValueError): service([[0]], [.1], **values)
    for means in ([], [math.inf], [math.nan]):
        with pytest.raises(ValueError): decoder.summarize([0,0], [], means)
    with pytest.raises(ValueError): decoder.summarize([2,0], [], [0.])
    with pytest.raises(ValueError): decoder.expand(service([[0],[]],[.1]).summarize([0,0],[],[0.]))
    bp = DecimatedMinSumSession([[0],[]],1,[.1])
    bp.reset_from_channel([0,0])
    with pytest.raises(ValueError): decoder.expand_parent(bp.snapshot())


def test_refresh_descendant_leaves_root_and_uses_hypothetical_ambiguity():
    rows, p, syndrome, means = [[0], [1], [2]], [.1,.2,.3], [1,1,1], [-3.,0.,4.]
    refresh = service(rows, p, selected_checks=1, local_variables=1, max_fixations=3)
    parent = refresh.summarize(syndrome, [], means)
    assert parent.select_checks(1) == [2]
    result = refresh.expand(parent)
    assert result.valid and result.correction == [1,1,1]
    assert [c.delta for c in result.candidates] == [[(2,1)], [(1,1),(2,1)], [(0,1),(1,1),(2,1)]]
    # Check 1 is more ambiguous than check 0. Choosing lowest index would differ.
    assert parent.ambiguity[1] > parent.ambiguity[0]
    assert len(result.candidates) > native.search_bp_pattern_bound(1,1)
    fixed = service(rows, p, selected_checks=1, local_variables=3, max_fixations=3, local_variable_policy='fixed_root')
    limited = fixed.expand(fixed.summarize(syndrome, [], means))
    assert not limited.valid and [c.delta for c in limited.candidates] == [[(2,1)]]


@pytest.mark.parametrize('policy', ['fixed_root', 'refresh_descendant'])
def test_per_tree_dedup_bounds_and_fresh_search_per_parent(policy):
    rows, p, syndrome = [[0,1,2],[1,2,3],[0,2,3],[0,1,2]], [.1,.2,.3,.4], [1,0,0,0]
    decoder = service(rows, p, selected_checks=1, local_variables=3, max_fixations=3, local_variable_policy=policy)
    parent = decoder.summarize(syndrome, [], [0.]*4)
    first = decoder.expand(parent, 8)
    patterns = [tuple(c.delta) for c in first.candidates]
    assert len(patterns) == len(set(patterns))
    bound = native.search_bp_pattern_bound(3,3) if policy == 'fixed_root' else min(native.search_bp_pattern_bound(4,3), sum(3**d for d in range(1,4)))
    assert len(patterns) <= bound
    decoder.expand(decoder.summarize([0,1,0,0], [(0,0)], [2.,1.,-1.,.1]), 9)
    assert fingerprint(decoder.expand(parent, 8).candidates) == fingerprint(first.candidates)


def test_initial_bp_failure_then_immediate_search_solution():
    decoder = native.SearchBPStage3([[0,1],[1,2]], 3, [.1]*3, [[1]],
                                    settings(initial_iterations=1, history_window=1))
    result = decoder.run_initial([1,1], 11)
    assert result.valid and not result.initial_success
    assert result.bp.actual_iterations == 1 and not result.bp.valid
    assert result.correction == [0,1,0] and result.prediction == [1]
    assert all(c.parent_id == 11 for c in result.candidates)
