#ifndef QEC_LPM_DP_DECODER_HPP
#define QEC_LPM_DP_DECODER_HPP

#include "lpm_dp_candidates.hpp"
#include "decimated_bp.hpp"
#include "osd0_bridge.hpp"
#include <algorithm>
#include <atomic>
#include <limits>
#include <memory>
#include <string_view>

namespace qec::lpm_dp_bp {
using ldpc::hybrid::Bits;
using ldpc::hybrid::Graph;
using ldpc::hybrid::Reals;
using ldpc::hybrid::Rows;
using qec::lpm_dp::Pattern;

inline constexpr std::string_view KIND = "lpm_dp_bp";
inline constexpr std::string_view PROFILE = "lpm_dp_bp_v1";
inline constexpr std::string_view NAME = "lpm_dp_bp_v1";
inline constexpr std::string_view ALGORITHM_VERSION = "LPM-DP-BP-1.0";

struct DecoderSettings : qec::lpm_dp::Settings {
    int initial_iterations = 30;
    int candidate_iterations = 20;
    int retained_parents = 8;
    int max_cycles = 10;
    double min_sum_scaling = 1.0;
    bool osd_fallback = false;

    void validate() const {
        qec::lpm_dp::Settings::validate();
        if (initial_iterations < history_window || candidate_iterations < history_window ||
            retained_parents < 1 || max_cycles < 1 || !std::isfinite(min_sum_scaling) ||
            min_sum_scaling <= 0 || min_sum_scaling > 1)
            throw std::invalid_argument("invalid LPM-DP BP decoder settings");
    }
};

struct Model {
    std::shared_ptr<const Graph> graph;
    Rows observables;

    Model(const Rows& h, int n, const Reals& probabilities, const Rows& a)
        : graph(std::make_shared<Graph>(h, n, probabilities)), observables(a) {
        for (const auto& row : observables) {
            if (!std::is_sorted(row.begin(), row.end()) ||
                std::adjacent_find(row.begin(), row.end()) != row.end())
                throw std::invalid_argument("observable rows must be sorted unique");
            for (int j : row) if (j < 0 || j >= n)
                throw std::invalid_argument("observable index outside model");
        }
    }

    Bits predict(const Bits& correction) const {
        ldpc::hybrid::binary(correction, size_t(graph->n));
        Bits prediction(observables.size(), 0);
        for (size_t a = 0; a < observables.size(); ++a)
            for (int j : observables[a]) prediction[a] ^= correction[size_t(j)];
        return prediction;
    }
};

inline Pattern extend_pattern(const Pattern& ancestor, const Pattern& additional) {
    Pattern out;
    if (ancestor.size() > out.max_size() - additional.size())
        throw std::length_error("LPM-DP fixation pattern exceeds vector capacity");
    out.reserve(ancestor.size() + additional.size());
    size_t i = 0, j = 0;
    while (i < ancestor.size() || j < additional.size()) {
        if (j == additional.size() || (i < ancestor.size() && ancestor[i].first < additional[j].first))
            out.push_back(ancestor[i++]);
        else if (i == ancestor.size() || additional[j].first < ancestor[i].first)
            out.push_back(additional[j++]);
        else
            throw std::invalid_argument("LPM-DP child fixation overlaps its ancestor");
    }
    return out;
}

inline double reliability(const Reals& mean, const std::vector<int8_t>& fixed) {
    if (mean.size() != fixed.size()) throw std::invalid_argument("LPM-DP reliability shape mismatch");
    double sum = 0;
    size_t count = 0;
    for (size_t j = 0; j < mean.size(); ++j) {
        if (fixed[j] < -1 || fixed[j] > 1) throw std::invalid_argument("invalid fixed mask");
        if (fixed[j] >= 0) continue;
        if (!std::isfinite(mean[j])) throw std::invalid_argument("free mean LLR must be finite");
        sum += std::abs(std::tanh(mean[j] / 2));
        ++count;
    }
    return count ? sum / double(count) : 0;
}

struct ParentState {
    uint64_t id = 0;
    ldpc::decimated::Snapshot snapshot;
    Pattern full;
    double retention = 0;

