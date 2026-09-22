#define QEC_SEARCH_BP_TESTING
#include "search_bp_decoder.hpp"
#include <cassert>
#include <iostream>
#include <map>

namespace qec::search_bp2 {
struct DecoderTestAccess {
    template<class Observer> static DecodeResult run(Decoder& decoder, const Bits& syndrome, Observer& observer) {
        return decoder.run(syndrome, observer);
    }
};
}
using namespace qec::search_bp2;

PooledCandidate entry(uint64_t id, Pattern full, std::optional<double> solve, double guide) {
    return {size_t(id), {id, full, solve, guide}, full};
}
// Independent full-sort / linear duplicate reference; production uses two heaps.
std::vector<size_t> reference_admit(const std::vector<PooledCandidate>& pool, size_t k) {
    std::vector<size_t> solve, guide, selected;
    for(size_t i=0;i<pool.size();++i) {
        guide.push_back(i); if(pool[i].candidate.f_solve) solve.push_back(i);
    }
    auto key=[&](size_t i) {return std::make_tuple(pool[i].full,pool[i].candidate.parent_id,pool[i].candidate.delta,i);};
    std::sort(solve.begin(),solve.end(),[&](size_t a,size_t b) {
        auto x=*pool[a].candidate.f_solve,y=*pool[b].candidate.f_solve;
        return x!=y?x<y:key(a)<key(b);
    });
    std::sort(guide.begin(),guide.end(),[&](size_t a,size_t b) {
        auto x=pool[a].candidate.f_guide,y=pool[b].candidate.f_guide;
        return x!=y?x<y:key(a)<key(b);
    });
    auto add=[&](size_t i) {
        if(selected.size()==k) return;
        for(size_t j:selected) if(pool[j].full==pool[i].full) return;
        selected.push_back(i);
    };
    for(size_t i=0;i<std::min(k/2,solve.size());++i) add(solve[i]);
    for(size_t i=0;i<std::min(k-k/2,guide.size());++i) add(guide[i]);
    for(size_t i:guide) add(i);
    for(size_t i:solve) add(i);
    return selected;
}
void admission_tests() {
    // Initial quotas select A twice in solve and A/B in guide. Refill must pick
    // C by guide before D, despite D's better solve score. Donor is solve A.
    std::vector<PooledCandidate> pool{
        entry(2,{{0,1}},1,0),entry(0,{{0,1}},2,1),
        entry(1,{{1,1}},10,2),entry(1,{{2,0}},std::nullopt,3),
        entry(0,{{3,1}},3,100)};
    assert(admit(pool,4)==std::vector<size_t>({0,2,3,4}));
    assert(admit(pool,3)==std::vector<size_t>({0,2,3}));
    assert(admit(pool,1)==std::vector<size_t>({0}));
    assert(admit(pool,99).size()==4);
    assert(admit({},5).empty());
    // Canonical full pattern, then parent identifier, wins equal-score ties.
    pool={entry(9,{{2,0}},1,1),entry(4,{{0,1}},1,1),entry(2,{{0,1}},1,1),entry(1,{{1,0}},std::nullopt,1)};
    assert(admit(pool,2)==std::vector<size_t>({2,3}));
    // Same resulting full pattern from DIFFERENT ancestor/delta decompositions.
    pool[1].candidate.delta={{0,1}}; pool[1].full={{0,1},{2,0}};
    pool[2].candidate.delta={{2,0}}; pool[2].full=pool[1].full;
    for(size_t k=1;k<12;++k) assert(admit(pool,k)==reference_admit(pool,k));
    for(int trial=0;trial<80;++trial) {
        pool.clear();
        for(int i=0;i<17;++i) pool.push_back(entry(i%3,{{(i*7+trial)%9,i%2}},
            i%3?std::optional<double>((i+trial)%5):std::nullopt,double((i*3+trial)%7)));
        for(size_t k=1;k<9;++k) assert(admit(pool,k)==reference_admit(pool,k));
    }
}

