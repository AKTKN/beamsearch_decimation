#pragma once

// Standalone AF-BP graph factorization core. No simulator or BP dependency.
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <iterator>
#include <limits>
#include <numeric>
#include <queue>
#include <set>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace af_bp_core {
using Ids = std::vector<int>;
using Rows = std::vector<Ids>;
using Reals = std::vector<double>;

inline void require_id(int id, std::size_t size, const char* label) {
    if (id < 0 || static_cast<std::size_t>(id) >= size)
        throw std::out_of_range(label);
}

inline bool sorted_unique(const Ids& ids) {
    return std::adjacent_find(ids.begin(), ids.end(), std::greater_equal<int>{}) == ids.end();
}

inline Ids intersection(const Ids& a, const Ids& b) {
    Ids result;
    std::set_intersection(a.begin(), a.end(), b.begin(), b.end(),
                          std::back_inserter(result));
    return result;
}

inline Ids xor_support(const Ids& a, const Ids& b) {
    Ids result;
    std::set_symmetric_difference(a.begin(), a.end(), b.begin(), b.end(),
                                  std::back_inserter(result));
    return result;
}

struct Variable {
    Ids checks;                 // sorted current check IDs
    Ids auxiliary_support;      // only allocated for auxiliary variables
    double base_llr = 0.0;
    bool physical = false;
};

struct Check {
    Ids variables;              // sorted current variable IDs
    int syndrome = 0;
    bool physical = false;
};

struct Biclique {
    Ids variables;
    Ids checks;
    bool operator<(const Biclique& other) const {
        if (variables != other.variables) return variables < other.variables;
        return checks < other.checks;
    }
    bool operator==(const Biclique& other) const {
        return variables == other.variables && checks == other.checks;
    }
};

struct FailureSettings {
    int residual_radius = 2;
    double distance_decay = 0.5;
    double uncertainty_weight = 1.0;
    double oscillation_weight = 1.0;
    std::string selection = "top_k";
    int top_k = 32;
    double threshold = 0.5;
};

struct FailureWeights {
    Ids residual_syndrome;
    Ids distance;
    Reals uncertainty;
    Reals oscillation;
    Reals omega;
    Ids suspicious;
};

struct CandidateScore {
    Biclique biclique;
    double net_cycle_reduction = 0.0;
    std::uint64_t internal_cycles = 0;
    std::size_t edges_before = 0, edges_after = 0;
    int max_variable_degree_before = 0, max_variable_degree_after = 0;
    int max_check_degree_before = 0, max_check_degree_after = 0;
    int auxiliaries_before = 0, auxiliaries_after = 0;
};

struct FactorizeResult {
    int applied = 0;
    std::vector<CandidateScore> chosen;
    std::vector<std::size_t> scored_seeds_per_step;
};

class Graph {
    std::vector<Variable> variables_;
    std::vector<Check> checks_;
    Rows original_rows_;
    Ids original_syndrome_;
    Rows original_variable_checks_;
    int n_phys_ = 0;
    int m_phys_ = 0;
    std::size_t edge_count_ = 0;

    static void insert(Ids& ids, int id) {
        auto it = std::lower_bound(ids.begin(), ids.end(), id);
        if (it != ids.end() && *it == id) throw std::invalid_argument("duplicate edge");
        ids.insert(it, id);
    }
    static void erase(Ids& ids, int id) {
        auto it = std::lower_bound(ids.begin(), ids.end(), id);
        if (it == ids.end() || *it != id) throw std::invalid_argument("missing edge");
        ids.erase(it);
    }
    static double pair_products(const Ids& ids, const Reals& weights) {
        double result = 0.0;
        for (std::size_t i = 0; i < ids.size(); ++i)
            for (std::size_t j = i + 1; j < ids.size(); ++j)
                result += weights[ids[i]] * weights[ids[j]];
        return result;
    }
    static double sum_weights(const Ids& ids, const Reals& weights) {
        double result = 0.0;
        for (int id : ids) result += weights[id];
        return result;
    }
    void validate_biclique(const Biclique& b) const {
        if (b.variables.size() < 2 || b.checks.size() < 2 ||
            !sorted_unique(b.variables) || !sorted_unique(b.checks))
            throw std::invalid_argument("biclique IDs must be sorted unique and have sizes >=2");
        for (int v : b.variables) require_id(v, variables_.size(), "biclique variable");
        for (int c : b.checks) {
            require_id(c, checks_.size(), "biclique check");
            if (!std::includes(checks_[c].variables.begin(), checks_[c].variables.end(),
                               b.variables.begin(), b.variables.end()))
                throw std::invalid_argument("biclique edge missing in current graph");
        }
    }
    Reals extended_weights(const Reals& omega) const {
        if (omega.size() != static_cast<std::size_t>(n_phys_))
            throw std::invalid_argument("omega must have n_phys entries");
        for (double x : omega)
            if (!std::isfinite(x) || x < 0.0) throw std::invalid_argument("omega must be finite nonnegative");
        Reals weights(variables_.size());
        for (int v = 0; v < static_cast<int>(variables_.size()); ++v) {
            if (variables_[v].physical) weights[v] = omega[v];
            else for (int physical : variables_[v].auxiliary_support)
                weights[v] = std::max(weights[v], omega[physical]);
        }
        return weights;
    }
    double new_aux_weight(const Biclique& b, const Reals& omega) const {
        Ids support;
        for (int v : b.variables) support = xor_support(support, physical_support(v));
        double result = 0.0;
        for (int j : support) result = std::max(result, omega[j]);
        return result;
    }

