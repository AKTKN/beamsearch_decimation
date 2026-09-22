#ifndef QEC_SEARCH_BP_DECODER_HPP
#define QEC_SEARCH_BP_DECODER_HPP
#include "search_bp_search.hpp"
#include "search_bp_admission.hpp"
#include "osd0_bridge.hpp"
#include <atomic>

namespace qec::search_bp2 {
struct DecoderSettings : Settings {
    int candidate_iterations = 20, k_run = 4, k_keep = 2, max_cycles = 2;
    bool osd_fallback = true;
    void validate() const {
        Settings::validate();
        if (candidate_iterations < history_window || k_run < 1 || k_keep < 1 || k_keep > k_run || max_cycles < 1)
            throw std::invalid_argument("invalid recursive BP budgets");
    }
};
inline Pattern fixed_pattern(const std::vector<int8_t>& fixed) {
    Pattern out;
    for (size_t j = 0; j < fixed.size(); ++j) if (fixed[j] >= 0) out.emplace_back(int(j), fixed[j]);
    return out;
}
inline double reliability(const Reals& mean, const std::vector<int8_t>& fixed) {
    if (mean.size() != fixed.size()) throw std::invalid_argument("reliability shape mismatch");
    double sum = 0; size_t count = 0;
    for (size_t j = 0; j < mean.size(); ++j) {
        if (fixed[j] < -1 || fixed[j] > 1) throw std::invalid_argument("invalid fixed mask");
        if (fixed[j] >= 0) continue;
        if (!std::isfinite(mean[j])) throw std::invalid_argument("free mean LLR must be finite");
        sum += std::abs(std::tanh(mean[j] / 2)); ++count;
    }
    return count ? sum / count : 0;
}
struct BPState {
    uint64_t id;
    ldpc::decimated::Snapshot snapshot;
    Pattern full;
    Reals mean;
    double r;
    BPState(uint64_t identifier, ldpc::decimated::Snapshot saved, Reals means)
        : id(identifier), snapshot(std::move(saved)), full(fixed_pattern(snapshot.fixed())),
          mean(std::move(means)), r(reliability(mean, snapshot.fixed())) {}
};
inline bool retention_less(const BPState& a, const BPState& b) {
    if (a.r != b.r) return a.r > b.r;
    if (a.full != b.full) return a.full < b.full;
    return a.id < b.id;
}
inline void retain(std::vector<BPState>& states, size_t k_keep) {
    const size_t keep = std::min(k_keep, states.size());
    std::partial_sort(states.begin(), states.begin() + keep, states.end(), retention_less);
    // erase immediately destroys discarded snapshots; retained vectors move.
    states.erase(states.begin() + keep, states.end());
}
inline Reals fallback_llrs(const BPState& state) {
    Reals llrs = state.snapshot.llrs(); // final signed posterior, not history mean
    for (size_t j = 0; j < llrs.size(); ++j) {
        if (state.snapshot.fixed()[j] >= 0)
            llrs[j] = state.snapshot.fixed()[j] ? -std::numeric_limits<double>::max()
                                              : std::numeric_limits<double>::max();
    }
    return llrs;
}
struct DecodeResult {
    bool valid = false, osd_called = false, correction_by_search = false;
    Bits correction, prediction;
    double physical_cost = 0;
};

// Compile-time no-op observer. The production binding exports only DecodeResult.
// Native tests instantiate the same loop with assertions, without a runtime
// telemetry mode, stored records, Python callbacks or production observability API.
struct NoObserver {
    void initial(const ldpc::decimated::Session&, const ldpc::decimated::Advance&) const {}
    void pool(int, const std::vector<BPState>&, const std::vector<PooledCandidate>&,
              const std::vector<size_t>&) const {}
    void inherited(int, const BPState&, const PooledCandidate&, const ldpc::decimated::Session&) const {}
    void advanced(int, const ldpc::decimated::Session&, const ldpc::decimated::Advance&) const {}
    void retained(int, const std::vector<BPState>&) const {}
    void fallback(const std::vector<BPState>&, const Reals&) const {}
};
class Decoder {
    std::shared_ptr<const Model> model_;
    DecoderSettings settings_;
    ldpc::decimated::Session bp_;
    ldpc::hybrid::Osd0Bridge osd_;
    std::atomic_flag busy_ = ATOMIC_FLAG_INIT;
    struct Guard {
        std::atomic_flag& flag;
        explicit Guard(std::atomic_flag& f) : flag(f) {
            if (flag.test_and_set()) throw std::logic_error("SEARCH-BP-2.1 decoder is non-reentrant");
        }
        ~Guard() { flag.clear(); }
    };
    static DecoderSettings checked(DecoderSettings s) { s.validate(); return s; }
    DecodeResult result(const Bits& correction, const Bits& syndrome, bool osd_called,
                        bool correction_by_search = false) const {
        DecodeResult out; out.osd_called = osd_called;
        out.correction_by_search = correction_by_search;
        out.valid = model_->graph->valid(correction, syndrome);
        if (out.valid) {
            out.correction = correction; out.prediction = model_->predict(correction);
            for (int j = 0; j < model_->graph->n; ++j)
                if (correction[j]) out.physical_cost = finite(out.physical_cost + model_->graph->weights[j]);
        }
        return out;
    }
    BPState capture(uint64_t id) const {
        if (bp_.history_count() != size_t(settings_.history_window))
            throw std::logic_error("unsuccessful BP state lacks a complete trailing window");
        return BPState(id, bp_.snapshot(), bp_.clipped_mean_llr());
    }
    template<class Observer> DecodeResult run(const Bits& syndrome, Observer& observer) {
        Guard guard(busy_);
        // All shot-owned states/pools below die on return or exception. The same
        // session buffer is reused for each child, always restoring its donor.
        bp_.reset_from_channel(syndrome);
        auto initial = bp_.continue_iterations(settings_.initial_iterations);
        observer.initial(bp_, initial);
        if (model_->graph->valid(bp_.decision(), syndrome)) return result(bp_.decision(), syndrome, false);
        std::vector<BPState> parents, descendants;
        parents.reserve(settings_.k_keep); descendants.reserve(settings_.k_run);
        if (initial.status != ldpc::decimated::Status::LocalContradiction) parents.push_back(capture(0));
        uint64_t next_id = 1;
        for (int cycle = 0; cycle < settings_.max_cycles && !parents.empty(); ++cycle) {
            std::vector<PooledCandidate> admitted;
            {
                std::vector<PooledCandidate> pool;
                for (size_t b = 0; b < parents.size(); ++b) {
                    const auto& parent = parents[b];
                    ParentScores summary(model_->graph, syndrome, parent.full, parent.mean, settings_.beta);
                    auto local = LocalSearch(summary, settings_, parent.id).run();
                    if (local.valid) return result(local.correction, syndrome, false, true);
                    if (local.candidates.size() > pool.max_size() - pool.size())
                        throw std::length_error("global candidate pool exceeds vector capacity");
                    // Reserve the first batch; subsequent appends keep vector's
                    // geometric growth instead of reallocating once per parent.
                    if (pool.empty()) pool.reserve(local.candidates.size());
                    for (auto& c : local.candidates) {
                        Pattern full = extend_pattern(parent.full, c.delta);
                        pool.push_back({b, std::move(c), std::move(full)});
                    }
                }
                const auto selected = admit(pool, size_t(settings_.k_run));
                observer.pool(cycle, parents, pool, selected);
                admitted.reserve(selected.size());
                for (size_t i : selected) admitted.push_back(std::move(pool[i]));
            } // Release all unadmitted patterns, rankings and search data before BP.
            descendants.clear();
            for (const auto& candidate : admitted) {
                const auto& parent = parents[candidate.parent_index];
                bp_.inherit_descendant(parent.snapshot, candidate.candidate.delta);
                observer.inherited(cycle, parent, candidate, bp_);
                const auto advance = bp_.continue_iterations(settings_.candidate_iterations);
                observer.advanced(cycle, bp_, advance);
                if (model_->graph->valid(bp_.decision(), syndrome)) return result(bp_.decision(), syndrome, false);
                // A structural contradiction has no feasible descendant and no
                // completed history. It cannot be a retained BP instance.
                if (advance.status != ldpc::decimated::Status::LocalContradiction)
                    descendants.push_back(capture(next_id++));
            }
            retain(descendants, size_t(settings_.k_keep));
            parents.clear(); // release previous generation before moving the next
            parents.swap(descendants);
            observer.retained(cycle, parents);
        }
        if (!settings_.osd_fallback) return DecodeResult{};
        // Retention leaves descending R order with deterministic pattern/id ties.
        Reals llrs = parents.empty() ? model_->graph->weights : fallback_llrs(parents.front());
        observer.fallback(parents, llrs);
        const auto osd = osd_.decode(syndrome, llrs); // exactly one direct native call
        return result(osd.correction, syndrome, true);
    }
#ifdef QEC_SEARCH_BP_TESTING
    friend struct DecoderTestAccess;
#endif
public:
    Decoder(const Rows& h, int n, const Reals& p, const Rows& a, DecoderSettings settings)
        : model_(std::make_shared<Model>(h, n, p, a)), settings_(checked(std::move(settings))),
          bp_(model_->graph, settings_.history_window, settings_.history_clip, settings_.scaling_factor),
          osd_(model_->graph) {}
    DecodeResult decode(const Bits& syndrome) { NoObserver observer; return run(syndrome, observer); }
};
}
#endif
