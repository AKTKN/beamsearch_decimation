#include "decoder.hpp"
#include <cassert>
#include <cmath>
#include <iostream>
#include <stdexcept>

using namespace af_bp_core;

static void near(double actual, double expected) {
    if (std::abs(actual - expected) > 1e-10 * (1.0 + std::abs(expected)))
        throw std::runtime_error("AF-BP native handoff differs from reference formula");
}

static double parity_llr(const Reals& q, const Ids& members, double epsilon = 1e-12) {
    double product = 1.0;
    for (int v : members) product *= std::tanh(q[v] / 2.0);
    product = std::clamp(product, -1.0 + epsilon, 1.0 - epsilon);
    return 2.0 * std::atanh(product);
}

static DecoderSettings tiny() {
    DecoderSettings cfg;
    cfg.initial_iteration_budget = 0;
    cfg.transformed_iteration_budget = 5;
    cfg.graph_rounds = 1;
    cfg.n_fact = 1;
    return cfg;
}

static void original_h_valid(const Rows& h, const Ids& syndrome, const DecodeResult& result) {
    assert(result.valid && result.correction.size() > 0);
    for (std::size_t a = 0; a < h.size(); ++a) {
        int parity = 0;
        for (int v : h[a]) parity ^= result.correction[v];
        assert(parity == syndrome[a]);
    }
}

static void test_identity_initial_and_original_boundary() {
    assert(std::string(KIND) == "af_bp");
    assert(std::string(PROFILE) == "af_bp_v1");
    assert(std::string(NAME) == "af_bp_v1");
    assert(std::string(ALGORITHM_VERSION) == "AF-BP-1.0");
    DecoderSettings cfg;
    cfg.graph_rounds = 3;
    cfg.initial_iteration_budget = 3;
    Decoder decoder({{0,1}}, {{0},{1}}, {0.1,0.2}, cfg);
    const auto result = decoder.decode({1}, true);
    assert(result.valid && result.status == "SUCCESS");
    assert(result.graph_instances == 1 && result.factorizations == 0);
    assert(result.total_iterations == 1 && result.calls.size() == 1);
    assert(result.calls[0].variant == "parallel");
    assert((result.prediction == result.correction));
    original_h_valid({{0,1}}, {1}, result);

    cfg.graph_rounds = 1;
    cfg.initial_iteration_budget = 0;
    cfg.transformed_iteration_budget = 5;
    Decoder transformed({{0,1},{0,1}}, {{0},{1}}, {0.1,0.2}, cfg);
    const auto later = transformed.decode({1,1}, true);
    assert(later.valid && later.graph_instances == 2 && later.factorizations == 1);
    assert(later.total_iterations == 2);
    assert(later.calls[0].actual_iterations == 0 && later.calls[1].actual_iterations == 2);
    assert(later.transforms.size() == 1 && later.transforms[0].new_variable == 2);
    original_h_valid({{0,1},{0,1}}, {1,1}, later);
}

static void test_initial_parallel_variants_and_hard_budgets() {
    for (const std::string variant : {"parallel", "serial", "qdither"})
        for (bool initial_parallel : {true, false}) {
            auto cfg = tiny();
            cfg.bp_variant = variant;
            cfg.initial_parallel = initial_parallel;
            cfg.phase1_iterations = 1;
            cfg.num_chains = 3;
            cfg.chain_iterations = 2;
            cfg.transformed_iteration_budget = 4;
            Decoder decoder({{0,1},{0,1}}, {}, {0.1,0.2}, cfg);
            const auto result = decoder.decode({1,1}, true);
            assert(result.valid && result.graph_instances == 2);
            assert(result.calls[0].variant == (initial_parallel ? "parallel" : variant));
            assert(result.calls[1].variant == variant);
            assert(result.calls[0].budget == 0 && result.calls[0].actual_iterations == 0);
            assert(result.calls[1].budget == 4 && result.calls[1].actual_iterations <= 4);
            assert(result.total_iterations == result.calls[0].actual_iterations +
                                               result.calls[1].actual_iterations);
            assert(result.total_iterations == (variant == "qdither" ? 3 : 2));
            if (variant == "qdither") {
                assert(result.calls[1].phase1_iterations == 1);
                assert((result.calls[1].chain_iterations == Ids{2}));
            }
        }

    auto capped = tiny();
    capped.initial_iteration_budget = 1;
    capped.transformed_iteration_budget = 1;
    capped.bp_variant = "qdither";
    capped.initial_parallel = false;
    capped.phase1_iterations = 3;
    capped.num_chains = 4;
    capped.chain_iterations = 3;
    Decoder decoder({{0,1},{0,1}}, {}, {0.1,0.2}, capped);
    const auto result = decoder.decode({1,1}, true);
    assert(result.graph_instances == 2 && result.total_iterations == 2);
    assert(result.calls[0].actual_iterations == 1 && result.calls[1].actual_iterations == 1);
    assert(result.calls[0].budget_truncated && result.calls[1].budget_truncated);
    assert(result.calls[0].phase1_iterations == 1);
    assert(result.calls[1].phase1_iterations == 1);
}

