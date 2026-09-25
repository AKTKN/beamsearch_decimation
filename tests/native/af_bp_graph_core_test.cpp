#include "af_bp_core/graph.hpp"
#include <cassert>
#include <cmath>
#include <iostream>
#include <set>
#include <stdexcept>

using namespace af_bp_core;

static void near(double actual, double expected) {
    if (std::abs(actual - expected) > 1e-10 * (1 + std::abs(expected)))
        throw std::runtime_error("floating result differs from independent oracle");
}

static std::vector<Biclique> exhaustive_discovery(const Graph& g, const Ids& u) {
    Ids active;
    for (int v = 0; v < g.variable_count(); ++v) {
        for (int j : g.physical_support(v))
            if (std::find(u.begin(), u.end(), j) != u.end()) {
                active.push_back(v); break;
            }
    }
    Ids related;
    for (int c = 0; c < g.check_count(); ++c)
        for (int v : g.check(c).variables)
            if (std::binary_search(active.begin(), active.end(), v)) {
                related.push_back(c); break;
            }
    std::set<Biclique> found;
    for (std::size_t i = 0; i < related.size(); ++i)
        for (std::size_t j = i + 1; j < related.size(); ++j) {
            Ids shared = intersection(g.check(related[i]).variables,
                                      g.check(related[j]).variables);
            if (shared.size() < 2) continue;
            bool touches = false;
            for (int v : shared) if (std::binary_search(active.begin(), active.end(), v)) touches = true;
            if (!touches) continue;
            Ids closure;
            for (int c : related)
                if (std::includes(g.check(c).variables.begin(), g.check(c).variables.end(),
                                  shared.begin(), shared.end())) closure.push_back(c);
            found.insert({shared, closure});
        }
    return {found.begin(), found.end()};
}

static double exhaustive_phi(const Graph& g, const Reals& omega) {
    Reals extended(g.variable_count());
    for (int v = 0; v < g.variable_count(); ++v)
        for (int physical : g.physical_support(v))
            extended[v] = std::max(extended[v], omega[physical]);
    double total = 0;
    for (int a = 0; a < g.check_count(); ++a)
        for (int b = a + 1; b < g.check_count(); ++b)
            for (int u = 0; u < g.variable_count(); ++u)
                for (int v = u + 1; v < g.variable_count(); ++v) {
                    const auto has = [&](int c, int x) {
                        const Ids& neighbors = g.check(c).variables;
                        return std::find(neighbors.begin(), neighbors.end(), x) != neighbors.end();
                    };
                    if (has(a,u) && has(a,v) && has(b,u) && has(b,v))
                        total += extended[u] * extended[v];
                }
    return total;
}

static void exact_delta(const Graph& g, const Biclique& b, const Reals& omega) {
    Graph trial = g;  // test oracle only; production delta never copies the graph
    const double old_phi = exhaustive_phi(trial, omega);
    trial.factorize(b);
    const double new_phi = exhaustive_phi(trial, omega);
    near(g.phi(omega), old_phi);
    near(trial.phi(omega), new_phi);
    near(g.net_cycle_reduction(b, omega), old_phi - new_phi);
    const auto score = g.score_candidate(b, omega);
    near(score.net_cycle_reduction, old_phi - new_phi);
    assert(score.edges_before == g.edge_count());
    assert(score.edges_after == trial.edge_count());
    assert(score.auxiliaries_after == trial.variable_count() - trial.physical_variables());
    int max_var_before = 0, max_var_after = 0, max_check_before = 0, max_check_after = 0;
    for (int v = 0; v < g.variable_count(); ++v)
        max_var_before = std::max(max_var_before, static_cast<int>(g.variable(v).checks.size()));
    for (int v = 0; v < trial.variable_count(); ++v)
        max_var_after = std::max(max_var_after, static_cast<int>(trial.variable(v).checks.size()));
    for (int c = 0; c < g.check_count(); ++c)
        max_check_before = std::max(max_check_before, static_cast<int>(g.check(c).variables.size()));
    for (int c = 0; c < trial.check_count(); ++c)
        max_check_after = std::max(max_check_after, static_cast<int>(trial.check(c).variables.size()));
    assert(score.max_variable_degree_before == max_var_before);
    assert(score.max_variable_degree_after == max_var_after);
    assert(score.max_check_degree_before == max_check_before);
    assert(score.max_check_degree_after == max_check_after);
}

