#include "search.hpp"
#include <cassert>
int main() {
    qec::Settings cfg; cfg.M=2; cfg.q=1; cfg.K=4; cfg.T0=1;
    qec::ScreenedDecoder d({{0,1}},2,{0.1,0.1},cfg);
    auto a=d.decode({1},true);
    assert(a.valid && a.status=="POST_CONVERGED");
    assert((a.correction==qec::Bits{0,1}));
    assert(a.completions==4 && a.successes==4);
    assert(d.decode({0}).initial_success);
    assert(d.decode({1}).correction==a.correction);
    auto screened=d.screen({1},{0,0},{0,0});
    assert(screened.enumerated==4 && screened.rejected==0);
    bool caught=false;
    try { d.score({1},{0,0},{2,0}); } catch(const std::invalid_argument&) { caught=true; }
    assert(caught);
}
