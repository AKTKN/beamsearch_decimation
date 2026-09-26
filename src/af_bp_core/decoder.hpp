#pragma once

// AF-BP-1.0 native state machine. It depends only on the standalone graph core
// and the opt-in ldpc.af_bp C++ Min-Sum engine, not on simulator data types.
#include "graph.hpp"
#include "af_bp.hpp"
#include <cstdint>
#include <optional>
#include <string>
#include <utility>

namespace af_bp_core {

inline constexpr const char* KIND = "af_bp";
inline constexpr const char* PROFILE = "af_bp_v1";
inline constexpr const char* NAME = "af_bp_v1";
inline constexpr const char* ALGORITHM_VERSION = "AF-BP-1.0";

struct DecoderSettings {
    bool initial_parallel = true;
    int initial_iteration_budget = 50;
    int transformed_iteration_budget = 50;
    std::string bp_variant = "parallel";
    std::string serial_order = "random_per_iteration";
    double scaling_factor = 1.0;
    int history_window = 8;
    int graph_rounds = 4;
    int n_fact = 1;
    std::string factorization_policy = "adaptive_cycle";
    FailureSettings failure;
    double atanh_epsilon = 1e-12;
    int phase1_iterations = 30;
    int num_chains = 0;
    int chain_iterations = 20;
    double alpha = 0.0;
    double beta = 1.0;
    double rho = 0.0;
    std::uint64_t seed = 0;
    std::string seed_policy = "syndrome_derived";
    std::string qdither_handoff = "graph_warm";
};

struct BpCallRecord {
    int graph_index = 0;
    std::string variant;
    int budget = 0;
    int actual_iterations = 0;
    int variable_count = 0;
    int check_count = 0;
    bool native_success = false;
    bool physical_valid = false;
    bool budget_truncated = false;
    int phase1_iterations = 0;
    Ids chain_iterations;
    std::uint64_t seed = 0;
    Reals q_init;
    Reals final_llrs;
};

struct TransformRecord {
    Biclique biclique;
    int new_variable = -1;
    double inherited_llr = 0.0;
};

struct DecodeResult {
    bool valid = false;
    std::optional<bool> initial_bp_converged;
    std::optional<bool> first_transform_converged;
    Ids correction;       // empty unless valid; owned physical length n0 on success
    Ids prediction;       // A*correction mod 2; empty on failure
    Ids last_physical_hard;
    std::int64_t total_iterations = 0;
    int graph_instances = 0;
    int factorizations = 0;
    std::string status = "DECLARED_FAILURE";
    std::vector<BpCallRecord> calls;       // populated only with diagnostics=true
    std::vector<TransformRecord> transforms; // populated only with diagnostics=true
};

class Decoder {
    Rows h0_;
    Rows observables_;
    Reals probabilities_;
    Reals base_llrs_;
    DecoderSettings cfg_;
    int n0_;