static void test_failure_weights() {
    Graph g({{0,1},{1,2},{3}}, {1,1,1,1}, {1,0,0});
    FailureSettings cfg;
    cfg.residual_radius = 3;
    cfg.top_k = 2;
    auto w = g.failure_weights({0,0,0,0}, {{2,0,-1,0},{-2,0,1,0}}, cfg);
    assert((w.residual_syndrome == Ids{1,0,0}));
    assert(w.distance[0] == 1 && w.distance[1] == 1 && w.distance[2] == 3);
    assert(w.distance[3] == std::numeric_limits<int>::max());
    near(w.uncertainty[0], 1); near(w.oscillation[0], 1);
    near(w.omega[0], 0.5); near(w.omega[1], 0.25);
    near(w.omega[2], 0.125); near(w.omega[3], 0);
    assert((w.suspicious == Ids{0,1}));
    cfg.selection = "threshold"; cfg.threshold = 0.125;
    assert((g.failure_weights({0,0,0,0}, {{2,0,-1,0},{-2,0,1,0}}, cfg).suspicious == Ids{0,1,2}));
    cfg.selection = "top_k"; cfg.top_k = 2;
    Graph ties({{0,1,2}}, {0,0,0}, {1});
    assert((ties.failure_weights({0,0,0}, {{0,0,0}}, cfg).suspicious == Ids{0,1}));
    bool rejected = false;
    try { g.failure_weights({1,0,0,0}, {{0,0,0,0}}, cfg); }
    catch (const std::invalid_argument&) { rejected = true; }
    assert(rejected); // zero residual is not a factorization trigger
}

static void test_discovery_closure_dedup() {
    Graph g({{0,1,2},{0,1,3},{0,1,4},{0,2,3}}, {1,1,1,1,1}, {0,0,0,0});
    const auto found = g.discover({0});
    assert(found == exhaustive_discovery(g, {0}));
    assert(std::find(found.begin(), found.end(), Biclique{{0,1},{0,1,2}}) != found.end());
    assert(std::count(found.begin(), found.end(), Biclique{{0,1},{0,1,2}}) == 1);
    assert(std::find(found.begin(), found.end(), Biclique{{0,2},{0,3}}) != found.end());
    assert(g.discover({4}).empty()); // one relevant check cannot form a pair
}

static void assert_unique_physical_lift(const Graph& g) {
    assert(g.physical_variables() <= 8 && g.variable_count() <= 12);
    const int physical = g.physical_variables();
    const int auxiliary = g.variable_count() - physical;
    for (int mask = 0; mask < (1 << physical); ++mask) {
        Ids x(physical);
        for (int v = 0; v < physical; ++v) x[v] = (mask >> v) & 1;
        const Ids residual = g.residual_syndrome(x);
        const bool originally_valid = std::all_of(residual.begin(), residual.end(),
                                                  [](int bit){ return bit == 0; });
        int valid_lifts = 0;
        for (int aux = 0; aux < (1 << auxiliary); ++aux) {
            Ids z = x;
            for (int v = 0; v < auxiliary; ++v) z.push_back((aux >> v) & 1);
            bool valid = true;
            for (int c = 0; c < g.check_count(); ++c) {
                int parity = g.check(c).syndrome;
                for (int v : g.check(c).variables) parity ^= z[v];
                if (parity) { valid = false; break; }
            }
            valid_lifts += valid;
        }
        assert(valid_lifts == (originally_valid ? 1 : 0));
    }
}

static void test_transform_support_and_physical_solutions() {
    Graph g({{0,1,2},{0,1,2},{0,1,3}}, {0.2,-0.3,0.4,0.5}, {1,1,0});
    assert_unique_physical_lift(g);
    const auto first = g.factorize({{0,1},{0,1,2}});
    assert(first.first == 4 && first.second == 3);
    assert((g.physical_support(4) == Ids{0,1}));
    assert(g.variable(4).base_llr == 0 && g.check(3).syndrome == 0);
    assert((g.check(0).variables == Ids{2,4}));
    assert((g.check(3).variables == Ids{0,1,4}));
    assert_unique_physical_lift(g);
    assert(g.discover({0}) == exhaustive_discovery(g, {0}));
    const auto second = g.factorize({{2,4},{0,1}});
    assert(second.first == 5 && second.second == 4);
    assert((g.physical_support(5) == Ids{0,1,2}));
    assert_unique_physical_lift(g);
    assert((xor_support({0,1,2}, {0,2}) == Ids{1}));
    assert((g.variable(5).checks == Ids{0,1,4}));
    assert((g.check(4).variables == Ids{2,4,5}));
    for (const auto& b : g.discover({0,1,2,3})) exact_delta(g, b, {0.1,0.2,0.3,0.4});
    bool duplicate = false, missing = false;
    try { g.add_edge(5, 0); } catch (const std::invalid_argument&) { duplicate = true; }
    try { g.remove_edge(0, 0); } catch (const std::invalid_argument&) { missing = true; }
    assert(duplicate && missing);
    // A test-only added constraint creates a nested overlap that cancels
    // physical support under symmetric difference: {0,1} XOR {0,1,2}={2}.
    g.add_edge(5, 3);
    const auto third = g.factorize({{4,5},{3,4}});
    assert((g.physical_support(third.first) == Ids{2}));
}

