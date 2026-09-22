#include "search_bp_stage3.hpp"
#include <cassert>
#include <iostream>
using namespace qec::search_bp2;

int main() {
    Settings s;
    s.initial_iterations = 5; s.history_window = 3; s.history_clip = .8; s.scaling_factor = .75;
    const Rows h{{0,1},{1,2},{0,2}};
    const Reals p{.1,.19,.27};
    Stage3 service(h, 3, p, {{0,1,2}}, s);
    auto failed = service.run_initial({1,0,0}, 21);
    assert(!failed.valid && failed.bp.actual_iterations == 5);
    auto saved = *failed.parent_state;
    const auto q = saved.q();
    const auto means = failed.parent_scores->mean;
    auto again = service.expand_parent(saved, 21);
    assert(again.candidates.size() == failed.candidates.size());
    assert(saved.q() == q && saved.history_count() == 3);
    for(size_t i=0; i<again.candidates.size(); ++i) {
        assert(again.candidates[i].delta == failed.candidates[i].delta);
        assert(again.candidates[i].f_guide == failed.candidates[i].f_guide);
    }
    auto zero = service.run_initial({0,0,0});
    assert(zero.valid && zero.initial_success && zero.candidates.empty() && !zero.parent_state);
    assert(service.run_initial({1,0,0}).parent_scores->mean == means);

    // Independent closed-form zero-LLR scoring: all probabilities are 1/2
    // until a check loses its final free neighbor.
    auto parent = service.summarize({1,0,0}, {}, {0,0,0});
    Scorer scratch(parent);
    auto score = scratch.evaluate({{0,0}}, 1, true);
    assert(std::abs(score.j_var-std::log(2.)) < 1e-15);
    assert(std::abs(score.g_amb-1./3) < 1e-15);
    assert(std::abs(score.f_guide-(std::log(2.)-1./3)) < 1e-15);
    assert(score.g == 0 && std::abs(score.h-std::log(.81/.19)) < 1e-14);
    assert(parent.residual == Bits({1,0,0}) && parent.fixed == std::vector<int8_t>({-1,-1,-1}));
    assert(select_checks(parent, 2) == std::vector<int>({0,1}));
    assert(select_variables(parent, 0, 1) == std::vector<int>({0}));

    s.selected_checks=1; s.local_variables=1; s.max_fixations=3;
    Stage3 refresh({{0},{1},{2}}, 3, {.1,.2,.3}, {}, s);
    auto summary = refresh.summarize({1,1,1}, {}, {-3,0,4});
    auto solution = refresh.expand(summary, 3);
    assert(solution.valid && solution.correction == Bits({1,1,1}));
    assert(solution.candidates.size() == 3);
    assert(solution.candidates[1].delta == Pattern({{1,1},{2,1}}));
    s.local_variables=3; s.local_variable_policy="fixed_root";
    Stage3 fixed({{0},{1},{2}}, 3, {.1,.2,.3}, {}, s);
    auto stopped = fixed.expand(fixed.summarize({1,1,1}, {}, {-3,0,4}), 3);
    assert(!stopped.valid && stopped.candidates.size() == 1);
    assert(pattern_bound(3,3) == 26 && pattern_bound(4,2) == 32);
    auto probes = fixed.expand(fixed.summarize({0,0,0}, {}, {0,0,0}), 4);
    assert(probes.candidates.size() == 2 && !probes.candidates[0].f_solve);
    bool rejected=false;
    try { scratch.evaluate({{0,0},{0,1}}, 1, true); }
    catch(const std::invalid_argument&) { rejected=true; }
    assert(rejected);
    std::cout << "Stage-3 formulas, both local policies, ownership, reset and full-solution validation passed\n";
}
