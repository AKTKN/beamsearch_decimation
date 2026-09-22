#ifndef QEC_SEARCH_BP_MODEL_HPP
#define QEC_SEARCH_BP_MODEL_HPP
#include "decimated_bp.hpp"
#include <optional>
#include <numeric>
#include <string>

namespace qec::search_bp2 {
using ldpc::hybrid::Bits;
using ldpc::hybrid::Reals;
using ldpc::hybrid::Rows;
using ldpc::hybrid::Graph;
using ldpc::decimated::Pattern;
using ldpc::hybrid::binary;
using ldpc::hybrid::finite;

// Share the original sparse H with ldpc. A is owned once; no dense H or search
// copy of its adjacency is needed. Public services retain this as const.
struct Model {
    std::shared_ptr<const Graph> graph;
    Rows observables;
    Model(const Rows& h, int n, const Reals& p, const Rows& a)
        : graph(std::make_shared<Graph>(h, n, p)), observables(a) {
        for (const auto& row : observables) {
            if (!std::is_sorted(row.begin(), row.end()) ||
                std::adjacent_find(row.begin(), row.end()) != row.end())
                throw std::invalid_argument("observable rows must be sorted unique");
            for (int j : row) if (j < 0 || j >= n)
                throw std::invalid_argument("observable index outside model");
        }
    }
    Bits predict(const Bits& correction) const {
        binary(correction, graph->n);
        Bits out(observables.size(), 0);
        for (size_t a = 0; a < observables.size(); ++a)
            for (int j : observables[a]) out[a] ^= correction[j];
        return out;
    }
};

struct Settings {
    int initial_iterations = 30, history_window = 8;
    double history_clip = 25, scaling_factor = 1;
    int selected_checks = 2, local_variables = 4, max_fixations = 2;
    std::string local_variable_policy = "refresh_descendant";
    double beta = 1, guidance_strength = 1;
    void validate() const {
        if (history_window < 1 || initial_iterations < history_window ||
            selected_checks < 1 || local_variables < 1 || max_fixations < 1 ||
            (local_variable_policy != "fixed_root" && local_variable_policy != "refresh_descendant") ||
            (local_variable_policy == "fixed_root" && max_fixations > local_variables) ||
            !std::isfinite(beta) || beta < 0 ||
            !std::isfinite(guidance_strength) || guidance_strength < 0)
            throw std::invalid_argument("invalid Step-1-to-4 settings");
        // The fork checks clip/scaling as well, including ring-sum overflow.
        if (!std::isfinite(history_clip) || history_clip <= 0 ||
            history_clip > std::numeric_limits<double>::max() / (2.0 * history_window) ||
            !std::isfinite(scaling_factor) || scaling_factor <= 0 || scaling_factor > 1)
            throw std::invalid_argument("invalid BP numerical settings");
    }
};

inline void validate_pattern(const Pattern& pattern, int n) {
    int previous = -1;
    for (auto [j, b] : pattern) {
        if (j <= previous || j >= n || (b != 0 && b != 1))
            throw std::invalid_argument("pattern must be sorted unique in-range binary assignments");
        previous = j;
    }
}

struct Candidate {
    uint64_t parent_id = 0;
    Pattern delta;                 // Full pattern = parent fixed union delta.
    std::optional<double> f_solve;
    double f_guide = 0;
    size_t depth() const { return delta.size(); }
    // The canonical tie key is (delta, parent_id). No strings or copied BP state.
};
inline bool canonical_less(const Candidate& a, const Candidate& b) {
    return a.delta != b.delta ? a.delta < b.delta : a.parent_id < b.parent_id;
}
}
#endif
