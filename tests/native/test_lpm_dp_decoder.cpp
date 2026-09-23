#define QEC_LPM_DP_TESTING
#include "lpm_dp_decoder.hpp"
#include <cassert>
#include <iostream>
#include <tuple>

namespace qec::lpm_dp_bp {
struct DecoderTestAccess {
    template<class Observer>
    static DecodeResult run(Decoder& decoder, const Bits& syndrome, Observer& observer) {
        return decoder.run(syndrome, observer);
    }
};
}

using namespace qec::lpm_dp_bp;

namespace {

Pattern fixed_pattern(const std::vector<int8_t>& fixed) {
    Pattern out;
    for (size_t j = 0; j < fixed.size(); ++j)
        if (fixed[j] >= 0) out.emplace_back(int(j), int(fixed[j]));
    return out;
}

struct SeenChild {
    double score;
    Pattern full;
    uint64_t id;
};

bool seen_less(const SeenChild& a, const SeenChild& b) {
    if (a.score != b.score) return a.score > b.score;
    if (a.full != b.full) return a.full < b.full;
    return a.id < b.id;
}

struct Observer : NoObserver {
    DecoderSettings settings;
    Rows rows;
    Decoder* decoder = nullptr;
    bool check_reentry = false;
    uint64_t previous_child_id = 0;
    int initial_calls = 0;
    int generated_calls = 0;
    int inherited_calls = 0;
    int contradiction_calls = 0;
    int advanced_calls = 0;
    int fallback_calls = 0;
    int retained_calls = 0;
    int multi_parent_cycles = 0;
    int hard_zero = 0;
    int hard_one = 0;
    size_t max_parents = 0;
    size_t max_generated = 0;
    size_t max_retained_children = 0;
    size_t snapshot_payload = 0;
    std::vector<int> evaluations;
    std::vector<SeenChild> considered_children;
    std::vector<std::tuple<uint64_t, Pattern, uint64_t>> candidate_order;
    std::vector<Reals> fallback_inputs;

    Observer(DecoderSettings value, Rows graph_rows)
        : settings(std::move(value)), rows(std::move(graph_rows)),
          evaluations(size_t(settings.max_cycles), 0) {}

    void initial(const ldpc::decimated::Session& bp, const ldpc::decimated::Advance&) {
        ++initial_calls;
        snapshot_payload = bp.snapshot_payload_bytes();
        if (check_reentry) {
            bool rejected = false;
            try { (void)decoder->decode(Bits(rows.size(), 0)); }
            catch (const std::logic_error&) { rejected = true; }
            assert(rejected);
        }
    }

    void generated(int cycle, size_t parent_index, const ParentState& parent,
                   const qec::lpm_dp::Result& result) {
        ++generated_calls;
        max_parents = std::max(max_parents, parent_index + 1);
        max_generated = std::max(max_generated, result.candidates.size());
        assert(result.parent_id == parent.id);
        assert(result.candidates.size() <= size_t(settings.candidates_per_parent));
        for (size_t i = 1; i < result.candidates.size(); ++i) {
            const auto& a = result.candidates[i - 1];
            const auto& b = result.candidates[i];
            assert(a.local_cost < b.local_cost ||
                   (a.local_cost == b.local_cost && a.selected_order_bits < b.selected_order_bits));
        }
        for (const auto& candidate : result.candidates)
            candidate_order.emplace_back(parent.id, candidate.pattern, candidate.selected_order_bits);
        if (parent_index == 0) considered_children.clear();
        if (parent_index > 0) ++multi_parent_cycles;
        (void)cycle;
    }

    void inherited(int cycle, const ParentState& parent,
                   const qec::lpm_dp::FixationCandidate& candidate, uint64_t child_id,
                   const Pattern& full, const ldpc::decimated::Session& bp) {
        ++inherited_calls;
        ++evaluations[size_t(cycle)];
        assert(child_id > previous_child_id);
        previous_child_id = child_id;
        assert(bp.total_iterations() == 0 && bp.history_count() == 0);
        assert(fixed_pattern(bp.fixed()) == full);
        for (auto [j, bit] : parent.full) assert(bp.fixed()[size_t(j)] == bit);
        for (auto [j, bit] : candidate.pattern) bit ? ++hard_one : ++hard_zero;

        const auto child = bp.snapshot();
        size_t edge = 0;
        for (size_t check = 0; check < rows.size(); ++check) for (int j : rows[check]) {
            if (child.fixed()[size_t(j)] >= 0) {
                assert(child.q()[edge] == 0);
                assert(child.check_to_variable()[edge] == 0);
            } else {
                assert(child.q()[edge] == parent.snapshot.q()[edge]);
                assert(child.check_to_variable()[edge] == parent.snapshot.check_to_variable()[edge]);
            }
            ++edge;
        }
    }

    void contradiction(int, uint64_t, const ldpc::decimated::Session& bp) {
        ++contradiction_calls;
        assert(bp.status() == ldpc::decimated::Status::LocalContradiction);
        assert(bp.total_iterations() == 0 && bp.history_count() == 0);
    }