    static std::uint64_t mix64(std::uint64_t x) {
        x += 0x9e3779b97f4a7c15ULL;
        x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
        x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
        return x ^ (x >> 31);
    }
    std::uint64_t call_seed(const Ids& syndrome, int graph_index) const {
        if (cfg_.seed_policy == "fixed") return cfg_.seed;
        std::uint64_t value = mix64(cfg_.seed ^ static_cast<std::uint64_t>(graph_index));
        for (int bit : syndrome) value = mix64(value ^ static_cast<std::uint64_t>(bit + 1));
        return value;
    }
    static bool original_valid(const Rows& h0, const Ids& syndrome, const Ids& physical) {
        for (std::size_t a = 0; a < h0.size(); ++a) {
            int parity = 0;
            for (int v : h0[a]) parity ^= physical[v];
            if (parity != syndrome[a]) return false;
        }
        return true;
    }
    Ids predict(const Ids& correction) const {
        Ids result(observables_.size());
        for (std::size_t a = 0; a < observables_.size(); ++a)
            for (int v : observables_[a]) result[a] ^= correction[v];
        return result;
    }
    double parity_handoff(const Biclique& b, const Reals& q_init) const {
        double product = 1.0;
        for (int v : b.variables) {
            if (v < 0 || static_cast<std::size_t>(v) >= q_init.size())
                throw std::logic_error("factorization references uninitialized variable");
            product *= std::tanh(q_init[v] / 2.0);
        }
        const double limit = 1.0 - cfg_.atanh_epsilon;
        return 2.0 * std::atanh(std::clamp(product, -limit, limit));
    }
    ldpc::af_bp::Result run_bp(const Graph& graph, const Ids& syndrome0,
                               const Reals& q_init, int graph_index,
                               ldpc::af_bp::Settings& settings_used) const {
        Rows rows;
        Ids syndrome;
        Reals base;
        rows.reserve(graph.check_count());
        syndrome.reserve(graph.check_count());
        base.reserve(graph.variable_count());
        for (int c = 0; c < graph.check_count(); ++c) {
            rows.push_back(graph.check(c).variables);
            syndrome.push_back(graph.check(c).syndrome);
        }
        for (int v = 0; v < graph.variable_count(); ++v)
            base.push_back(graph.variable(v).base_llr);
        settings_used.variant = graph_index == 0 && cfg_.initial_parallel ? "parallel" : cfg_.bp_variant;
        settings_used.serial_order = cfg_.serial_order;
        settings_used.scaling_factor = cfg_.scaling_factor;
        settings_used.history_window = cfg_.history_window;
        settings_used.seed = call_seed(syndrome0, graph_index);
        settings_used.max_iterations = graph_index == 0 ? cfg_.initial_iteration_budget
                                                         : cfg_.transformed_iteration_budget;
        settings_used.max_total_iterations = settings_used.max_iterations;
        settings_used.phase1_iterations = cfg_.phase1_iterations;
        settings_used.num_chains = cfg_.num_chains;
        settings_used.chain_iterations = cfg_.chain_iterations;
        settings_used.alpha = cfg_.alpha;
        settings_used.beta = cfg_.beta;
        settings_used.rho = cfg_.rho;
        settings_used.qdither_handoff = cfg_.qdither_handoff;
        ldpc::af_bp::Decoder engine(std::move(rows), std::move(base), settings_used);
        const Reals empty_initialization;
        const Reals& initialization =
            settings_used.variant == "qdither" && cfg_.qdither_handoff == "paper"
                ? empty_initialization : q_init;
        return engine.decode(syndrome, initialization);
    }

public:
    // All arrays are copied. H0/A rows must have sorted unique column IDs.
    // Probabilities are physical P(error=1), strictly between zero and one.
    Decoder(Rows h0, Rows observables, Reals probabilities, DecoderSettings cfg)
        : h0_(std::move(h0)), observables_(std::move(observables)),
          probabilities_(std::move(probabilities)), cfg_(std::move(cfg)),
          n0_(static_cast<int>(probabilities_.size())) {
        if (cfg_.initial_iteration_budget < 0 || cfg_.transformed_iteration_budget < 0 ||
            cfg_.graph_rounds < 0 || cfg_.n_fact < 0 || cfg_.history_window < 1 ||
            cfg_.phase1_iterations < 0 || cfg_.num_chains < 0 || cfg_.chain_iterations < 0 ||
            !(cfg_.scaling_factor > 0 && cfg_.scaling_factor <= 1) ||
            !(cfg_.atanh_epsilon > 0 && cfg_.atanh_epsilon < 1) ||
            !(cfg_.alpha >= 0 && cfg_.alpha <= cfg_.beta && cfg_.beta <= 1) ||
            !(cfg_.rho >= 0 && cfg_.rho <= 1) ||
            !std::isfinite(cfg_.scaling_factor) || !std::isfinite(cfg_.atanh_epsilon) ||
            !std::isfinite(cfg_.alpha) || !std::isfinite(cfg_.beta) || !std::isfinite(cfg_.rho) ||
            (cfg_.bp_variant != "parallel" && cfg_.bp_variant != "serial" && cfg_.bp_variant != "qdither") ||
            (cfg_.serial_order != "natural" && cfg_.serial_order != "random_per_iteration") ||
            (cfg_.seed_policy != "fixed" && cfg_.seed_policy != "syndrome_derived") ||
            (cfg_.qdither_handoff != "paper" && cfg_.qdither_handoff != "graph_warm") ||
            (cfg_.factorization_policy != "adaptive_cycle" &&
             cfg_.factorization_policy != "shen_cycle_count") ||
            cfg_.failure.residual_radius < 0 || cfg_.failure.top_k < 0 ||
            !std::isfinite(cfg_.failure.distance_decay) ||
            cfg_.failure.distance_decay < 0 || cfg_.failure.distance_decay > 1 ||
            !std::isfinite(cfg_.failure.uncertainty_weight) ||
            !std::isfinite(cfg_.failure.oscillation_weight) ||
            cfg_.failure.uncertainty_weight < 0 || cfg_.failure.oscillation_weight < 0 ||
            !std::isfinite(cfg_.failure.uncertainty_weight + cfg_.failure.oscillation_weight) ||
            cfg_.failure.uncertainty_weight + cfg_.failure.oscillation_weight <= 0 ||
            !std::isfinite(cfg_.failure.threshold) || cfg_.failure.threshold < 0 ||
            (cfg_.failure.selection != "top_k" && cfg_.failure.selection != "threshold"))
            throw std::invalid_argument("invalid AF-BP decoder settings");
        if (cfg_.bp_variant == "qdither" && cfg_.graph_rounds > 0 && cfg_.n_fact > 0 &&
            cfg_.qdither_handoff != "graph_warm")
            throw std::invalid_argument("AF-BP qDither graph relay requires graph_warm handoff");
        for (double p : probabilities_) {
            if (!std::isfinite(p) || p <= 0.0 || p >= 1.0)
                throw std::invalid_argument("physical probabilities must be strictly in (0,1)");
            base_llrs_.push_back(std::log1p(-p) - std::log(p));
        }
        for (const Rows* matrix : {&h0_, &observables_})
            for (const auto& row : *matrix) {
                if (!sorted_unique(row)) throw std::invalid_argument("matrix rows must be sorted unique");
                for (int v : row) require_id(v, n0_, "matrix column");
            }
    }

