#ifndef QEC_SEARCH_BP_SEARCH_HPP
#define QEC_SEARCH_BP_SEARCH_HPP
#include "search_bp_scores.hpp"
#include <queue>
#include <set>

namespace qec::search_bp2 {
inline std::vector<int> select_checks(const ParentScores& p, int count) {
    if (count < 1) throw std::invalid_argument("selected check count must be positive");
    std::vector<int> checks(p.graph->m);
    std::iota(checks.begin(), checks.end(), 0);
    const size_t n = std::min(size_t(count), checks.size());
    std::partial_sort(checks.begin(), checks.begin() + n, checks.end(), [&](int a, int b) {
        return p.ambiguity[a] != p.ambiguity[b] ? p.ambiguity[a] > p.ambiguity[b] : a < b;
    });
    checks.resize(n); return checks;
}
inline std::vector<int> select_variables(const ParentScores& p, int a, int count) {
    if (a < 0 || a >= p.graph->m || count < 1) throw std::invalid_argument("invalid local selection");
    std::vector<int> variables;
    variables.reserve(p.graph->rp[a + 1] - p.graph->rp[a]);
    for (size_t e = p.graph->rp[a]; e < p.graph->rp[a + 1]; ++e)
        if (p.fixed[p.graph->col[e]] < 0) variables.push_back(p.graph->col[e]);
    const size_t n = std::min(size_t(count), variables.size());
    std::partial_sort(variables.begin(), variables.begin() + n, variables.end(), [&](int j, int k) {
        return p.confidence[j] != p.confidence[k] ? p.confidence[j] < p.confidence[k] : j < k;
    });
    variables.resize(n); return variables;
}
inline size_t pattern_bound(size_t m, size_t q) {
    size_t term = 1, sum = 0;
    for (size_t d = 1; d <= std::min(m, q); ++d) {
        // term_d = term_(d-1) * (m-d+1) * 2 / d, exactly.
        size_t numerator = m - d + 1, denominator = d;
        size_t divisor = std::gcd(numerator, denominator);
        numerator /= divisor; denominator /= divisor;
        divisor = std::gcd(term, denominator);
        size_t reduced = term / divisor; denominator /= divisor;
        // Any remaining denominator divides 2.
        const size_t factor = 2 / denominator;
        if (numerator > SIZE_MAX / factor || reduced > SIZE_MAX / (numerator * factor))
            throw std::length_error("local pattern count overflows size_t");
        term = reduced * numerator * factor;
        if (term > SIZE_MAX - sum) throw std::length_error("local pattern count overflows size_t");
        sum += term;
    }
    return sum;
}
struct LocalResult {
    std::vector<Candidate> candidates;
    Bits correction;  // Populated only with a validated full solution.
    bool valid = false;
};

class LocalSearch {
    const ParentScores& parent_;
    const Settings& settings_;
    uint64_t parent_id_;
    Scorer scorer_;
    LocalResult result_;