    void advanced(int, uint64_t, const ldpc::decimated::Session& bp,
                  const ldpc::decimated::Advance& advance) {
        ++advanced_calls;
        assert(advance.actual_iterations <= uint64_t(settings.candidate_iterations));
        if (!advance.valid() && advance.status != ldpc::decimated::Status::LocalContradiction)
            assert(bp.history_count() == size_t(settings.history_window));
    }

    void considered(int, uint64_t id, double score, const Pattern& full,
                    bool competitive, size_t retained_count) {
        considered_children.push_back({score, full, id});
        assert(retained_count <= size_t(settings.retained_parents));
        max_retained_children = std::max(max_retained_children, retained_count);
        if (!competitive) assert(retained_count == size_t(settings.retained_parents));
    }

    void retained(int, size_t old_parent_count, const std::vector<ParentState>& states,
                  bool scratch_empty) {
        ++retained_calls;
        assert(old_parent_count > 0 && scratch_empty);
        assert(states.size() <= size_t(settings.retained_parents));
        assert(std::is_sorted(states.begin(), states.end(), retention_less));
        std::sort(considered_children.begin(), considered_children.end(), seen_less);
        const size_t expected = std::min(size_t(settings.retained_parents), considered_children.size());
        assert(states.size() == expected);
        for (size_t i = 0; i < expected; ++i) {
            assert(states[i].retention == considered_children[i].score);
            assert(states[i].full == considered_children[i].full);
            assert(states[i].id == considered_children[i].id);
        }
        considered_children.clear();
    }