static void test_failure_stops_and_reference_handoff_mode() {
    auto cfg = tiny();
    Decoder no_candidate({{0,1},{1,2}}, {}, {0.1,0.2,0.3}, cfg);
    auto result = no_candidate.decode({1,0}, true);
    assert(!result.valid && result.status == "NO_CANDIDATE" && result.factorizations == 0);
    assert(result.correction.empty() && result.prediction.empty());

    cfg.n_fact = 0;
    Decoder no_budget({{0,1},{0,1}}, {}, {0.1,0.2}, cfg);
    assert(no_budget.decode({1,1}).status == "NO_FACTORIZATION_BUDGET");

    cfg.n_fact = 1;
    cfg.failure.selection = "threshold";
    cfg.failure.threshold = 0.0;
    cfg.failure.distance_decay = 0.0;
    Decoder zero_score({{0,1},{0,1}}, {}, {0.1,0.2}, cfg);
    result = zero_score.decode({1,1}, true);
    assert(!result.valid && result.status == "NONPOSITIVE_SCORE");
    assert(result.graph_instances == 1 && result.factorizations == 0);

    cfg = tiny();
    cfg.bp_variant = "qdither";
    cfg.qdither_handoff = "paper";
    bool rejected = false;
    try { Decoder forbidden({{0,1},{0,1}}, {}, {0.1,0.2}, cfg); }
    catch (const std::invalid_argument&) { rejected = true; }
    assert(rejected);
    cfg.graph_rounds = 0;
    cfg.initial_parallel = false;
    cfg.initial_iteration_budget = 4;
    Decoder paper_only({{0,1}}, {}, {0.1,0.2}, cfg);
    assert(paper_only.decode({1}).valid);
}

static void test_nested_handoff_and_multiple_graph_rounds() {
    const Rows h{{0,1,2},{0,1,2},{0,1,2},{0,1,3},{0,1,3}};
    auto cfg = tiny();
    cfg.factorization_policy = "shen_cycle_count";
    cfg.n_fact = 2;
    cfg.transformed_iteration_budget = 0;
    Decoder decoder(h, {{0},{1},{2},{3}}, {0.1,0.2,0.15,0.2}, cfg);
    const auto result = decoder.decode({1,1,1,1,1}, true);
    assert(!result.valid && result.status == "GRAPH_ROUNDS_EXHAUSTED");
    assert(result.total_iterations == 0 && result.graph_instances == 2);
    assert(result.factorizations == 2 && result.transforms.size() == 2);
    assert(result.transforms[0].new_variable == 4);
    assert(result.transforms[1].new_variable == 5);
    assert(result.transforms[1].biclique.variables[1] == 4);
    const Reals parent = result.calls[0].final_llrs;
    near(result.calls[1].q_init[4], parity_llr(parent, result.transforms[0].biclique.variables));
    Reals intermediate = parent;
    intermediate.push_back(result.calls[1].q_init[4]);
    near(result.calls[1].q_init[5], parity_llr(intermediate, result.transforms[1].biclique.variables));
    for (int v = 0; v < 4; ++v) near(result.calls[1].q_init[v], parent[v]);
    assert(result.calls[1].q_init.size() == 6);

    cfg.n_fact = 1;
    cfg.graph_rounds = 3;
    Decoder rounds(h, {}, {0.1,0.2,0.15,0.2}, cfg);
    const auto many = rounds.decode({1,1,1,1,1}, true);
    assert(!many.valid && many.status == "GRAPH_ROUNDS_EXHAUSTED");
    assert(many.graph_instances == 4 && many.factorizations == 3);
    assert(many.calls.size() == 4 && many.transforms.size() == 3);
    for (int i = 1; i < 4; ++i) {
        assert(many.calls[i].q_init.size() == many.calls[i - 1].final_llrs.size() + 1);
        for (std::size_t v = 0; v < many.calls[i - 1].final_llrs.size(); ++v)
            near(many.calls[i].q_init[v], many.calls[i - 1].final_llrs[v]);
    }

    // Contradictory physical checks keep all four graph instances active.
    // Each instance has a one-iteration budget and spends it exactly once.
    cfg.initial_iteration_budget = 1;
    cfg.transformed_iteration_budget = 1;
    Decoder counted(h, {}, {0.1,0.2,0.15,0.2}, cfg);
    const auto failure = counted.decode({1,1,1,1,0}, true);
    assert(!failure.valid && failure.status == "GRAPH_ROUNDS_EXHAUSTED");
    assert(failure.graph_instances == 4 && failure.factorizations == 3);
    assert(failure.total_iterations == 4 && failure.calls.size() == 4);
    for (const auto& call : failure.calls)
        assert(call.budget == 1 && call.actual_iterations == 1);
}