static void test_exact_phi_and_local_delta() {
    Graph g({{0,1,2},{0,1,2},{0,1,3},{1,2,3},{2,3,4}},
            {1,1,1,1,1}, {0,0,0,0,0});
    const Reals omega{0.2,0.7,0.9,0.4,0.1};
    near(g.phi(omega), exhaustive_phi(g, omega));
    for (const auto& b : g.discover({0,1,2})) exact_delta(g, b, omega);
    const Biclique creation{{0,1,2},{0,1}};
    exact_delta(g, creation, omega);
    Graph trial = g;
    const auto [y, q] = trial.factorize(creation);
    assert((intersection(trial.check(q).variables, trial.check(2).variables) == Ids{0,1}));
    assert(y == 5); // defining check creates a new q--check-2 4-cycle
    for (const auto& b : trial.discover({0,1,2})) exact_delta(trial, b, omega);
    // Randomized small graphs compare every discovered candidate to full-copy oracle.
    std::uint32_t state = 1761;
    int positive = 0;
    for (int sample = 0; sample < 160; ++sample) {
        Rows rows(5);
        for (int c = 0; c < 5; ++c)
            for (int v = 0; v < 6; ++v) {
                state = state * 1664525u + 1013904223u;
                if ((state >> 28) < 9) rows[c].push_back(v);
            }
        Graph random(rows, Reals(6, 0.1), Ids(5, 0));
        const Reals weights{0.1,0.5,0.2,0.8,0.3,0.6};
        for (const Ids& u : {Ids{0}, Ids{1,3}, Ids{0,1,2,3,4,5}}) {
            const auto candidates = random.discover(u);
            assert(candidates == exhaustive_discovery(random, u));
            double oracle_best_delta = -1.0;
            Biclique oracle_adaptive;
            std::uint64_t oracle_best_cycles = 0;
            Biclique oracle_shen;
            for (const auto& b : candidates) {
                exact_delta(random, b, weights);
                const double delta = random.net_cycle_reduction(b, weights);
                assert(delta >= -1e-12);
                positive += delta > 1e-12;
                if (delta > oracle_best_delta ||
                    (delta == oracle_best_delta && b < oracle_adaptive)) {
                    oracle_best_delta = delta;
                    oracle_adaptive = b;
                }
                const std::uint64_t cycles =
                    (b.variables.size() * (b.variables.size() - 1) / 2) *
                    (b.checks.size() * (b.checks.size() - 1) / 2);
                if (cycles > oracle_best_cycles ||
                    (cycles == oracle_best_cycles && b < oracle_shen)) {
                    oracle_best_cycles = cycles;
                    oracle_shen = b;
                }
            }
            Graph adaptive = random;
            const auto selected_adaptive = adaptive.factorize_graph(weights, u, 1, "adaptive_cycle");
            assert(selected_adaptive.applied == (oracle_best_delta > 0 ? 1 : 0));
            if (selected_adaptive.applied)
                assert(selected_adaptive.chosen.front().biclique == oracle_adaptive);
            Graph shen = random;
            const auto selected_shen = shen.factorize_graph(weights, u, 1, "shen_cycle_count");
            assert(selected_shen.applied == (candidates.empty() ? 0 : 1));
            if (selected_shen.applied)
                assert(selected_shen.chosen.front().biclique == oracle_shen);
        }
    }
    assert(positive > 0);
    // Zero weights make every pairwise weighted cycle score zero, even when
    // topology changes. The admissible nonnegative weights cannot yield a
    // negative net score for a valid biclique (see final audit proof).
    Graph zero_graph({{0,1},{0,1}}, {0,0}, {0,0});
    const auto zero_candidate = zero_graph.discover({0}).front();
    exact_delta(zero_graph, zero_candidate, {0,0});
    assert(zero_graph.net_cycle_reduction(zero_candidate, {0,0}) == 0);
}

