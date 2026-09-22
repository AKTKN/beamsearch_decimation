#ifndef QEC_SEARCH_BP_STAGE3_HPP
#define QEC_SEARCH_BP_STAGE3_HPP
#include "search_bp_search.hpp"

namespace qec::search_bp2 {
struct Stage3Result {
    bool valid = false, initial_success = false;
    Bits correction, prediction;
    ldpc::decimated::Advance bp;
    // Only unsuccessful initial BP needs a donor snapshot for future stages.
    std::optional<ldpc::decimated::Snapshot> parent_state;
    std::optional<ParentScores> parent_scores;
    std::vector<Candidate> candidates;
};

// Worker-owned, non-reentrant Steps 1--4 service; deliberately not a decoder.
// There is no admission, recursive BP execution, fallback, or truth input.
class Stage3 {
    std::shared_ptr<const Model> model_;
    Settings settings_;
    ldpc::decimated::Session bp_;
    static Settings checked(Settings s) { s.validate(); return s; }
public:
    Stage3(const Rows& h, int n, const Reals& p, const Rows& a, Settings settings)
        : model_(std::make_shared<Model>(h, n, p, a)), settings_(checked(settings)),
          bp_(model_->graph, settings_.history_window, settings_.history_clip, settings_.scaling_factor) {}
    // Boundary for independently supplied parent means (already clipped/averaged).
    // C++ orchestration uses expand_parent below to obtain them from the BP API.
    ParentScores summarize(const Bits& syndrome, const Pattern& fixed, Reals means) const {
        return ParentScores(model_->graph, syndrome, fixed, std::move(means), settings_.beta);
    }
    LocalResult expand(const ParentScores& parent, uint64_t parent_id) const {
        if (parent.graph.get() != model_->graph.get()) throw std::invalid_argument("foreign parent model");
        return LocalSearch(parent, settings_, parent_id).run();
    }
    Stage3Result run_initial(const Bits& syndrome, uint64_t parent_id = 0) {
        Stage3Result out;
        bp_.reset_from_channel(syndrome, {}, parent_id);
        out.bp = bp_.continue_iterations(settings_.initial_iterations);
        // Independently validate original H/s; do not trust a convergence flag.
        if (model_->graph->valid(bp_.decision(), syndrome)) {
            out.valid = out.initial_success = true;
            out.correction = bp_.decision(); out.prediction = model_->predict(out.correction);
            return out;
        }
        if (out.bp.status == ldpc::decimated::Status::LocalContradiction) return out;
        out.parent_state.emplace(bp_.snapshot());
        out.parent_scores.emplace(summarize(syndrome, {}, bp_.clipped_mean_llr()));
        auto local = expand(*out.parent_scores, parent_id);
        out.valid = local.valid; out.correction = std::move(local.correction);
        out.candidates = std::move(local.candidates);
        if (out.valid) out.prediction = model_->predict(out.correction);
        return out;
    }
    // Uses a const BP snapshot to reconstruct the same session, without touching
    // its donor. A full window is required before scoring an unsuccessful parent.
    LocalResult expand_parent(const ldpc::decimated::Snapshot& snapshot, uint64_t parent_id) {
        bp_.reset_from_channel(snapshot.syndrome(), {}, snapshot.shot_id());
        bp_.restore(snapshot); // checks model, shot and numerical identity
        if (bp_.history_count() != size_t(settings_.history_window))
            throw std::invalid_argument("parent scoring requires a full trailing history window");
        Pattern fixed;
        for (int j = 0; j < model_->graph->n; ++j)
            if (snapshot.fixed()[j] >= 0) fixed.emplace_back(j, snapshot.fixed()[j]);
        const auto parent = summarize(snapshot.syndrome(), fixed, bp_.clipped_mean_llr());
        return expand(parent, parent_id);
    }
};
}
#endif