    void fallback(const std::vector<ParentState>& states, const Reals& llrs) {
        ++fallback_calls;
        fallback_inputs.push_back(llrs);
        assert(std::all_of(llrs.begin(), llrs.end(), [](double x) { return std::isfinite(x); }));
        if (!states.empty()) {
            const auto& best = states.front().snapshot;
            for (size_t j = 0; j < llrs.size(); ++j) {
                const double expected = best.fixed()[j] < 0 ? best.llrs()[j]
                    : (best.fixed()[j] ? -std::numeric_limits<double>::max()
                                       : std::numeric_limits<double>::max());
                assert(llrs[j] == expected);
            }
        }
    }
};

DecoderSettings small_settings() {
    DecoderSettings settings;
    settings.history_window = 1;
    settings.initial_iterations = 1;
    settings.candidate_iterations = 2;
    settings.pool_size = 8;
    settings.local_check_limit = 1;
    settings.max_fixations = 1;
    settings.candidates_per_parent = 2;
    settings.retained_mass_target = .9;
    settings.retained_parents = 2;
    settings.max_cycles = 3;
    settings.osd_fallback = false;
    return settings;
}

void settings_and_identity_tests() {
    DecoderSettings defaults;
    defaults.validate();
    assert(KIND == "lpm_dp_bp" && PROFILE == "lpm_dp_bp_v1" && NAME == "lpm_dp_bp_v1");
    assert(ALGORITHM_VERSION == "LPM-DP-BP-1.0");
    assert(defaults.history_window == 8 && defaults.history_clip == 25);
    assert(defaults.pool_size == 32 && defaults.local_check_limit == 2);
    assert(defaults.max_fixations == 4 && defaults.candidates_per_parent == 2);
    assert(defaults.retained_mass_target == .9 && defaults.proposal_clip == 30);
    assert(defaults.initial_iterations == 30 && defaults.candidate_iterations == 20);
    assert(defaults.retained_parents == 8 && defaults.max_cycles == 10);
    assert(defaults.min_sum_scaling == 1 && !defaults.osd_fallback);
    for (int field = 0; field < 5; ++field) {
        auto invalid = defaults;
        if (field == 0) invalid.initial_iterations = 7;
        if (field == 1) invalid.candidate_iterations = 7;
        if (field == 2) invalid.retained_parents = 0;
        if (field == 3) invalid.max_cycles = 0;
        if (field == 4) invalid.min_sum_scaling = 0;
        bool rejected = false;
        try { invalid.validate(); } catch (const std::invalid_argument&) { rejected = true; }
        assert(rejected);
    }
}

void initial_and_zero_tests() {
    auto settings = small_settings();
    Decoder decoder({{0}}, 1, {.1}, {{0}}, settings);
    auto one = decoder.decode({1});
    assert(one.valid && !one.osd_called && one.correction == Bits({1}) && one.prediction == Bits({1}));
    auto zero = decoder.decode({0});
    assert(zero.valid && !zero.osd_called && zero.correction == Bits({0}));
}

void recursive_retention_and_reuse_tests() {
    auto settings = small_settings();
    const Rows rows{{0,1,2,3,4,5},{0,1,2,3,4,5}};
    const Reals probabilities{.1,.13,.17,.21,.27,.31};
    Decoder decoder(rows, 6, probabilities, {{0,1}}, settings);
    Observer first(settings, rows);
    first.decoder = &decoder;
    first.check_reentry = true;
    const auto failed = DecoderTestAccess::run(decoder, {1,0}, first);
    assert(!failed.valid && !failed.osd_called && failed.correction.empty());
    assert(first.generated_calls >= settings.max_cycles);
    assert(first.inherited_calls == first.advanced_calls);
    assert(first.retained_calls == settings.max_cycles);
    assert(first.multi_parent_cycles > 0);
    assert(first.hard_zero > 0 && first.hard_one > 0);
    assert(first.max_generated == size_t(settings.candidates_per_parent));
    assert(first.max_retained_children <= size_t(settings.retained_parents));
    for (int evaluations : first.evaluations)
        assert(evaluations <= settings.retained_parents * settings.candidates_per_parent);

    Observer second(settings, rows);
    const auto repeated = DecoderTestAccess::run(decoder, {1,0}, second);
    assert(repeated.valid == failed.valid && repeated.osd_called == failed.osd_called);
    assert(second.candidate_order == first.candidate_order);
    assert(second.evaluations == first.evaluations);

    const size_t n = probabilities.size();
    const size_t max_pattern_payload = 8 * size_t(settings.max_cycles * settings.max_fixations);
    const size_t bounded_payload =
        2 * size_t(settings.retained_parents) *
            (first.snapshot_payload + max_pattern_payload) +
        first.snapshot_payload + n + rows.size() + 8 * n + max_pattern_payload;
    assert(first.max_retained_children <= size_t(settings.retained_parents));
    std::cout << "representative bounded vector payload <= " << bounded_payload
              << " bytes; max parents=" << settings.retained_parents
              << " max retained children=" << first.max_retained_children << "\n";
}

void contradiction_and_fallback_tests() {
    auto settings = small_settings();
    const Rows rows{{0},{0}};
    Decoder no_osd(rows, 1, {.1}, {}, settings);
    Observer rejected(settings, rows);
    auto failure = DecoderTestAccess::run(no_osd, {1,0}, rejected);
    assert(!failure.valid && !failure.osd_called);
    assert(rejected.inherited_calls >= 1 && rejected.contradiction_calls == rejected.inherited_calls);
    assert(rejected.advanced_calls == 0 && rejected.max_retained_children == 0);

    settings.osd_fallback = true;
    Decoder with_osd(rows, 1, {.1}, {}, settings);
    Observer fallback(settings, rows);
    auto result = DecoderTestAccess::run(with_osd, {1,0}, fallback);
    assert(!result.valid && result.osd_called && fallback.fallback_calls == 1);
    assert(fallback.fallback_inputs.size() == 1);
    assert(fallback.fallback_inputs[0] == Reals({std::log1p(-.1) - std::log(.1)}));

    auto retained_settings = small_settings();
    retained_settings.osd_fallback = true;
    const Rows duplicate_rows{{0,1,2,3,4,5},{0,1,2,3,4,5}};
    Decoder retained_osd(duplicate_rows, 6, {.1,.13,.17,.21,.27,.31}, {}, retained_settings);
    Observer retained_fallback(retained_settings, duplicate_rows);
    result = DecoderTestAccess::run(retained_osd, {1,0}, retained_fallback);
    assert(!result.valid && result.osd_called && retained_fallback.fallback_calls == 1);
    assert(retained_fallback.max_retained_children > 0 &&
           retained_fallback.fallback_inputs.size() == 1);
}

void child_convergence_and_original_validation_test() {
    auto settings = small_settings();
    settings.candidate_iterations = 3;
    const Rows rows{{0,1},{1,2}};
    Decoder decoder(rows, 3, {.1,.1,.1}, {{1}}, settings);
    Observer observer(settings, rows);
    const auto result = DecoderTestAccess::run(decoder, {1,1}, observer);
    assert(result.valid && !result.osd_called && observer.inherited_calls > 0);
    Graph graph(rows, 3, {.1,.1,.1});
    assert(graph.valid(result.correction, {1,1}));
    assert(result.prediction == Bits({result.correction[1]}));
}

void candidate_width_memory_test() {
    auto settings = small_settings();
    settings.max_fixations = 2;
    settings.candidates_per_parent = 4;
    settings.retained_mass_target = .2;
    settings.max_cycles = 2;
    const Rows rows{{0,1,2,3,4,5},{0,1,2,3,4,5}};
    Decoder decoder(rows, 6, {.5,.5,.5,.5,.5,.5}, {}, settings);
    Observer observer(settings, rows);
    const auto result = DecoderTestAccess::run(decoder, {1,0}, observer);
    assert(!result.valid && !result.osd_called);
    assert(observer.max_generated == 4);
    assert(observer.max_retained_children <= 2);
    for (int evaluations : observer.evaluations) assert(evaluations <= 8);
}

} // namespace

int main() {
    settings_and_identity_tests();
    initial_and_zero_tests();
    recursive_retention_and_reuse_tests();
    contradiction_and_fallback_tests();
    child_convergence_and_original_validation_test();
    candidate_width_memory_test();
    std::cout << "LPM-DP BP state machine, warm starts, bounded retention and fallback passed\n";
}