struct Observer : NoObserver {
    DecoderSettings settings;
    Decoder* decoder=nullptr;
    bool check_reentry=false;
    int pool_calls=0, inherited_calls=0, fallback_calls=0, multi_parent_cycles=0;
    std::vector<int> executions;
    std::vector<std::pair<double,Pattern>> evaluated;
    std::vector<uint64_t> retained_ids;
    Reals fallback_input;
    uint64_t fallback_id=UINT64_MAX;
    explicit Observer(DecoderSettings s):settings(s),executions(size_t(s.max_cycles),0) {}
    void initial(const ldpc::decimated::Session&,const ldpc::decimated::Advance&) {
        if(check_reentry) {
            bool rejected=false;
            try {decoder->decode({0,0});} catch(const std::logic_error&) {rejected=true;}
            assert(rejected);
        }
    }
    void pool(int cycle,const std::vector<BPState>& parents,const std::vector<PooledCandidate>& pool,const std::vector<size_t>& selected) {
        ++pool_calls;
        assert(selected==reference_admit(pool,size_t(settings.k_run)));
        assert(selected.size()<=size_t(settings.k_run));
        if(parents.size()>1) ++multi_parent_cycles;
        if(cycle) {
            assert(parents.size()==retained_ids.size());
            for(size_t i=0;i<parents.size();++i) assert(parents[i].id==retained_ids[i]);
        }
        evaluated.clear();
    }
    void inherited(int cycle,const BPState& parent,const PooledCandidate& candidate,const ldpc::decimated::Session& bp) {
        ++inherited_calls; ++executions[cycle];
        assert(executions[cycle]<=settings.k_run);
        assert(bp.total_iterations()==0 && bp.history_count()==0);
        assert(fixed_pattern(bp.fixed())==candidate.full);
        for(auto [j,b]:parent.full) assert(bp.fixed()[j]==b);
        const auto child=bp.snapshot();
        // All remaining free messages and posterior values are inherited exactly.
        for(size_t j=0;j<child.fixed().size();++j)
            if(child.fixed()[j]<0) assert(child.llrs()[j]==parent.snapshot.llrs()[j]);
        // Snapshot q comparison performed against graph topology in the Python
        // reference as well; no donor mutation is possible through this const API.
        assert(parent.snapshot.iterations()>=size_t(settings.history_window));
    }
    void advanced(int,const ldpc::decimated::Session& bp,const ldpc::decimated::Advance& a) {
        assert(a.actual_iterations<=uint64_t(settings.candidate_iterations));
        if(!a.valid() && a.status!=ldpc::decimated::Status::LocalContradiction) {
            auto means=bp.clipped_mean_llr();
            double sum=0;size_t count=0;
            for(size_t j=0;j<means.size();++j) if(bp.fixed()[j]<0) {sum+=std::abs(std::tanh(means[j]/2));++count;}
            evaluated.push_back({count?sum/count:0,fixed_pattern(bp.fixed())});
        }
    }
    void retained(int,const std::vector<BPState>& states) {
        assert(states.size()<=size_t(settings.k_keep));
        std::sort(evaluated.begin(),evaluated.end(),[](const auto& a,const auto& b) {
            return a.first!=b.first?a.first>b.first:a.second<b.second;
        });
        assert(states.size()==std::min(size_t(settings.k_keep),evaluated.size()));
        retained_ids.clear();
        for(size_t i=0;i<states.size();++i) {
            assert(states[i].r==evaluated[i].first && states[i].full==evaluated[i].second);
            retained_ids.push_back(states[i].id);
        }
    }
    void fallback(const std::vector<BPState>& states,const Reals& llrs) {
        ++fallback_calls; fallback_input=llrs;
        if(!states.empty()) {
            for(const auto& s:states) assert(!retention_less(s,states.front()));
            fallback_id=states.front().id;
            const auto& best=states.front().snapshot;
            for(size_t j=0;j<llrs.size();++j) {
                double expected=best.fixed()[j]<0?best.llrs()[j]:
                    (best.fixed()[j]?-std::numeric_limits<double>::max():std::numeric_limits<double>::max());
                assert(llrs[j]==expected && std::isfinite(llrs[j]));
            }
        }
    }
};

