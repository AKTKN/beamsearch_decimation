#ifndef QEC_LPM_DP_MODEL_HPP
#define QEC_LPM_DP_MODEL_HPP

#include "hybrid_graph.hpp"
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <utility>
#include <vector>

namespace qec::lpm_dp {
using ldpc::hybrid::Bits;
using ldpc::hybrid::Graph;
using ldpc::hybrid::Reals;
using Pattern = std::vector<std::pair<int, int>>;

struct Settings {
    int history_window = 8;
    double history_clip = 25.0;
    int pool_size = 32;
    int local_check_limit = 2;
    int max_fixations = 4;
    int candidates_per_parent = 2;
    double retained_mass_target = 0.9;
    double proposal_clip = 30.0;

    void validate() const {
        if (history_window < 1 || !std::isfinite(history_clip) || history_clip <= 0 || history_clip > 30 ||
            pool_size < 1 || (local_check_limit != 1 && local_check_limit != 2) ||
            max_fixations < 1 || max_fixations > 64 || candidates_per_parent < 2 ||
            !std::isfinite(retained_mass_target) || retained_mass_target <= 0 || retained_mass_target > 1 ||
            !std::isfinite(proposal_clip) || proposal_clip <= 0 || proposal_clip > 30)
            throw std::invalid_argument("invalid LPM-DP 1.0 settings");
    }
};

// Non-owning immutable view. check_to_variable is aligned with Graph::col/row:
// entry e is the final completed-iteration message mu_(row[e])->col[e].
// posterior_history is ordered oldest to newest and must contain exactly W rows.
struct ParentView {
    const Graph& graph;
    const Bits& syndrome;
    const std::vector<int8_t>& fixed;
    const std::vector<Reals>& posterior_history;
    const Reals& check_to_variable;
    uint64_t parent_id = 0;
};

// Decoder-facing view of the same parent. The mean must be the exact clipped
// W-sample mean exported by a session whose history_count == W. This avoids
// duplicating the snapshot's O(NW) ring in every retained parent.
struct AveragedParentView {
    const Graph& graph;
    const Bits& syndrome;
    const std::vector<int8_t>& fixed;
    const Reals& mean_llr;
    const Reals& check_to_variable;
    uint64_t parent_id = 0;
};

enum class Status {
    Ok,
    ParentContradiction,
    ExistingSolution,
    NoActiveVariables,
    LocalInfeasible,
};

struct ParentSummary {
    Status status = Status::Ok;
    Bits residual;
    Bits free;
    Reals mean_llr;
    Reals uncertainty;
    std::vector<int> uncertain_pool;  // (-u_j,j), hence uncertainty descending.
};

struct Region {
    std::vector<int> checks;          // Ascending original check IDs; size one or two.
    std::vector<int> variables;       // Full free selected-check neighborhood, ascending.
    std::vector<int> uncertain_local; // U intersect variables, in fixation-score order.
    std::vector<int> fixation_order;  // First q0 entries of uncertain_local.
};

struct LocalVariable {
    int id = -1;
    uint8_t parity_label = 0;
    double field = 0;
    std::array<double, 2> unary_probability{};
    std::array<double, 2> unary_cost{};
};

struct LocalFields {
    std::vector<LocalVariable> variables; // Ascending original variable ID.
};

struct ListEntry {
    double cost = 0;
    uint64_t bits = 0; // Selected-order bit string, with the first bit most significant.
};

using StateCosts = std::array<double, 4>;
using StateLists = std::array<std::vector<ListEntry>, 4>;

struct DPTables {
    int states = 0;
    uint8_t target = 0;
    std::vector<StateCosts> suffix_cost;
    std::vector<StateCosts> prefix_cost;
    std::vector<StateLists> prefix_top;
    bool feasible = false;
};

struct FixationCandidate {
    uint64_t parent_id = 0;
    Pattern pattern;                  // Canonical original-variable-ID order.
    double local_cost = 0;
    double log_probability = 0;
    uint64_t selected_order_bits = 0;
};

struct FixationEvaluation {
    int fixation_count = 0;
    double negative_log_normalizer = 0;
    double log_retained_mass = -std::numeric_limits<double>::infinity();
    double retained_mass = 0;
    std::vector<ListEntry> ranked;
};

struct Result {
    Status status = Status::Ok;
    uint64_t parent_id = 0;
    std::vector<int> selected_checks;
    std::vector<int> fixation_order;
    int fixation_count = 0;
    double negative_log_normalizer = 0;
    double retained_mass = 0;
    std::vector<FixationCandidate> candidates;
};

} // namespace qec::lpm_dp
#endif
