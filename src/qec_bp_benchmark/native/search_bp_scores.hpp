#ifndef QEC_SEARCH_BP_SCORES_HPP
#define QEC_SEARCH_BP_SCORES_HPP
#include "search_bp_model.hpp"

namespace qec::search_bp2 {
struct Scores { double g = 0, h = 0, f_solve = 0, j_var = 0, g_amb = 0, f_guide = 0; };

// One immutable posterior summary per parent. Fixed means are ignored.
struct ParentScores {
    std::shared_ptr<const Graph> graph;
    Bits syndrome, residual;
    std::vector<int8_t> fixed;
    Reals mean, signed_confidence, confidence, probability, ambiguity;
    size_t free_count = 0;
    double beta, objective = 0, fixed_cost = 0;
    ParentScores(std::shared_ptr<const Graph> g, const Bits& s, const Pattern& d,
                 Reals means, double check_weight)
        : graph(std::move(g)), syndrome(s), residual(s), fixed(graph->n, -1),
          mean(std::move(means)), signed_confidence(graph->n), confidence(graph->n),
          probability(graph->m), ambiguity(graph->m), beta(check_weight) {
        binary(s, graph->m); validate_pattern(d, graph->n);
        if (mean.size() != size_t(graph->n) || !std::isfinite(beta) || beta < 0)
            throw std::invalid_argument("invalid posterior shape or beta");
        for (auto [j, b] : d) {
            fixed[j] = int8_t(b);
            if (b) fixed_cost = finite(fixed_cost + graph->weights[j]);
            for (size_t k = graph->cp[j]; k < graph->cp[j + 1]; ++k)
                residual[graph->row[graph->ce[k]]] ^= uint8_t(b);
        }
        double variable_sum = 0;
        for (int j = 0; j < graph->n; ++j) {
            if (fixed[j] >= 0) { confidence[j] = 1; continue; }
            if (!std::isfinite(mean[j])) throw std::invalid_argument("free mean LLR must be finite");
            ++free_count;
            signed_confidence[j] = std::tanh(mean[j] / 2);
            confidence[j] = std::abs(signed_confidence[j]);
            variable_sum += 1 - confidence[j];
        }
        double check_sum = 0;
        for (int a = 0; a < graph->m; ++a) {
            double product = residual[a] ? -1 : 1;
            for (size_t e = graph->rp[a]; e < graph->rp[a + 1]; ++e) {
                const int j = graph->col[e];
                if (fixed[j] < 0) product *= signed_confidence[j];
            }
            probability[a] = .5 * (1 + product);
            ambiguity[a] = 1 - probability[a]; check_sum += ambiguity[a];
        }
        // Empty normalized sums contribute zero. No candidates can fix an
        // already fully fixed parent; inconsistent empty checks have Q=0.
        objective = finite((free_count ? variable_sum / free_count : 0) +
                           (graph->m ? beta * (check_sum / graph->m) : 0));
    }
};

// Reused O(N+M) scratch. Loading a pattern restores only previously touched
// entries, flips incident residual checks, then recomputes only touched Qs.
// No BP calls and no writes to the parent or its message/history snapshot.
class Scorer {
    const ParentScores& parent_;
    std::vector<int> touched_, changed_, coverage_;
    Bits marked_;
public:
    std::vector<int8_t> fixed;
    Bits residual;
    Reals probability;
    explicit Scorer(const ParentScores& parent)
        : parent_(parent), coverage_(parent.graph->n), marked_(parent.graph->m, 0),
          fixed(parent.fixed), residual(parent.residual), probability(parent.probability) {
        touched_.reserve(parent.graph->m); changed_.reserve(parent.graph->n);
    }
    void load(const Pattern& delta) {
        const auto& g = *parent_.graph;
        validate_pattern(delta, g.n);
        if (delta.empty()) throw std::invalid_argument("candidate delta must be nonempty");
        for (auto [j, b] : delta) {
            (void)b;
            if (parent_.fixed[j] >= 0) throw std::invalid_argument("delta overlaps parent fixation");
        }
        for (int j : changed_) fixed[j] = parent_.fixed[j];
        for (int a : touched_) {
            residual[a] = parent_.residual[a]; probability[a] = parent_.probability[a]; marked_[a] = 0;
        }
        touched_.clear(); changed_.clear();
        for (auto [j, b] : delta) {
            fixed[j] = int8_t(b); changed_.push_back(j);
            for (size_t k = g.cp[j]; k < g.cp[j + 1]; ++k) {
                const int a = g.row[g.ce[k]];
                residual[a] ^= uint8_t(b);
                if (!marked_[a]) { marked_[a] = 1; touched_.push_back(a); }
            }
        }
        // Ascending order also fixes floating-point reduction order.
        std::sort(touched_.begin(), touched_.end());
        for (int a : touched_) {
            double product = residual[a] ? -1 : 1;
            for (size_t e = g.rp[a]; e < g.rp[a + 1]; ++e) {
                const int j = g.col[e];
                if (fixed[j] < 0) product *= parent_.signed_confidence[j];
            }
            probability[a] = .5 * (1 + product);
        }
    }
    Scores evaluate(const Pattern& delta, double lambda, bool solve) {
        if (!std::isfinite(lambda) || lambda < 0) throw std::invalid_argument("invalid guidance strength");
        load(delta);
        Scores out;
        double variable_gain = 0, check_gain = 0;
        for (auto [j, b] : delta) {
            const double x = (2 * b - 1) * parent_.mean[j];
            // Stable -log sigmoid(-x); equivalent to the normative probability.
            out.j_var = finite(out.j_var + (std::max(x, 0.0) + std::log1p(std::exp(-std::abs(x)))));
            variable_gain += 1 - parent_.confidence[j];
        }
        for (int a : touched_) check_gain += probability[a] - parent_.probability[a];
        out.j_var /= delta.size();
        const double reduction = variable_gain / parent_.free_count +
            (parent_.graph->m ? parent_.beta * (check_gain / parent_.graph->m) : 0);
        out.g_amb = finite(reduction / delta.size());
        out.f_guide = finite(out.j_var - lambda * out.g_amb);
        if (solve) {
            const auto& g = *parent_.graph;
            out.g = parent_.fixed_cost;
            for (auto [j, b] : delta) if (b) out.g = finite(out.g + g.weights[j]);
            std::fill(coverage_.begin(), coverage_.end(), 0);
            for (int a = 0; a < g.m; ++a) if (residual[a])
                for (size_t e = g.rp[a]; e < g.rp[a + 1]; ++e)
                    if (fixed[g.col[e]] < 0) ++coverage_[g.col[e]];
            for (int a = 0; a < g.m; ++a) if (residual[a]) {
                double minimum = std::numeric_limits<double>::infinity();
                for (size_t e = g.rp[a]; e < g.rp[a + 1]; ++e) {
                    const int j = g.col[e];
                    if (fixed[j] < 0) minimum = std::min(minimum, g.weights[j] / coverage_[j]);
                }
                // An empty free neighborhood is a local contradiction, +inf.
                if (std::isinf(minimum)) { out.h = minimum; break; }
                out.h = finite(out.h + minimum);
            }
            out.f_solve = std::isinf(out.h) ? out.h : finite(out.g + out.h);
        }
        return out;
    }
};
}
#endif