int main() {
    admission_tests();
    assert(std::abs(reliability({-2,0,1e200},{-1,-1,1})-std::tanh(1.)/2)<1e-15);
    assert(reliability({1},{0})==0);
    auto graph=std::make_shared<Graph>(Rows{{0,1,2}},3,Reals{.1,.2,.3});
    ldpc::decimated::Session state_bp(graph,1,25,1);
    std::vector<BPState> states;
    state_bp.reset_from_channel({1},{{0,0}});
    states.emplace_back(4,state_bp.snapshot(),Reals{0,0,0});
    state_bp.reset_from_channel({1},{{1,0}});
    states.emplace_back(3,state_bp.snapshot(),Reals{2,0,2});
    state_bp.reset_from_channel({1},{{0,0}});
    states.emplace_back(2,state_bp.snapshot(),Reals{0,2,2});
    states.emplace_back(1,state_bp.snapshot(),Reals{0,2,2});
    retain(states,2);
    assert(states.size()==2 && states[0].id==1 && states[1].id==2);
    DecoderSettings s;
    s.initial_iterations=3;s.candidate_iterations=3;s.history_window=2;
    s.selected_checks=2;s.local_variables=2;s.max_fixations=1;
    s.k_run=4;s.k_keep=2;s.max_cycles=3;
    const Rows h{{0,1,2,3,4,5},{0,1,2,3,4,5}};
    const Reals p{.1,.13,.17,.21,.27,.31};
    Decoder decoder(h,6,p,{{0,1}},s);
    Observer observer(s);observer.decoder=&decoder;observer.check_reentry=true;
    auto failed=DecoderTestAccess::run(decoder,{1,0},observer);
    assert(!failed.valid && failed.osd_called && !failed.correction_by_search && failed.correction.empty());
    assert(observer.pool_calls==3 && observer.multi_parent_cycles==2);
    assert(observer.fallback_calls==1 && observer.fallback_id!=UINT64_MAX);
    for(int count:observer.executions) assert(count==s.k_run);
    // Zero syndrome exits before any search or OSD; later failed shots are exact.
    auto zero=decoder.decode({0,0});assert(zero.valid && !zero.osd_called && !zero.correction_by_search);
    Observer repeated(s);
    auto again=DecoderTestAccess::run(decoder,{1,0},repeated);
    assert(again.valid==failed.valid && repeated.fallback_input==observer.fallback_input);
    assert(repeated.executions==observer.executions);
    bool bad=false;try {decoder.decode({2,0});}catch(const std::invalid_argument&){bad=true;}assert(bad);
    assert(decoder.decode({0,0}).valid); // exception guard reset

    // Structural contradiction gives no viable initial parent: channel fallback.
    Decoder impossible({{}, {0}},1,{.1},{},s);Observer channel(s);
    auto invalid=DecoderTestAccess::run(impossible,{1,0},channel);
    assert(!invalid.valid && invalid.osd_called && channel.fallback_calls==1 && channel.pool_calls==0);
    assert(channel.fallback_input==Reals({std::log1p(-.1)-std::log(.1)}));
    // Valid initial BP returns without invoking fallback.
    Decoder easy({{0}},1,{.1},{{0}},s);Observer early(s);
    auto success=DecoderTestAccess::run(easy,{1},early);
    assert(success.valid && !success.osd_called && !success.correction_by_search &&
           success.prediction==Bits({1}) && early.fallback_calls==0);
    // Nonconverged initial BP followed by an immediate direct search solution.
    s.initial_iterations=s.candidate_iterations=s.history_window=1;s.max_fixations=2;
    Decoder direct({{0,1},{1,2}},3,{.1,.1,.1},{{1}},s);Observer searched(s);
    auto found=DecoderTestAccess::run(direct,{1,1},searched);
    assert(found.valid && !found.osd_called && found.correction_by_search &&
           searched.inherited_calls==0 && searched.fallback_calls==0);
    s.candidate_iterations=3;s.local_variables=1;s.max_fixations=1;s.selected_checks=1;
    Decoder decimated({{0,1},{1,2}},3,{.1,.1,.1},{{1}},s);Observer bp_success(s);
    auto solved=DecoderTestAccess::run(decimated,{1,1},bp_success);
    assert(solved.valid && !solved.osd_called && !solved.correction_by_search &&
           bp_success.inherited_calls==1 && bp_success.fallback_calls==0);
    Decoder exhausted({{0},{0}},1,{.1},{},s);Observer no_survivors(s);
    auto no_solution=DecoderTestAccess::run(exhausted,{1,0},no_survivors);
    assert(!no_solution.valid && no_solution.osd_called && no_survivors.pool_calls==1);
    assert(no_survivors.fallback_id==UINT64_MAX && no_survivors.fallback_calls==1);
    s.osd_fallback=false;
    Decoder no_osd({{0},{0}},1,{.1},{},s);
    auto disabled=no_osd.decode({1,0});
    assert(!disabled.valid && !disabled.osd_called && !disabled.correction_by_search);
    std::cout << "Global admission/reference, inherited states, 3 recursive cycles, R retention, fallback and non-reentrancy passed\n";
}