    ParentState(uint64_t identifier, ldpc::decimated::Snapshot saved,
                Pattern complete, double score)
        : id(identifier), snapshot(std::move(saved)), full(std::move(complete)),
          retention(score) {}
};

inline bool retention_less(const ParentState& a, const ParentState& b) {
    if (a.retention != b.retention) return a.retention > b.retention;
    if (a.full != b.full) return a.full < b.full;
    return a.id < b.id;
}

struct DecodeResult {
    bool valid = false;
    bool osd_called = false;
    Bits correction;
    Bits prediction;
    double physical_cost = 0;
};

// Compile-time no-op observer: production exposes no search telemetry. Native
// tests instantiate the same state machine with assertions.
struct NoObserver {
    void initial(const ldpc::decimated::Session&, const ldpc::decimated::Advance&) const {}
    void generated(int, size_t, const ParentState&, const qec::lpm_dp::Result&) const {}
    void inherited(int, const ParentState&, const qec::lpm_dp::FixationCandidate&,
                   uint64_t, const Pattern&, const ldpc::decimated::Session&) const {}
    void contradiction(int, uint64_t, const ldpc::decimated::Session&) const {}
    void advanced(int, uint64_t, const ldpc::decimated::Session&,
                  const ldpc::decimated::Advance&) const {}
    void considered(int, uint64_t, double, const Pattern&, bool, size_t) const {}
    void retained(int, size_t, const std::vector<ParentState>&, bool) const {}
    void fallback(const std::vector<ParentState>&, const Reals&) const {}
};

class Decoder {
    std::shared_ptr<const Model> model_;
    DecoderSettings settings_;
    ldpc::decimated::Session bp_;
    ldpc::hybrid::Osd0Bridge osd_;
    std::atomic_flag busy_ = ATOMIC_FLAG_INIT;

    struct Guard {
        std::atomic_flag& flag;
        explicit Guard(std::atomic_flag& value) : flag(value) {
            if (flag.test_and_set()) throw std::logic_error("LPM-DP-BP-1.0 decoder is non-reentrant");
        }
        ~Guard() { flag.clear(); }
    };

    static DecoderSettings checked(DecoderSettings settings) {
        settings.validate();
        return settings;
    }

    DecodeResult make_result(const Bits& correction, const Bits& syndrome, bool osd_called) const {
        DecodeResult out;
        out.osd_called = osd_called;
        out.valid = model_->graph->valid(correction, syndrome);
        if (!out.valid) return out;
        out.correction = correction;
        out.prediction = model_->predict(correction);
        for (int j = 0; j < model_->graph->n; ++j)
            if (correction[size_t(j)])
                out.physical_cost = ldpc::hybrid::finite(
                    out.physical_cost + model_->graph->weights[size_t(j)]);
        return out;
    }

    ParentState capture(uint64_t id, Pattern full, double score) const {
        if (bp_.history_count() != size_t(settings_.history_window))
            throw std::logic_error("unsuccessful LPM-DP BP state lacks a complete trailing window");
        return ParentState(id, bp_.snapshot(), std::move(full), score);
    }

    size_t retention_position(const std::vector<ParentState>& states, double score,
                              const Pattern& full, uint64_t id) const {
        return size_t(std::lower_bound(states.begin(), states.end(), 0,
            [&](const ParentState& state, int) {
                if (state.retention != score) return state.retention > score;
                if (state.full != full) return state.full < full;
                return state.id < id;
            }) - states.begin());
    }

