#include "decimated_bp.hpp"
#include <cassert>
#include <iostream>
#include <utility>

using namespace ldpc::decimated;

int main() {
    const ldpc::hybrid::Rows rows{{0, 1, 3}, {1, 2, 4}, {0, 2, 5}, {3, 4, 5}};
    const Reals p{.1, .13, .17, .21, .27, .31};
    auto graph = std::make_shared<Graph>(rows, 6, p);
    unsigned comparisons = 0;
    for (double alpha : {.5, .75, 1.}) {
        for (unsigned word = 1; word < 16; ++word) {
            Bits syndrome(4);
            for (unsigned j = 0; j < 4; ++j) syndrome[j] = (word >> j) & 1;
            for (int budget = 1; budget <= 8; ++budget) {
                ldpc::bp::BpSparse pcm(4, 6, 12);
                for (int a = 0; a < 4; ++a) for (int j : rows[a]) pcm.insert_entry(a, j);
                ldpc::bp::BpDecoder upstream(pcm, p, budget, ldpc::bp::MINIMUM_SUM,
                    ldpc::bp::PARALLEL, alpha, 1, {}, 0, false, ldpc::bp::SYNDROME);
                Session bp(graph, 3, 1.5, alpha);
                bp.reset_from_channel(syndrome);
                auto result = bp.continue_iterations(budget);
                auto expected = upstream.decode(syndrome);
                assert(bp.decision() == expected);
                assert(result.valid() == upstream.converge);
                assert(result.actual_iterations == uint64_t(upstream.iterations));
                for (size_t j = 0; j < p.size(); ++j)
                    assert(std::abs(bp.posterior_llr()[j] - upstream.log_prob_ratios[j]) < 1e-11);
                ++comparisons;
            }
        }
    }
    auto triangle = std::make_shared<Graph>(ldpc::hybrid::Rows{{0, 1}, {1, 2}, {0, 2}},
                                           3, Reals{.1, .19, .27});
    Session split(triangle, 3, .8, .75), whole(triangle, 3, .8, .75);
    split.reset_from_channel({1, 0, 0}, {}, 9);
    whole.reset_from_channel({1, 0, 0}, {}, 9);
    split.continue_iterations(4);
    auto saved = split.snapshot();
    assert(saved.payload_bytes() == 8 * (2 * 6 + 2 * 3 + 3 * 3) + 3 + 3);
    assert(saved.check_to_variable() == split.check_to_variable());
    auto copied = saved;
    auto copy_assigned = split.snapshot(); copy_assigned = saved;
    auto moved = std::move(copied);
    auto move_assigned = split.snapshot(); move_assigned = std::move(copy_assigned);
    assert(moved.check_to_variable() == saved.check_to_variable());
    assert(move_assigned.check_to_variable() == saved.check_to_variable());
    split.continue_iterations(9); whole.continue_iterations(13);
    assert(split.snapshot().q() == whole.snapshot().q());
    assert(split.clipped_mean_llr() == whole.clipped_mean_llr());
    split.restore(moved);
    assert(split.check_to_variable() == saved.check_to_variable());
    split.continue_iterations(9);
    assert(split.clipped_mean_llr() == whole.clipped_mean_llr());
    split.inherit_descendant(move_assigned, {{0, 1}});
    assert(split.history_count() == 0 && split.total_iterations() == 0);
    assert(split.residual_syndrome() == Bits({0, 0, 1}));
    split.continue_iterations(8);
    assert(split.decision()[0] == 1 && split.posterior_llr()[0] < 0);
    auto descendant = split.snapshot();
    for (size_t e = 0; e < triangle->col.size(); ++e)
        if (triangle->col[e] == 0) {
            assert(descendant.q()[e] == 0);
            assert(descendant.check_to_variable()[e] == 0);
        }
    split.reset_from_channel({1, 0, 0}, {{0, 0}, {1, 0}}, 10);
    auto contradiction = split.continue_iterations(100);
    assert(contradiction.status == Status::LocalContradiction && contradiction.actual_iterations == 0);
    bool rejected = false;
    try { split.restore(saved); } catch (const std::invalid_argument&) { rejected = true; }
    assert(rejected);
    split.reset_from_channel({0, 0, 0});
    assert(split.continue_iterations(100).actual_iterations == 0);
    assert(split.history_count() == 0 && split.decision() == Bits({0, 0, 0}));
    std::cout << comparisons << " pinned parallel min-sum comparisons and state/history checks passed\n";
    return 0;
}