    double net_delta_with_weights(const Biclique& b, const Reals& physical_omega,
                                  const Reals& weights) const {
        const double new_weight = new_aux_weight(b, physical_omega);
        const double sum_s = sum_weights(b.variables, weights);
        const double pair_s = pair_products(b.variables, weights);
        double delta = 0.0;
        for (std::size_t i = 0; i < b.checks.size(); ++i)
            for (std::size_t j = i + 1; j < b.checks.size(); ++j) {
                const Ids shared = intersection(checks_[b.checks[i]].variables,
                                                checks_[b.checks[j]].variables);
                Ids outside;
                std::set_difference(shared.begin(), shared.end(), b.variables.begin(),
                                    b.variables.end(), std::back_inserter(outside));
                delta += pair_s + (sum_s - new_weight) * sum_weights(outside, weights);
            }
        for (int d = 0; d < check_count(); ++d)
            if (!std::binary_search(b.checks.begin(), b.checks.end(), d)) {
                const Ids a = intersection(b.variables, checks_[d].variables);
                const double pair_a = pair_products(a, weights);
                const double sum_a = sum_weights(a, weights);
                for (int c : b.checks) {
                    const Ids shared = intersection(checks_[c].variables, checks_[d].variables);
                    Ids outside;
                    std::set_difference(shared.begin(), shared.end(), b.variables.begin(),
                                        b.variables.end(), std::back_inserter(outside));
                    delta += pair_a + sum_a * sum_weights(outside, weights);
                }
                // New defining check q shares A with d, creating these cycles.
                delta -= pair_a;
            }
        return delta;
    }

    template <class Visitor>
    void for_each_pair_seed(const Ids& suspicious, Visitor&& visit) const {
        Ids active = active_variables(suspicious);
        std::vector<char> active_flag(variables_.size()), relevant_flag(checks_.size());
        for (int v : active) {
            active_flag[v] = 1;
            for (int c : variables_[v].checks) relevant_flag[c] = 1;
        }
        // Only check pairs sharing an actual variable are accumulated. A pair
        // may yield the same closed biclique as another pair; production scores
        // such seeds without retaining K variable/check lists in memory.
        std::set<std::pair<int, int>> seeds;
        for (const auto& variable : variables_) {
            Ids related;
            for (int c : variable.checks) if (relevant_flag[c]) related.push_back(c);
            for (std::size_t i = 0; i < related.size(); ++i)
                for (std::size_t j = i + 1; j < related.size(); ++j)
                    seeds.emplace(related[i], related[j]);
        }
        for (const auto& [a, b] : seeds) {
            Ids shared = intersection(checks_[a].variables, checks_[b].variables);
            if (shared.size() < 2 ||
                std::none_of(shared.begin(), shared.end(), [&](int v){ return active_flag[v]; })) continue;
            Ids closure;
            for (int c : variables_[shared.front()].checks)
                if (relevant_flag[c] &&
                    std::includes(checks_[c].variables.begin(), checks_[c].variables.end(),
                                  shared.begin(), shared.end())) closure.push_back(c);
            visit(Biclique{std::move(shared), std::move(closure)});
        }
    }

public:
    // rows: sorted unique physical column IDs; syndrome: binary physical checks.
    // Graph owns all input copies and exposes const adjacency views.
    Graph(Rows rows, Reals base_llrs, Ids syndrome)
        : original_rows_(std::move(rows)), original_syndrome_(std::move(syndrome)),
          n_phys_(static_cast<int>(base_llrs.size())),
          m_phys_(static_cast<int>(original_rows_.size())) {
        if (original_syndrome_.size() != original_rows_.size())
            throw std::invalid_argument("syndrome length differs from physical checks");
        original_variable_checks_.resize(n_phys_);
        variables_.reserve(n_phys_);
        for (double llr : base_llrs) {
            if (!std::isfinite(llr)) throw std::invalid_argument("base LLR must be finite");
            variables_.push_back(Variable{{}, {}, llr, true});
        }
        for (int a = 0; a < m_phys_; ++a) {
            if (original_syndrome_[a] != 0 && original_syndrome_[a] != 1)
                throw std::invalid_argument("syndrome must be binary");
            const auto& row = original_rows_[a];
            if (!sorted_unique(row)) throw std::invalid_argument("physical rows must be sorted unique");
            checks_.push_back(Check{{}, original_syndrome_[a], true});
            for (int v : row) {
                require_id(v, variables_.size(), "physical column");
                add_edge(v, a);
                original_variable_checks_[v].push_back(a);
            }
        }
    }