    DecodeResult decode(const Ids& syndrome, bool diagnostics = false) const {
        if (syndrome.size() != h0_.size() ||
            std::any_of(syndrome.begin(), syndrome.end(), [](int bit){ return bit != 0 && bit != 1; }))
            throw std::invalid_argument("syndrome must be binary with one bit per H0 check");
        Graph graph(h0_, base_llrs_, syndrome); // shot-local mutable state
        Reals q_init = base_llrs_;
        DecodeResult result;
        for (int graph_index = 0; graph_index <= cfg_.graph_rounds; ++graph_index) {
            ldpc::af_bp::Settings used;
            const Reals call_handoff = diagnostics ? q_init : Reals{};
            const auto bp = run_bp(graph, syndrome, q_init, graph_index, used);
            result.total_iterations += bp.total_iterations;
            result.graph_instances = graph_index + 1;
            if (bp.correction.size() != static_cast<std::size_t>(graph.variable_count()) ||
                bp.final_llrs.size() != static_cast<std::size_t>(graph.variable_count()))
                throw std::logic_error("BP engine returned inconsistent graph-sized arrays");
            result.last_physical_hard.assign(bp.correction.begin(), bp.correction.begin() + n0_);
            const bool physical_valid = original_valid(h0_, syndrome, result.last_physical_hard);
            if (graph_index == 0) result.initial_bp_converged = physical_valid;
            if (graph_index == 1) result.first_transform_converged = physical_valid;
            if (diagnostics) result.calls.push_back(BpCallRecord{
                graph_index, used.variant, used.max_total_iterations, bp.total_iterations,
                graph.variable_count(), graph.check_count(), bp.success, physical_valid,
                bp.budget_truncated, bp.phase1_iterations_executed,
                bp.chain_iterations_executed, used.seed, call_handoff, bp.final_llrs});
            if (physical_valid) {
                result.valid = true;
                result.correction = result.last_physical_hard;
                result.prediction = predict(result.correction);
                result.status = "SUCCESS";
                return result;
            }
            if (graph_index == cfg_.graph_rounds) {
                result.status = "GRAPH_ROUNDS_EXHAUSTED";
                break;
            }
            std::vector<Reals> physical_history;
            if (bp.trailing_history.empty())
                physical_history.emplace_back(bp.final_llrs.begin(), bp.final_llrs.begin() + n0_);
            else for (const auto& row : bp.trailing_history)
                physical_history.emplace_back(row.begin(), row.begin() + n0_);
            const auto failure = graph.failure_weights(result.last_physical_hard,
                                                       physical_history, cfg_.failure);
            if (failure.suspicious.empty()) { result.status = "EMPTY_U"; break; }
            if (cfg_.n_fact == 0) { result.status = "NO_FACTORIZATION_BUDGET"; break; }
            q_init = bp.final_llrs;
            const auto changed = graph.factorize_graph(
                failure.omega, failure.suspicious, cfg_.n_fact, cfg_.factorization_policy,
                [&](const Biclique& b, int y) {
                    if (y != static_cast<int>(q_init.size()))
                        throw std::logic_error("new auxiliary ID is not next handoff slot");
                    const double inherited = parity_handoff(b, q_init);
                    q_init.push_back(inherited); // immediate, before next transform
                    if (diagnostics) result.transforms.push_back({b, y, inherited});
                });
            result.factorizations += changed.applied;
            if (!changed.applied) {
                const bool had_candidate = !changed.scored_seeds_per_step.empty() &&
                                           changed.scored_seeds_per_step.front() > 0;
                result.status = had_candidate ? "NONPOSITIVE_SCORE" : "NO_CANDIDATE";
                break;
            }
        }
        return result;
    }
};
} // namespace af_bp_core