    template<class Observer> DecodeResult run(const Bits& syndrome, Observer& observer) {
        Guard guard(busy_);
        bp_.reset_from_channel(syndrome);
        const auto initial = bp_.continue_iterations(settings_.initial_iterations);
        observer.initial(bp_, initial);
        if (model_->graph->valid(bp_.decision(), syndrome))
            return make_result(bp_.decision(), syndrome, false);

        std::vector<ParentState> parents, children;
        parents.reserve(size_t(settings_.retained_parents));
        children.reserve(size_t(settings_.retained_parents));
        if (initial.status != ldpc::decimated::Status::LocalContradiction) {
            Reals mean = bp_.clipped_mean_llr();
            parents.push_back(capture(0, {}, reliability(mean, bp_.fixed())));
        }

        uint64_t next_id = 1;
        for (int cycle = 0; cycle < settings_.max_cycles && !parents.empty(); ++cycle) {
            children.clear();
            const size_t old_parent_count = parents.size();
            for (size_t parent_index = 0; parent_index < parents.size(); ++parent_index) {
                const auto& parent = parents[parent_index];
                bp_.restore(parent.snapshot);
                const Reals mean = bp_.clipped_mean_llr();
                const qec::lpm_dp::AveragedParentView view{
                    *model_->graph, syndrome, parent.snapshot.fixed(), mean,
                    parent.snapshot.check_to_variable(), parent.id};
                const auto generated = qec::lpm_dp::generate_candidates(view, settings_);
                observer.generated(cycle, parent_index, parent, generated);
                if (generated.status == qec::lpm_dp::Status::ExistingSolution) {
                    Bits correction(size_t(model_->graph->n), 0);
                    for (auto [j, bit] : parent.full) correction[size_t(j)] = uint8_t(bit);
                    if (!model_->graph->valid(correction, syndrome))
                        throw std::logic_error("LPM-DP existing fixed completion failed original H/s");
                    return make_result(correction, syndrome, false);
                }
                if (generated.status != qec::lpm_dp::Status::Ok) continue;

                for (const auto& candidate : generated.candidates) {
                    if (next_id == std::numeric_limits<uint64_t>::max())
                        throw std::overflow_error("LPM-DP child identifier overflow");
                    const uint64_t child_id = next_id++;
                    Pattern full = extend_pattern(parent.full, candidate.pattern);
                    bp_.inherit_descendant(parent.snapshot, candidate.pattern);
                    observer.inherited(cycle, parent, candidate, child_id, full, bp_);
                    if (bp_.status() == ldpc::decimated::Status::LocalContradiction) {
                        observer.contradiction(cycle, child_id, bp_);
                        continue;
                    }

                    const auto advance = bp_.continue_iterations(settings_.candidate_iterations);
                    observer.advanced(cycle, child_id, bp_, advance);
                    if (model_->graph->valid(bp_.decision(), syndrome))
                        return make_result(bp_.decision(), syndrome, false);
                    if (advance.status == ldpc::decimated::Status::LocalContradiction) continue;

                    Reals mean = bp_.clipped_mean_llr();
                    const double score = reliability(mean, bp_.fixed());
                    const size_t position = retention_position(children, score, full, child_id);
                    const bool competitive = position < size_t(settings_.retained_parents);
                    const size_t retained_count = competitive
                        ? std::min(children.size() + 1, size_t(settings_.retained_parents))
                        : children.size();
                    observer.considered(cycle, child_id, score, full, competitive, retained_count);
                    if (!competitive) continue;

                    if (children.size() == size_t(settings_.retained_parents)) children.pop_back();
                    ParentState saved = capture(child_id, std::move(full), score);
                    children.insert(children.begin() + std::ptrdiff_t(position), std::move(saved));
                }
            }
            parents.clear();
            parents.swap(children);
            observer.retained(cycle, old_parent_count, parents, children.empty());
        }

        if (!settings_.osd_fallback) return DecodeResult{};
        Reals llrs = model_->graph->weights;
        if (!parents.empty()) {
            llrs = parents.front().snapshot.llrs();
            for (size_t j = 0; j < llrs.size(); ++j) if (parents.front().snapshot.fixed()[j] >= 0)
                llrs[j] = parents.front().snapshot.fixed()[j]
                    ? -std::numeric_limits<double>::max() : std::numeric_limits<double>::max();
        }
        observer.fallback(parents, llrs);
        const auto osd = osd_.decode(syndrome, llrs);
        return make_result(osd.correction, syndrome, true);
    }

#ifdef QEC_LPM_DP_TESTING
    friend struct DecoderTestAccess;
#endif

public:
    Decoder(const Rows& h, int n, const Reals& probabilities, const Rows& observables,
            DecoderSettings settings = {})
        : model_(std::make_shared<Model>(h, n, probabilities, observables)),
          settings_(checked(std::move(settings))),
          bp_(model_->graph, settings_.history_window, settings_.history_clip,
              settings_.min_sum_scaling),
          osd_(model_->graph) {}

    DecodeResult decode(const Bits& syndrome) {
        NoObserver observer;
        return run(syndrome, observer);
    }
};

} // namespace qec::lpm_dp_bp
#endif