    int physical_variables() const { return n_phys_; }
    int physical_checks() const { return m_phys_; }
    int variable_count() const { return static_cast<int>(variables_.size()); }
    int check_count() const { return static_cast<int>(checks_.size()); }
    std::size_t edge_count() const { return edge_count_; }
    const Variable& variable(int v) const { require_id(v, variables_.size(), "variable"); return variables_[v]; }
    const Check& check(int c) const { require_id(c, checks_.size(), "check"); return checks_[c]; }
    const Rows& original_rows() const { return original_rows_; }
    const Ids& original_syndrome() const { return original_syndrome_; }

    Ids physical_support(int v) const {
        require_id(v, variables_.size(), "variable");
        return variables_[v].physical ? Ids{v} : variables_[v].auxiliary_support;
    }

    void add_edge(int v, int c) {
        require_id(v, variables_.size(), "variable"); require_id(c, checks_.size(), "check");
        if (std::binary_search(variables_[v].checks.begin(), variables_[v].checks.end(), c))
            throw std::invalid_argument("duplicate edge");
        insert(variables_[v].checks, c);
        insert(checks_[c].variables, v);
        ++edge_count_;
    }
    void remove_edge(int v, int c) {
        require_id(v, variables_.size(), "variable"); require_id(c, checks_.size(), "check");
        if (!std::binary_search(variables_[v].checks.begin(), variables_[v].checks.end(), c))
            throw std::invalid_argument("missing edge");
        erase(variables_[v].checks, c);
        erase(checks_[c].variables, v);
        --edge_count_;
    }

    // The immutable original basis is always used, even after nested transforms.
    Ids residual_syndrome(const Ids& physical_hard) const {
        if (physical_hard.size() != static_cast<std::size_t>(n_phys_))
            throw std::invalid_argument("physical hard decision length differs from n_phys");
        for (int bit : physical_hard)
            if (bit != 0 && bit != 1)
                throw std::invalid_argument("physical hard decision must be binary");
        Ids residual(m_phys_);
        for (int a = 0; a < m_phys_; ++a) {
            int parity = original_syndrome_[a];
            for (int v : original_rows_[a]) parity ^= physical_hard[v];
            residual[a] = parity;
        }
        return residual;
    }