static void test_many_exhaustive_physical_lifts() {
    std::uint32_t state = 271828;
    for (int sample = 0; sample < 80; ++sample) {
        const int n = 3 + sample % 3;
        Rows rows(4);
        for (int a = 0; a < 4; ++a)
            for (int v = 0; v < n; ++v) {
                state = state * 1664525u + 1013904223u;
                if ((state >> 29) < 5) rows[a].push_back(v);
            }
        Ids syndrome(4);
        for (int a = 0; a < 4; ++a) syndrome[a] = (state >> a) & 1;
        Graph graph(rows, Reals(n, 0.2), syndrome);
        assert_unique_physical_lift(graph);
        for (int depth = 0; depth < 2; ++depth) {
            Ids suspicious;
            for (int v = 0; v < n; ++v) suspicious.push_back(v);
            const auto candidates = graph.discover(suspicious);
            assert(candidates == exhaustive_discovery(graph, suspicious));
            if (candidates.empty()) break;
            const auto [aux, defining_check] = graph.factorize(candidates.front());
            assert(graph.variable(aux).base_llr == 0);
            assert(graph.check(defining_check).syndrome == 0);
            assert_unique_physical_lift(graph);
        }
    }
}

static void test_policies_and_rediscovery() {
    const Reals four(4, 1.0);
    Graph a({{0,1},{0,1},{2,3},{2,3}}, four, {0,0,0,0});
    const auto before = a.edge_count();
    assert(a.factorize_graph(four, {0,2}, 0, "adaptive_cycle").applied == 0);
    assert(a.edge_count() == before);
    const auto first = a.factorize_graph(four, {0,2}, 1, "adaptive_cycle");
    assert(first.applied == 1 && (first.chosen[0].biclique.variables == Ids{0,1}));
    assert(first.chosen[0].net_cycle_reduction > 0);
    const auto second = a.factorize_graph(four, {0,2}, 3, "adaptive_cycle");
    assert(second.applied == 1 && (second.chosen[0].biclique.variables == Ids{2,3}));
    Graph stop({{0,1},{0,1}}, {1,1}, {0,0});
    assert(stop.factorize_graph({0,0}, {0}, 2, "adaptive_cycle").applied == 0);
    assert(stop.variable_count() == 2);
    assert(stop.factorize_graph({0,0}, {0}, 1, "shen_cycle_count").applied == 1);

    Graph shen({{0,1},{0,1},{2,3,4},{2,3,4},{2,3,4}}, Reals(5,1), {0,0,0,0,0});
    auto chosen = shen.factorize_graph(Reals(5,1), {0,2}, 1, "shen_cycle_count");
    assert(chosen.applied == 1 && (chosen.chosen[0].biclique.variables == Ids{2,3,4}));
    assert(chosen.chosen[0].internal_cycles == 9);

    Graph overlap({{0,1,2},{0,1,2},{0,1,2},{0,1,3},{0,1,3}},
                  Reals(4,1), {0,0,0,0,0});
    const auto stale = overlap.discover({0});
    const auto many = overlap.factorize_graph(Reals(4,1), {0}, 3, "shen_cycle_count");
    assert(many.applied >= 2 && (many.chosen.front().biclique.variables == Ids{0,1}));
    assert(many.chosen[1].biclique.variables[1] >= 4); // newly created y
    assert(std::find(stale.begin(), stale.end(), many.chosen[1].biclique) == stale.end());
    assert(many.scored_seeds_per_step.size() >= 2);
    assert_unique_physical_lift(overlap);
}

static void test_sparse_support_and_diagnostics() {
    constexpr int n = 20000;
    Graph g({{0,1},{0,1},{100,101},{100,101}}, Reals(n, 0.2), {0,0,0,0});
    for (int v = 0; v < n; ++v) assert(g.variable(v).auxiliary_support.empty());
    for (int v = 0; v < n; ++v) assert(g.variable(v).auxiliary_support.capacity() == 0);
    const auto candidate = g.discover({0}).front();
    const auto score = g.score_candidate(candidate, Reals(n, 0.1));
    assert(score.edges_before == 8 && score.edges_after == 9);
    assert(score.max_variable_degree_before == 2 && score.max_variable_degree_after == 3);
    assert(score.max_check_degree_before == 2 && score.max_check_degree_after == 3);
    const auto [y,q] = g.factorize(candidate);
    assert(y == n && q == 4 && (g.physical_support(y) == Ids{0,1}));
    assert(g.variable(y).auxiliary_support.size() == 2);
    assert(g.edge_count() == score.edges_after);
}

int main() {
    test_failure_weights();
    test_discovery_closure_dedup();
    test_transform_support_and_physical_solutions();
    test_exact_phi_and_local_delta();
    test_many_exhaustive_physical_lifts();
    test_policies_and_rediscovery();
    test_sparse_support_and_diagnostics();
    std::cout << "AF-BP graph core: 7 native test groups passed\n";
}
