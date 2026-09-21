#include "reference_bp.hpp"
#include <cassert>
#include <cmath>
#include <iostream>
#include <limits>
using namespace ldpc::reference;

int main() {
    const double p = 1 / (1 + std::exp(1.0));
    ReferenceBp odd({{0}}, 1, {p});
    auto zero = odd.decode({0});
    assert(zero.status == Status::CONVERGED && zero.iterations == 0 && zero.history.empty());
    auto one = odd.decode({1}, 3, 25, 2, {}, true);
    assert(one.status == Status::CONVERGED && one.iterations == 1);
    assert(one.last_decision == Bits({1}));
    assert(std::abs(one.beliefs[0] + 24) < 1e-12);
    assert(one.trace[1].check_to_variable == Beliefs({-25}));
    assert(odd.decode({1}, 3, 25, 2, {0}).status == Status::LOCAL_CONTRADICTION);
    assert(odd.decode({1}, 3, 25, 2, {1}).iterations == 0);
    assert(odd.decode({1}, 3, 25, 2, {1}).free_ids.empty());
    ReferenceBp inconsistent({{0, 1}, {0, 1}}, 2, {.5, .5});
    auto history = inconsistent.decode({1, 0}, 5, 25, 2, {}, true);
    assert(history.status == Status::NONCONVERGENCE && history.iterations == 5);
    assert(history.history.size() == 2 && history.trace.size() == 6);
    assert(history.reliability == Beliefs({0, 0}) && history.flips == Bits({0, 0}));
    ReferenceBp saturation({{0}}, 1, {1e-100});
    auto tie = saturation.decode({1}, 2);
    assert(tie.status == Status::NONCONVERGENCE && tie.last_decision == Bits({0}));
    assert(tie.beliefs == Beliefs({0}));
    ReferenceBp isolated({{0}}, 2, {.1, .25});
    auto isolate = isolated.decode({1});
    assert(std::abs(isolate.beliefs[1] - std::log(3)) < 1e-12);
    ReferenceBp empty({{}, {}}, 0, {});
    assert(empty.decode({0, 0}).status == Status::CONVERGED);
    assert(empty.decode({0, 1}).status == Status::LOCAL_CONTRADICTION);
    for (int i = 0; i < 100; ++i) {
        assert(odd.decode({i % 2}).last_decision == Bits({i % 2}));
    }
    bool rejected = false;
    try { ReferenceBp bad({{0, 0}}, 1, {.1}); } catch (const std::invalid_argument &) { rejected = true; }
    assert(rejected);
    rejected = false;
    try { odd.decode({1}, 1, std::numeric_limits<double>::quiet_NaN()); }
    catch (const std::invalid_argument &) { rejected = true; }
    assert(rejected);
    std::cout << "reference_bp native checks passed\n";
}
