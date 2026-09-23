#ifndef QEC_LPM_DP_CANDIDATES_HPP
#define QEC_LPM_DP_CANDIDATES_HPP

#include "lpm_dp_model.hpp"
#include <algorithm>
#include <cmath>
#include <map>
#include <numeric>
#include <queue>
#include <set>

namespace qec::lpm_dp {
namespace detail {

inline double clipped(double value, double limit) {
    return std::min(limit, std::max(-limit, value));
}

inline double softplus(double value) {
    return std::max(value, 0.0) + std::log1p(std::exp(-std::abs(value)));
}

inline double log_add_cost(double a, double b) {
    const double infinity = std::numeric_limits<double>::infinity();
    if (a == infinity) return b;
    if (b == infinity) return a;
    if (!std::isfinite(a) || !std::isfinite(b))
        throw std::runtime_error("invalid LPM-DP log-domain operand");
    const double minimum = std::min(a, b);
    return minimum - std::log1p(std::exp(-std::abs(a - b)));
}

inline bool list_less(const ListEntry& a, const ListEntry& b) {
    return a.cost != b.cost ? a.cost < b.cost : a.bits < b.bits;
}

inline bool contains_check(const std::vector<int>& checks, int check) {
    return std::binary_search(checks.begin(), checks.end(), check);
}

inline const LocalVariable& local_variable(const LocalFields& fields, int id) {
    const auto position = std::lower_bound(fields.variables.begin(), fields.variables.end(), id,
        [](const LocalVariable& value, int key) { return value.id < key; });
    if (position == fields.variables.end() || position->id != id)
        throw std::invalid_argument("local fields do not cover the selected region");
    return *position;
}

inline StateCosts empty_state_costs() {
    StateCosts out;
    out.fill(std::numeric_limits<double>::infinity());
    out[0] = 0;
    return out;
}

inline StateCosts sum_step(const StateCosts& old, const LocalVariable& variable, int states) {
    StateCosts next;
    next.fill(std::numeric_limits<double>::infinity());
    for (int state = 0; state < states; ++state) {
        const double zero = old[size_t(state)] + variable.unary_cost[0];
        const double one = old[size_t(state ^ variable.parity_label)] + variable.unary_cost[1];
        next[size_t(state)] = log_add_cost(zero, one);
    }
    return next;
}

inline void validate_parent(const ParentView& parent, const Settings& settings) {
    settings.validate();
    const auto& graph = parent.graph;
    ldpc::hybrid::binary(parent.syndrome, size_t(graph.m));
    if (parent.fixed.size() != size_t(graph.n) ||
        parent.posterior_history.size() != size_t(settings.history_window) ||
        parent.check_to_variable.size() != graph.col.size())
        throw std::invalid_argument("LPM-DP parent array shape mismatch");
    for (int8_t value : parent.fixed)
        if (value < -1 || value > 1) throw std::invalid_argument("invalid LPM-DP fixed mask");
    for (const auto& sample : parent.posterior_history) {
        if (sample.size() != size_t(graph.n))
            throw std::invalid_argument("LPM-DP history row shape mismatch");
        for (int j = 0; j < graph.n; ++j) {
            const double value = sample[size_t(j)];
            if (std::isnan(value) || (parent.fixed[size_t(j)] < 0 && !std::isfinite(value)))
                throw std::invalid_argument("free history LLRs must be finite and no history value may be NaN");
        }
    }
    for (size_t edge = 0; edge < parent.check_to_variable.size(); ++edge) {
        const double value = parent.check_to_variable[edge];
        if (std::isnan(value) ||
            (parent.fixed[size_t(graph.col[edge])] < 0 && !std::isfinite(value)))
            throw std::invalid_argument("free check-to-variable messages must be finite and no message may be NaN");
    }
}

inline void validate_region_shape(const Region& region) {
    if (region.checks.empty() || region.checks.size() > 2 ||
        !std::is_sorted(region.checks.begin(), region.checks.end()) ||
        std::adjacent_find(region.checks.begin(), region.checks.end()) != region.checks.end() ||
        region.variables.empty() || !std::is_sorted(region.variables.begin(), region.variables.end()) ||
        std::adjacent_find(region.variables.begin(), region.variables.end()) != region.variables.end())
        throw std::invalid_argument("invalid LPM-DP region shape");
}

} // namespace detail

inline ParentSummary summarize_parent(const ParentView& parent, const Settings& settings) {
    detail::validate_parent(parent, settings);
    const auto& graph = parent.graph;
    ParentSummary out;
    out.residual = parent.syndrome;
    out.free.resize(size_t(graph.n));
    out.mean_llr.assign(size_t(graph.n), 0);
    out.uncertainty.assign(size_t(graph.n), 0);
    for (int j = 0; j < graph.n; ++j) out.free[size_t(j)] = parent.fixed[size_t(j)] < 0;
    for (int j = 0; j < graph.n; ++j) if (parent.fixed[size_t(j)] == 1)
        for (size_t k = graph.cp[size_t(j)]; k < graph.cp[size_t(j + 1)]; ++k)
            out.residual[size_t(graph.row[graph.ce[k]])] ^= uint8_t(1);

    for (int check = 0; check < graph.m; ++check) {
        bool free_neighbor = false;
        for (size_t edge = graph.rp[size_t(check)]; edge < graph.rp[size_t(check + 1)]; ++edge)
            free_neighbor |= parent.fixed[size_t(graph.col[edge])] < 0;
        if (!free_neighbor && out.residual[size_t(check)]) {
            out.status = Status::ParentContradiction;
            return out;
        }
    }
    if (std::none_of(out.residual.begin(), out.residual.end(), [](uint8_t value) { return value != 0; })) {
        out.status = Status::ExistingSolution;
        return out;
    }

    struct PoolItem { double uncertainty; int id; };
    const auto better = [](const PoolItem& a, const PoolItem& b) {
        return a.uncertainty != b.uncertainty ? a.uncertainty > b.uncertainty : a.id < b.id;
    };
    std::priority_queue<PoolItem, std::vector<PoolItem>, decltype(better)> heap(better);
    for (int j = 0; j < graph.n; ++j) {
        if (parent.fixed[size_t(j)] >= 0) continue;
        double sum = 0;
        for (const auto& sample : parent.posterior_history)
            sum += detail::clipped(sample[size_t(j)], settings.history_clip);
        const double mean = sum / double(settings.history_window);
        out.mean_llr[size_t(j)] = mean;
        const double uncertainty = 2.0 / (1.0 + std::exp(std::abs(mean)));
        out.uncertainty[size_t(j)] = uncertainty;
        if (graph.cp[size_t(j)] == graph.cp[size_t(j + 1)]) continue;
        PoolItem item{uncertainty, j};
        if (heap.size() < size_t(settings.pool_size)) heap.push(item);
        else if (better(item, heap.top())) { heap.pop(); heap.push(item); }
    }
    while (!heap.empty()) { out.uncertain_pool.push_back(heap.top().id); heap.pop(); }
    std::sort(out.uncertain_pool.begin(), out.uncertain_pool.end(), [&](int j, int k) {
        const double a = out.uncertainty[size_t(j)], b = out.uncertainty[size_t(k)];
        return a != b ? a > b : j < k;
    });
    if (out.uncertain_pool.empty()) out.status = Status::NoActiveVariables;
    return out;
}

inline Region select_region(const Graph& graph, const ParentSummary& parent, const Settings& settings) {
    settings.validate();
    if (parent.status != Status::Ok || parent.residual.size() != size_t(graph.m) ||
        parent.free.size() != size_t(graph.n) || parent.uncertainty.size() != size_t(graph.n) ||
        parent.uncertain_pool.empty())
        throw std::invalid_argument("select_region requires a normal nonempty parent summary");
    std::vector<int> ordered_pool = parent.uncertain_pool;
    std::sort(ordered_pool.begin(), ordered_pool.end());
    std::map<int, double> single;
    std::map<std::pair<int, int>, double> pairs;
    for (int j : ordered_pool) {
        std::vector<int> checks;
        checks.reserve(graph.cp[size_t(j + 1)] - graph.cp[size_t(j)]);
        for (size_t k = graph.cp[size_t(j)]; k < graph.cp[size_t(j + 1)]; ++k)
            checks.push_back(graph.row[graph.ce[k]]);
        const double uncertainty = parent.uncertainty[size_t(j)];
        for (int check : checks) single[check] += uncertainty;
        for (size_t a = 0; a < checks.size(); ++a)
            for (size_t b = a + 1; b < checks.size(); ++b)
                pairs[{checks[a], checks[b]}] += uncertainty;
    }

    Region out;
    bool have_pair = false;
    double pair_weight = 0;
    std::pair<int, int> selected_pair{};
    if (settings.local_check_limit == 2) for (const auto& [pair, weight] : pairs) {
        if (weight <= 0) continue;
        if (!have_pair || weight > pair_weight || (weight == pair_weight && pair < selected_pair)) {
            have_pair = true; pair_weight = weight; selected_pair = pair;
        }
    }
    if (have_pair) out.checks = {selected_pair.first, selected_pair.second};
    else {
        if (single.empty()) throw std::logic_error("active uncertainty pool has no incident check");
        int selected = -1; double selected_weight = 0;
        for (const auto& [check, weight] : single)
            if (selected < 0 || weight > selected_weight) { selected = check; selected_weight = weight; }
        out.checks = {selected};
    }

    std::set<int> variables;
    for (int check : out.checks)
        for (size_t edge = graph.rp[size_t(check)]; edge < graph.rp[size_t(check + 1)]; ++edge) {
            const int j = graph.col[edge];
            if (parent.free[size_t(j)]) variables.insert(j);
        }
    out.variables.assign(variables.begin(), variables.end());

    struct Position { int id; int incidence; double score; };
    std::vector<Position> positions;
    for (int j : parent.uncertain_pool) {
        int incidence = 0;
        for (int check : out.checks) {
            const auto first = graph.col.begin() + std::ptrdiff_t(graph.rp[size_t(check)]);
            const auto last = graph.col.begin() + std::ptrdiff_t(graph.rp[size_t(check + 1)]);
            incidence += std::binary_search(first, last, j);
        }
        if (incidence) positions.push_back({j, incidence, parent.uncertainty[size_t(j)] * incidence});
    }
    std::sort(positions.begin(), positions.end(), [](const Position& a, const Position& b) {
        return a.score != b.score ? a.score > b.score : a.id < b.id;
    });
    for (const auto& position : positions) out.uncertain_local.push_back(position.id);
    const size_t q0 = std::min(size_t(settings.max_fixations), out.uncertain_local.size());
    out.fixation_order.assign(out.uncertain_local.begin(), out.uncertain_local.begin() + q0);
    if (out.fixation_order.empty()) throw std::logic_error("selected region has no fixation position");
    return out;
}

inline LocalFields build_local_fields(const ParentView& parent, const Region& region,
                                      const Settings& settings) {
    detail::validate_parent(parent, settings);
    detail::validate_region_shape(region);
    std::set<int> expected_variables;
    for (int check : region.checks) {
        if (check < 0 || check >= parent.graph.m)
            throw std::invalid_argument("selected check is outside the graph");
        for (size_t edge = parent.graph.rp[size_t(check)];
             edge < parent.graph.rp[size_t(check + 1)]; ++edge) {
            const int j = parent.graph.col[edge];
            if (parent.fixed[size_t(j)] < 0) expected_variables.insert(j);
        }
    }
    if (!std::equal(expected_variables.begin(), expected_variables.end(),
                    region.variables.begin(), region.variables.end()))
        throw std::invalid_argument("local region is not the full free selected-check neighborhood");
    LocalFields out;
    out.variables.reserve(region.variables.size());
    for (int j : region.variables) {
        if (j < 0 || j >= parent.graph.n || parent.fixed[size_t(j)] >= 0)
            throw std::invalid_argument("local region must contain free in-range variables");
        double field = detail::clipped(parent.graph.weights[size_t(j)], settings.proposal_clip);
        uint8_t label = 0;
        for (size_t k = parent.graph.cp[size_t(j)]; k < parent.graph.cp[size_t(j + 1)]; ++k) {
            const size_t edge = parent.graph.ce[k];
            const int check = parent.graph.row[edge];
            const auto selected = std::lower_bound(region.checks.begin(), region.checks.end(), check);
            if (selected != region.checks.end() && *selected == check)
                label |= uint8_t(1U << size_t(selected - region.checks.begin()));
            else
                field += detail::clipped(parent.check_to_variable[edge], settings.proposal_clip);
        }
        field = detail::clipped(field, settings.proposal_clip);
        LocalVariable value;
        value.id = j; value.parity_label = label; value.field = field;
        value.unary_cost[0] = detail::softplus(-field);
        value.unary_cost[1] = detail::softplus(field);
        value.unary_probability[0] = std::exp(-value.unary_cost[0]);
        value.unary_probability[1] = std::exp(-value.unary_cost[1]);
        out.variables.push_back(value);
    }
    if (!std::is_sorted(out.variables.begin(), out.variables.end(),
                        [](const LocalVariable& a, const LocalVariable& b) { return a.id < b.id; }))
        throw std::invalid_argument("local region variables must be sorted");
    return out;
}

inline DPTables build_dp_tables(const Region& region, const LocalFields& fields,
                                const Bits& residual, const Settings& settings) {
    settings.validate();
    detail::validate_region_shape(region);
    const size_t q0 = region.fixation_order.size();
    if (q0 < 1 || q0 > size_t(settings.max_fixations) || fields.variables.size() != region.variables.size() ||
        !std::is_sorted(fields.variables.begin(), fields.variables.end(),
                        [](const LocalVariable& a, const LocalVariable& b) { return a.id < b.id; }))
        throw std::invalid_argument("invalid LPM-DP location or field shape");
    const int states = 1 << region.checks.size();
    for (size_t index = 0; index < fields.variables.size(); ++index) {
        const auto& variable = fields.variables[index];
        if (variable.id != region.variables[index] || variable.parity_label == 0 ||
            variable.parity_label >= states || !std::isfinite(variable.field) ||
            !std::isfinite(variable.unary_probability[0]) || variable.unary_probability[0] <= 0 ||
            !std::isfinite(variable.unary_probability[1]) || variable.unary_probability[1] <= 0 ||
            !std::isfinite(variable.unary_cost[0]) || variable.unary_cost[0] < 0 ||
            !std::isfinite(variable.unary_cost[1]) || variable.unary_cost[1] < 0)
            throw std::invalid_argument("invalid LPM-DP local field");
    }
    std::vector<int> fixation_ids = region.fixation_order;
    std::sort(fixation_ids.begin(), fixation_ids.end());
    if (std::adjacent_find(fixation_ids.begin(), fixation_ids.end()) != fixation_ids.end() ||
        std::any_of(fixation_ids.begin(), fixation_ids.end(), [&](int id) {
            return !std::binary_search(region.variables.begin(), region.variables.end(), id);
        }))
        throw std::invalid_argument("fixation order must be unique and contained in the region");
    DPTables out;
    out.states = states;
    for (size_t bit = 0; bit < region.checks.size(); ++bit) {
        const int check = region.checks[bit];
        if (check < 0 || size_t(check) >= residual.size() || residual[size_t(check)] > 1)
            throw std::invalid_argument("invalid selected-check residual");
        out.target |= uint8_t(residual[size_t(check)] << bit);
    }
    out.suffix_cost.resize(q0 + 1);
    out.prefix_cost.resize(q0 + 1);
    out.prefix_top.resize(q0 + 1);

    StateCosts boundary = detail::empty_state_costs();
    for (int j : region.variables) if (!std::binary_search(fixation_ids.begin(), fixation_ids.end(), j))
        boundary = detail::sum_step(boundary, detail::local_variable(fields, j), out.states);
    out.suffix_cost[q0] = boundary;
    for (size_t q = q0; q-- > 0;)
        out.suffix_cost[q] = detail::sum_step(out.suffix_cost[q + 1],
                                              detail::local_variable(fields, region.fixation_order[q]), out.states);
    out.feasible = std::isfinite(out.suffix_cost[0][out.target]);
    if (!out.feasible) return out;

    out.prefix_cost[0] = detail::empty_state_costs();
    out.prefix_top[0][0].push_back({0, 0});
    const size_t keep = size_t(settings.candidates_per_parent);
    if (keep > std::vector<ListEntry>{}.max_size() / 2)
        throw std::length_error("LPM-DP list width exceeds vector capacity");
    for (size_t q = 1; q <= q0; ++q) {
        const auto& variable = detail::local_variable(fields, region.fixation_order[q - 1]);
        out.prefix_cost[q] = detail::sum_step(out.prefix_cost[q - 1], variable, out.states);
        for (int state = 0; state < out.states; ++state) {
            std::vector<ListEntry> merged;
            const auto& zero = out.prefix_top[q - 1][size_t(state)];
            const auto& one = out.prefix_top[q - 1][size_t(state ^ variable.parity_label)];
            merged.reserve(zero.size() + one.size());
            for (const auto& entry : zero)
                merged.push_back({entry.cost + variable.unary_cost[0], uint64_t(entry.bits << 1)});
            for (const auto& entry : one)
                merged.push_back({entry.cost + variable.unary_cost[1], uint64_t((entry.bits << 1) | 1U)});
            std::sort(merged.begin(), merged.end(), detail::list_less);
            if (merged.size() > keep) merged.resize(keep);
            out.prefix_top[q][size_t(state)] = std::move(merged);
        }
    }
    return out;
}

inline FixationEvaluation evaluate_fixation_count(const DPTables& tables, int fixation_count,
                                                   const Settings& settings, size_t region_size) {
    settings.validate();
    if (!tables.feasible || fixation_count < 1 || size_t(fixation_count) >= tables.suffix_cost.size() ||
        tables.prefix_cost.size() != tables.suffix_cost.size() ||
        tables.prefix_top.size() != tables.suffix_cost.size())
        throw std::invalid_argument("invalid LPM-DP fixation-count evaluation");
    FixationEvaluation out;
    out.fixation_count = fixation_count;
    const size_t q = size_t(fixation_count);
    for (int state = 0; state < tables.states; ++state) {
        const double boundary = tables.suffix_cost[q][size_t(tables.target ^ state)];
        if (!std::isfinite(boundary)) continue;
        for (const auto& entry : tables.prefix_top[q][size_t(state)])
            out.ranked.push_back({entry.cost + boundary, entry.bits});
    }
    std::sort(out.ranked.begin(), out.ranked.end(), detail::list_less);
    if (out.ranked.size() > size_t(settings.candidates_per_parent))
        out.ranked.resize(size_t(settings.candidates_per_parent));
    if (out.ranked.empty()) throw std::logic_error("feasible local model produced no candidate");

    double normalizer = std::numeric_limits<double>::infinity();
    for (int state = 0; state < tables.states; ++state) {
        const double cost = tables.prefix_cost[q][size_t(state)] +
            tables.suffix_cost[q][size_t(tables.target ^ state)];
        normalizer = detail::log_add_cost(normalizer, cost);
    }
    out.negative_log_normalizer = normalizer;
    if (fixation_count == 1) {
        out.log_retained_mass = 0;
        out.retained_mass = 1;
        return out;
    }
    double retained_cost = std::numeric_limits<double>::infinity();
    for (const auto& entry : out.ranked)
        retained_cost = detail::log_add_cost(retained_cost, entry.cost);
    double log_mass = normalizer - retained_cost;
    const double tolerance = 128 * std::numeric_limits<double>::epsilon() *
        (1 + double(region_size) + double(tables.suffix_cost.size() - 1)) * (1 + settings.proposal_clip);
    if (log_mass > tolerance) throw std::runtime_error("LPM-DP retained mass exceeds one");
    if (log_mass > 0) log_mass = 0;
    out.log_retained_mass = log_mass;
    out.retained_mass = std::exp(log_mass);
    return out;
}

inline Result choose_fixation_count(uint64_t parent_id, const Region& region,
                                    const DPTables& tables, const Settings& settings) {
    settings.validate();
    Result out;
    out.parent_id = parent_id;
    out.selected_checks = region.checks;
    out.fixation_order = region.fixation_order;
    if (!tables.feasible) { out.status = Status::LocalInfeasible; return out; }
    const double threshold = std::log(settings.retained_mass_target);
    FixationEvaluation selected;
    for (size_t q = region.fixation_order.size(); q > 0; --q) {
        auto evaluation = evaluate_fixation_count(tables, int(q), settings, region.variables.size());
        if (q == 1 || evaluation.log_retained_mass >= threshold) {
            selected = std::move(evaluation);
            break;
        }
    }
    out.fixation_count = selected.fixation_count;
    out.negative_log_normalizer = selected.negative_log_normalizer;
    out.retained_mass = selected.retained_mass;
    for (const auto& entry : selected.ranked) {
        FixationCandidate candidate;
        candidate.parent_id = parent_id;
        candidate.local_cost = entry.cost;
        candidate.log_probability = selected.negative_log_normalizer - entry.cost;
        candidate.selected_order_bits = entry.bits;
        for (int position = 0; position < selected.fixation_count; ++position) {
            const unsigned shift = unsigned(selected.fixation_count - 1 - position); // 0--63, never 64.
            const int bit = int((entry.bits >> shift) & uint64_t(1));
            candidate.pattern.emplace_back(region.fixation_order[size_t(position)], bit);
        }
        std::sort(candidate.pattern.begin(), candidate.pattern.end());
        out.candidates.push_back(std::move(candidate));
    }
    return out;
}

inline Result generate_candidates(const ParentView& parent, const Settings& settings = {}) {
    settings.validate();
    const auto summary = summarize_parent(parent, settings);
    Result out; out.status = summary.status; out.parent_id = parent.parent_id;
    if (summary.status != Status::Ok) return out;
    const auto region = select_region(parent.graph, summary, settings);
    const auto fields = build_local_fields(parent, region, settings);
    const auto tables = build_dp_tables(region, fields, summary.residual, settings);
    return choose_fixation_count(parent.parent_id, region, tables, settings);
}

} // namespace qec::lpm_dp
#endif