    FailureWeights failure_weights(const Ids& physical_hard,
                                   const std::vector<Reals>& trailing_physical_llrs,
                                   const FailureSettings& cfg) const {
        if (cfg.residual_radius < 0 || cfg.top_k < 0 ||
            !(cfg.distance_decay >= 0 && cfg.distance_decay <= 1) ||
            !std::isfinite(cfg.distance_decay) ||
            cfg.uncertainty_weight < 0 || cfg.oscillation_weight < 0 ||
            !std::isfinite(cfg.uncertainty_weight) || !std::isfinite(cfg.oscillation_weight) ||
            cfg.uncertainty_weight + cfg.oscillation_weight <= 0 ||
            !std::isfinite(cfg.threshold) || cfg.threshold < 0 ||
            (cfg.selection != "top_k" && cfg.selection != "threshold"))
            throw std::invalid_argument("invalid failure-weight settings");
        if (trailing_physical_llrs.empty())
            throw std::invalid_argument("at least one marginal history entry is required");
        for (const auto& row : trailing_physical_llrs) {
            if (row.size() != static_cast<std::size_t>(n_phys_))
                throw std::invalid_argument("marginal history width differs from n_phys");
            for (double x : row) if (!std::isfinite(x))
                throw std::invalid_argument("marginal history must be finite");
        }
        FailureWeights result;
        result.residual_syndrome = residual_syndrome(physical_hard);
        Ids sources;
        for (int a = 0; a < m_phys_; ++a)
            if (result.residual_syndrome[a]) sources.push_back(a);
        if (sources.empty()) throw std::invalid_argument("no physical residual; BP should have terminated");

        // BFS on the immutable bipartite physical Tanner graph. Check sources
        // have distance 0, their adjacent variables distance 1.
        constexpr int unreachable = std::numeric_limits<int>::max();
        Ids check_distance(m_phys_, unreachable);
        result.distance.assign(n_phys_, unreachable);
        std::queue<std::pair<bool, int>> queue;
        for (int a : sources) { check_distance[a] = 0; queue.emplace(true, a); }
        while (!queue.empty()) {
            const auto [is_check, id] = queue.front(); queue.pop();
            if (is_check) {
                for (int v : original_rows_[id]) if (result.distance[v] == unreachable) {
                    result.distance[v] = check_distance[id] + 1;
                    queue.emplace(false, v);
                }
            } else {
                for (int a : original_variable_checks_[id]) if (check_distance[a] == unreachable) {
                    check_distance[a] = result.distance[id] + 1;
                    queue.emplace(true, a);
                }
            }
        }
        result.uncertainty.resize(n_phys_);
        result.oscillation.resize(n_phys_);
        result.omega.resize(n_phys_);
        for (int v = 0; v < n_phys_; ++v) {
            double mean = 0.0;
            for (const auto& row : trailing_physical_llrs) mean += row[v];
            mean /= static_cast<double>(trailing_physical_llrs.size());
            result.uncertainty[v] = 1.0 - std::abs(std::tanh(mean / 2.0));
            int flips = 0;
            for (std::size_t t = 1; t < trailing_physical_llrs.size(); ++t)
                flips += ((trailing_physical_llrs[t][v] > 0) -
                          (trailing_physical_llrs[t][v] < 0)) !=
                         ((trailing_physical_llrs[t-1][v] > 0) -
                          (trailing_physical_llrs[t-1][v] < 0));
            result.oscillation[v] = trailing_physical_llrs.size() < 2 ? 0.0 :
                static_cast<double>(flips) / (trailing_physical_llrs.size() - 1);
            if (result.distance[v] <= cfg.residual_radius)
                result.omega[v] = std::pow(cfg.distance_decay, result.distance[v]) *
                    (cfg.uncertainty_weight * result.uncertainty[v] +
                     cfg.oscillation_weight * result.oscillation[v]) /
                    (cfg.uncertainty_weight + cfg.oscillation_weight);
        }
        if (cfg.selection == "top_k") {
            Ids order(n_phys_);
            std::iota(order.begin(), order.end(), 0);
            std::sort(order.begin(), order.end(), [&](int a, int b) {
                if (result.omega[a] != result.omega[b]) return result.omega[a] > result.omega[b];
                return a < b;
            });
            for (int v : order) if (result.omega[v] > 0 &&
                static_cast<int>(result.suspicious.size()) < cfg.top_k) result.suspicious.push_back(v);
            std::sort(result.suspicious.begin(), result.suspicious.end());
        } else {
            for (int v = 0; v < n_phys_; ++v)
                if (result.omega[v] >= cfg.threshold) result.suspicious.push_back(v);
        }
        return result;
    }

    Ids active_variables(const Ids& suspicious) const {
        if (!sorted_unique(suspicious)) throw std::invalid_argument("U must be sorted unique");
        for (int j : suspicious) require_id(j, n_phys_, "suspicious physical variable");
        Ids active;
        for (int v = 0; v < variable_count(); ++v) {
            if (variables_[v].physical) {
                if (std::binary_search(suspicious.begin(), suspicious.end(), v)) active.push_back(v);
            } else if (!intersection(variables_[v].auxiliary_support, suspicious).empty()) {
                active.push_back(v);
            }
        }
        return active;
    }

    std::vector<Biclique> discover(const Ids& suspicious) const {
        std::set<Biclique> unique;
        for_each_pair_seed(suspicious, [&](Biclique b){ unique.insert(std::move(b)); });
        return {unique.begin(), unique.end()};
    }

    double phi(const Reals& physical_omega) const {
        const Reals weights = extended_weights(physical_omega);
        double score = 0.0;
        for (int a = 0; a < check_count(); ++a)
            for (int b = a + 1; b < check_count(); ++b)
                score += pair_products(intersection(checks_[a].variables, checks_[b].variables), weights);
        return score;
    }

    // Exact affected-neighborhood delta; never constructs a trial graph.
    double net_cycle_reduction(const Biclique& b, const Reals& physical_omega) const {
        validate_biclique(b);
        const Reals weights = extended_weights(physical_omega);
        return net_delta_with_weights(b, physical_omega, weights);
    }