static void test_reset_seeds_and_original_validation() {
    auto cfg = tiny();
    cfg.bp_variant = "serial";
    cfg.initial_parallel = false;
    cfg.serial_order = "random_per_iteration";
    cfg.initial_iteration_budget = 2;
    cfg.seed = 42;
    cfg.seed_policy = "syndrome_derived";
    Decoder serial({{0,1},{0,1}}, {{0},{1}}, {0.1,0.2}, cfg);
    const auto first = serial.decode({1,1}, true);
    const auto other = serial.decode({0,0}, true);
    const auto replay = serial.decode({1,1}, true);
    assert(other.valid && other.total_iterations == 0);
    assert(first.valid == replay.valid && first.total_iterations == replay.total_iterations);
    assert(first.last_physical_hard == replay.last_physical_hard);
    assert(first.calls.size() == replay.calls.size());
    for (std::size_t i = 0; i < first.calls.size(); ++i) {
        assert(first.calls[i].seed == replay.calls[i].seed);
        assert(first.calls[i].final_llrs == replay.calls[i].final_llrs);
    }
    assert(first.calls[0].seed != first.calls[1].seed);
    cfg.seed_policy = "fixed";
    cfg.initial_iteration_budget = 0;
    Decoder fixed({{0,1},{0,1}}, {}, {0.1,0.2}, cfg);
    const auto fixed_result = fixed.decode({1,1}, true);
    assert(fixed_result.calls.size() == 2);
    assert(fixed_result.calls[0].seed == 42 && fixed_result.calls[1].seed == 42);

    cfg.bp_variant = "qdither";
    cfg.initial_parallel = false;
    cfg.initial_iteration_budget = 0;
    cfg.phase1_iterations = 1;
    cfg.num_chains = 3;
    cfg.chain_iterations = 2;
    cfg.seed_policy = "syndrome_derived";
    Decoder dither({{0,1},{0,1}}, {}, {0.1,0.2}, cfg);
    const auto d1 = dither.decode({1,1}, true);
    const auto d2 = dither.decode({1,1}, true);
    assert(d1.valid && d2.valid && d1.total_iterations == d2.total_iterations);
    assert(d1.correction == d2.correction);
    assert(d1.calls[1].chain_iterations == d2.calls[1].chain_iterations);

    for (const Ids& syndrome : {Ids{0,0}, Ids{1,1}, Ids{0,1}, Ids{1,0}}) {
        const auto result = dither.decode(syndrome);
        if (result.valid) original_h_valid({{0,1},{0,1}}, syndrome, result);
        else assert(result.correction.empty() && result.prediction.empty());
    }
}

static void test_qdither_configuration_matches_direct_native_engine() {
    DecoderSettings cfg;
    cfg.initial_parallel = false;
    cfg.initial_iteration_budget = 4;
    cfg.graph_rounds = 0;
    cfg.bp_variant = "qdither";
    cfg.qdither_handoff = "paper";
    cfg.phase1_iterations = 1;
    cfg.num_chains = 2;
    cfg.chain_iterations = 3;
    cfg.alpha = 0.4;
    cfg.beta = 0.7;
    cfg.rho = 0.8;
    cfg.seed = 9;
    cfg.seed_policy = "fixed";
    Decoder service({{0,1},{0,1}}, {}, {0.1,0.2}, cfg);
    const auto result = service.decode({0,1}, true); // inconsistent syndrome
    assert(!result.valid && result.status == "GRAPH_ROUNDS_EXHAUSTED");
    assert(result.total_iterations == 4 && result.calls.size() == 1);

    ldpc::af_bp::Settings native;
    native.variant = "qdither";
    native.max_iterations = 4;
    native.max_total_iterations = 4;
    native.phase1_iterations = cfg.phase1_iterations;
    native.num_chains = cfg.num_chains;
    native.chain_iterations = cfg.chain_iterations;
    native.alpha = cfg.alpha;
    native.beta = cfg.beta;
    native.rho = cfg.rho;
    native.seed = cfg.seed;
    native.qdither_handoff = "paper";
    ldpc::af_bp::Decoder direct({{0,1},{0,1}},
        {std::log(9.0), std::log(4.0)}, native);
    const auto expected = direct.decode({0,1});
    assert(result.total_iterations == expected.total_iterations);
    assert(result.calls[0].phase1_iterations == expected.phase1_iterations_executed);
    assert(result.calls[0].chain_iterations == expected.chain_iterations_executed);
    for (std::size_t v = 0; v < expected.final_llrs.size(); ++v)
        near(result.calls[0].final_llrs[v], expected.final_llrs[v]);
}

int main() {
    test_identity_initial_and_original_boundary();
    test_initial_parallel_variants_and_hard_budgets();
    test_failure_stops_and_reference_handoff_mode();
    test_nested_handoff_and_multiple_graph_rounds();
    test_reset_seeds_and_original_validation();
    test_qdither_configuration_matches_direct_native_engine();
    std::cout << "AF-BP decoder: 6 native integration groups passed\n";
}