    bool emit(const Pattern& delta, bool solve) {
        const auto scores = scorer_.evaluate(delta, settings_.guidance_strength, solve);
        result_.candidates.push_back({parent_id_, delta,
            solve ? std::optional<double>(scores.f_solve) : std::nullopt, scores.f_guide});
        if (solve && std::none_of(scorer_.residual.begin(), scorer_.residual.end(), [](uint8_t x){ return x != 0; })) {
            Bits correction(parent_.graph->n, 0);
            for (int j = 0; j < parent_.graph->n; ++j)
                if (scorer_.fixed[j] >= 0) correction[j] = uint8_t(scorer_.fixed[j]);
            if (!parent_.graph->valid(correction, parent_.syndrome))
                throw std::logic_error("search residual disagrees with original H validation");
            result_.correction = std::move(correction); result_.valid = true;
        }
        return result_.valid;
    }
    void enumerate(const std::vector<int>& local, size_t start, Pattern& delta) {
        for (size_t k = start; k < local.size(); ++k) for (int b = 0; b < 2; ++b) {
            delta.emplace_back(local[k], b);
            emit(delta, false); // Changing a satisfied parity is permitted.
            if (delta.size() < size_t(settings_.max_fixations)) enumerate(local, k + 1, delta);
            delta.pop_back();
        }
    }
    void solve_tree(int anchor, std::vector<int> local) {
        const auto& g = *parent_.graph;
        const auto physical_less = [&](int j, int k) {
            return g.weights[j] != g.weights[k] ? g.weights[j] < g.weights[k] : j < k;
        };
        std::sort(local.begin(), local.end(), physical_less);
        std::set<Pattern> seen; // Per local tree; never carried into another BP cycle.
        // Heap contains indices, not copies of messages/residuals or patterns.
        auto worse = [&](size_t a, size_t b) {
            const auto& x = result_.candidates[a]; const auto& y = result_.candidates[b];
            return x.f_solve != y.f_solve ? *x.f_solve > *y.f_solve : canonical_less(y, x);
        };
        std::priority_queue<size_t, std::vector<size_t>, decltype(worse)> frontier(worse);
        auto branch = [&](int check, const Pattern& base, const std::vector<int>& eligible) {
            // Earlier eligible variables are excluded by explicit zero fixations.
            // Each child chooses the first selected-one variable canonically.
            Pattern prefix;
            prefix.reserve(std::min(size_t(g.n), size_t(settings_.max_fixations)));
            prefix.assign(base.begin(), base.end());
            for (int j : eligible) {
                if (std::any_of(base.begin(), base.end(), [j](auto x){ return x.first == j; })) continue;
                if (!std::binary_search(g.col.begin() + g.rp[check], g.col.begin() + g.rp[check + 1], j)) continue;
                if (prefix.size() == size_t(settings_.max_fixations)) break;
                const auto position = std::lower_bound(prefix.begin(), prefix.end(), std::pair<int,int>{j, 0});
                const size_t offset = size_t(position - prefix.begin());
                prefix.insert(position, {j, 1});
                if (!seen.insert(prefix).second) { prefix[offset].second = 0; continue; }
                if (emit(prefix, true)) return;
                const size_t index = result_.candidates.size() - 1;
                if (prefix.size() < size_t(settings_.max_fixations) && std::isfinite(*result_.candidates[index].f_solve))
                    frontier.push(index);
                prefix[offset].second = 0;
            }
        };
        branch(anchor, {}, local);
        std::vector<int> refreshed;
        while (!result_.valid && !frontier.empty()) {
            // Copy only this bounded pattern: emit may reallocate the result pool.
            Pattern base = result_.candidates[frontier.top()].delta; frontier.pop();
            scorer_.load(base);
            int check = -1;
            for (int a = 0; a < g.m; ++a) if (scorer_.residual[a]) {
                if (check < 0 || (settings_.local_variable_policy == "refresh_descendant" &&
                    scorer_.probability[a] < scorer_.probability[check])) check = a;
            }
            if (check < 0) continue;
            if (settings_.local_variable_policy == "fixed_root") branch(check, base, local);
            else {
                refreshed.clear();
                // Reuse the largest visited check neighborhood, not an N-sized
                // allocation for every tree (or any allocation in fixed_root).
                refreshed.reserve(g.rp[check + 1] - g.rp[check]);
                for (size_t e = g.rp[check]; e < g.rp[check + 1]; ++e)
                    if (scorer_.fixed[g.col[e]] < 0) refreshed.push_back(g.col[e]);
                const size_t count = std::min(refreshed.size(), size_t(settings_.local_variables));
                std::partial_sort(refreshed.begin(), refreshed.begin() + count, refreshed.end(), [&](int j, int k) {
                    return parent_.confidence[j] != parent_.confidence[k] ?
                        parent_.confidence[j] < parent_.confidence[k] : j < k;
                });
                refreshed.resize(count);
                std::sort(refreshed.begin(), refreshed.end(), physical_less);
                branch(check, base, refreshed);
            }
        }
    }
public:
    LocalSearch(const ParentScores& parent, const Settings& settings, uint64_t parent_id)
        : parent_(parent), settings_(settings), parent_id_(parent_id), scorer_(parent) { settings.validate(); }
    LocalResult run() {
        const auto checks = select_checks(parent_, settings_.selected_checks);
        for (int a : checks) {
            auto local = select_variables(parent_, a, settings_.local_variables);
            // Root-bounded enumeration has the exact N_pat(m,q) bound. Refresh
            // trees may leave that set; reserve the root width and let the
            // vector grow, without imposing an unrelated child/leaf limit.
            const size_t bound = parent_.residual[a] && settings_.local_variable_policy == "refresh_descendant"
                ? local.size() : pattern_bound(local.size(), settings_.max_fixations);
            if (bound > result_.candidates.max_size() - result_.candidates.size())
                throw std::length_error("candidate pool exceeds vector capacity");
            result_.candidates.reserve(result_.candidates.size() + bound);
            if (parent_.residual[a]) solve_tree(a, std::move(local));
            else {
                std::sort(local.begin(), local.end());
                Pattern delta; delta.reserve(std::min(local.size(), size_t(settings_.max_fixations)));
                enumerate(local, 0, delta);
            }
            if (result_.valid) break;
        }
        return std::move(result_);
    }
};
}
#endif
