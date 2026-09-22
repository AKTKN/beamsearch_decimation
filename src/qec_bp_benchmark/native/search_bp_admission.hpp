#ifndef QEC_SEARCH_BP_ADMISSION_HPP
#define QEC_SEARCH_BP_ADMISSION_HPP
#include "search_bp_model.hpp"
#include <set>

namespace qec::search_bp2 {
struct PooledCandidate {
    size_t parent_index;
    Candidate candidate;
    Pattern full;
};
inline Pattern extend_pattern(const Pattern& parent, const Pattern& delta) {
    Pattern full;
    full.reserve(parent.size() + delta.size());
    std::merge(parent.begin(), parent.end(), delta.begin(), delta.end(), std::back_inserter(full));
    for (size_t i = 1; i < full.size(); ++i)
        if (full[i-1].first == full[i].first) throw std::invalid_argument("candidate overlaps ancestor fixation");
    return full;
}

// Return execution-order indices into the global cycle pool. Quotas are over
// occurrences BEFORE deduplication, exactly Unique(Top_s union Top_g). First
// selected occurrence donates its BP state. All rankings have a total order.
inline std::vector<size_t> admit(const std::vector<PooledCandidate>& pool, size_t k_run) {
    if (!k_run) throw std::invalid_argument("K_run must be positive");
    std::vector<size_t> solve, guide;
    solve.reserve(pool.size()); guide.reserve(pool.size());
    for (size_t i = 0; i < pool.size(); ++i) {
        const auto& c = pool[i].candidate;
        if (!std::isfinite(c.f_guide) || (c.f_solve && (std::isnan(*c.f_solve) || *c.f_solve < 0)))
            throw std::invalid_argument("invalid candidate score");
        guide.push_back(i);
        if (c.f_solve) solve.push_back(i);
    }
    auto tie_less = [&](size_t i, size_t j) {
        const auto& a = pool[i]; const auto& b = pool[j];
        if (a.full != b.full) return a.full < b.full;
        if (a.candidate.parent_id != b.candidate.parent_id) return a.candidate.parent_id < b.candidate.parent_id;
        if (a.candidate.delta != b.candidate.delta) return a.candidate.delta < b.candidate.delta;
        return i < j;
    };
    auto solve_worse = [&](size_t i, size_t j) {
        const double a = *pool[i].candidate.f_solve, b = *pool[j].candidate.f_solve;
        return a != b ? a > b : tie_less(j, i);
    };
    auto guide_worse = [&](size_t i, size_t j) {
        const double a = pool[i].candidate.f_guide, b = pool[j].candidate.f_guide;
        return a != b ? a > b : tie_less(j, i);
    };
    std::make_heap(solve.begin(), solve.end(), solve_worse);
    std::make_heap(guide.begin(), guide.end(), guide_worse);
    std::vector<size_t> selected; selected.reserve(std::min(k_run, pool.size()));
    std::set<Pattern> seen;
    auto take = [&](auto& heap, auto worse, size_t occurrences) {
        while (occurrences-- && !heap.empty() && selected.size() < k_run) {
            std::pop_heap(heap.begin(), heap.end(), worse);
            const size_t index = heap.back(); heap.pop_back();
            if (seen.insert(pool[index].full).second) selected.push_back(index);
        }
    };
    take(solve, solve_worse, k_run / 2);
    take(guide, guide_worse, k_run - k_run / 2);
    take(guide, guide_worse, guide.size());
    take(solve, solve_worse, solve.size());
    return selected;
}
}
#endif