    CandidateScore score_candidate(const Biclique& b, const Reals& omega) const {
        const double delta = net_cycle_reduction(b, omega);
        CandidateScore score;
        score.biclique = b;
        score.net_cycle_reduction = delta;
        auto choose2 = [](std::size_t x) -> std::uint64_t { return x * (x - 1) / 2; };
        score.internal_cycles = choose2(b.variables.size()) * choose2(b.checks.size());
        score.edges_before = edge_count_;
        score.edges_after = edge_count_ - b.variables.size() * b.checks.size() +
                            b.variables.size() + b.checks.size() + 1;
        score.auxiliaries_before = variable_count() - n_phys_;
        score.auxiliaries_after = score.auxiliaries_before + 1;
        const int q_degree = static_cast<int>(b.variables.size()) + 1;
        score.max_check_degree_after = q_degree;
        for (int c = 0; c < check_count(); ++c) {
            const int degree = static_cast<int>(checks_[c].variables.size());
            score.max_check_degree_before = std::max(score.max_check_degree_before, degree);
            score.max_check_degree_after = std::max(score.max_check_degree_after,
                degree + (std::binary_search(b.checks.begin(), b.checks.end(), c)
                          ? 1 - static_cast<int>(b.variables.size()) : 0));
        }
        score.max_variable_degree_after = static_cast<int>(b.checks.size()) + 1;
        for (int v = 0; v < variable_count(); ++v) {
            const int degree = static_cast<int>(variables_[v].checks.size());
            score.max_variable_degree_before = std::max(score.max_variable_degree_before, degree);
            score.max_variable_degree_after = std::max(score.max_variable_degree_after,
                degree + (std::binary_search(b.variables.begin(), b.variables.end(), v)
                          ? 1 - static_cast<int>(b.checks.size()) : 0));
        }
        return score;
    }

    // Mutates only current graph. Old IDs stay stable; returns (new y, new q).
    std::pair<int, int> factorize(const Biclique& b) {
        validate_biclique(b);
        Ids support;
        for (int v : b.variables) support = xor_support(support, physical_support(v));
        const int y = variable_count();
        const int q = check_count();
        variables_.push_back(Variable{{}, std::move(support), 0.0, false});
        checks_.push_back(Check{{}, 0, false});
        for (int v : b.variables) add_edge(v, q);
        add_edge(y, q);
        for (int c : b.checks) {
            for (int v : b.variables) remove_edge(v, c);
            add_edge(y, c);
        }
        return {y, q};
    }

    FactorizeResult factorize_graph(const Reals& omega, const Ids& suspicious,
                                    int n_fact, const std::string& policy) {
        if (n_fact < 0 || (policy != "adaptive_cycle" && policy != "shen_cycle_count"))
            throw std::invalid_argument("invalid factorization policy or budget");
        extended_weights(omega); // validate once even when n_fact=0
        active_variables(suspicious);
        FactorizeResult result;
        for (int t = 0; t < n_fact; ++t) {
            const Reals weights = extended_weights(omega);
            Biclique best_biclique;
            double best_delta = 0.0;
            std::uint64_t best_cycles = 0;
            bool have_best = false;
            std::size_t scored_seeds = 0;
            for_each_pair_seed(suspicious, [&](const Biclique& candidate) {
                ++scored_seeds;
                const double delta = policy == "adaptive_cycle" ?
                    net_delta_with_weights(candidate, omega, weights) : 0.0;
                const auto choose2 = [](std::size_t x) -> std::uint64_t { return x * (x - 1) / 2; };
                const std::uint64_t cycles = policy == "shen_cycle_count" ?
                    choose2(candidate.variables.size()) * choose2(candidate.checks.size()) : 0;
                const bool better = !have_best ||
                    (policy == "adaptive_cycle"
                        ? delta > best_delta ||
                          (delta == best_delta && candidate < best_biclique)
                        : cycles > best_cycles ||
                          (cycles == best_cycles && candidate < best_biclique));
                if (better) {
                    best_biclique = candidate;
                    best_delta = delta;
                    best_cycles = cycles;
                    have_best = true;
                }
            });
            result.scored_seeds_per_step.push_back(scored_seeds);
            if (!have_best) break;
            if (policy == "adaptive_cycle" && best_delta <= 0.0) break;
            CandidateScore best = score_candidate(best_biclique, omega);
            factorize(best.biclique);
            result.chosen.push_back(std::move(best));
            ++result.applied;
        }
        return result;
    }
};
}  // namespace af_bp_core
