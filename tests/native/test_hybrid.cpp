#include <cstdlib>
#include <new>
#include <atomic>
static bool fail_next_allocation=false;
void* operator new(std::size_t n) {
    if(fail_next_allocation) {fail_next_allocation=false;throw std::bad_alloc();}
    if(void* p=std::malloc(n ? n : 1)) return p;
    throw std::bad_alloc();
}
void operator delete(void* p) noexcept {std::free(p);}
void operator delete(void* p,std::size_t) noexcept {std::free(p);}
#include "hybrid.hpp"
#include <cassert>
#include <iostream>
using namespace qec::hybrid;
int main() {
    uint64_t compared=0;
    for(int code=0;code<64;++code) {
        Rows rows(2);for(int a=0;a<2;++a) for(int i=0;i<3;++i) if(code&(1<<(a*3+i))) rows[a].push_back(i);
        for(int mode=0;mode<3;++mode) {
            Settings s;s.bp_enabled=mode!=0;s.warm=mode==1;s.expansions={1,2,1};s.iterations={mode?2:0,mode?2:0,mode?2:0};
            s.max_depth=2;s.max_generated_nodes=9;
            Decoder fast(rows,3,{.1,.5,.2},{{0},{1,2}},s),reference(rows,3,{.1,.5,.2},{{0},{1,2}},s,true);
            for(int bits=0;bits<4;++bits) {
                Bits syndrome{uint8_t(bits&1),uint8_t((bits>>1)&1)};
                auto a=fast.decode(syndrome,true),b=reference.decode(syndrome,true);
                assert(a.valid==b.valid && a.correction==b.correction && a.prediction==b.prediction);
                assert(a.summary.exit_reason==b.summary.exit_reason && a.summary.search.generated==b.summary.search.generated);
                assert(a.summary.search.expanded==b.summary.search.expanded && a.summary.bp_iterations==b.summary.bp_iterations);
                assert(a.summary.bp_attempts==b.summary.bp_attempts && a.summary.hint_id==b.summary.hint_id);
                auto t=fast.export_telemetry();assert(t.rounds.size()==a.summary.cycles_started);
                for(const auto& p:t.phases) assert(p.cpu>=0 && p.wall>=0 && p.end>=p.start);
                ++compared;
            }
        }
    }
    // Inconsistent redundant checks prevent goals; inspect the entire tiny tree.
    auto model=std::make_shared<Model>(Rows{{0,1},{0,1}},2,Reals{.1,.2},Rows{});
    Settings settings;settings.max_depth=2;SearchSession search(model,settings);
    search.reset({1,0});search.advance(100);
    const auto& nodes=search.nodes();
    for(const auto& parent:nodes) {
        std::vector<const Node*> children;for(const auto& child:nodes) if(child.parent==parent.id) children.push_back(&child);
        if(children.empty()) continue;
        int a=0;while(!bit(parent.residual,a)) ++a;
        for(int bits=0;bits<4;++bits) {
            bool compatible=true;for(auto [i,b]:parent.key) compatible&=(((bits>>i)&1)==b);
            if(!compatible) continue;
            int parity=0;for(int i:model->ordered[a]) parity^=(bits>>i)&1;
            if(parity!=uint8_t(a==0)) continue;
            int matches=0;for(auto child:children) {
                bool match=true;for(auto [i,b]:child->key) match&=(((bits>>i)&1)==b);matches+=match;
            }
            assert(matches==1);
        }
    }
    // Deterministically inject allocation failure into the next shot's root.
    Decoder d({{0,1},{1,2}},3,{.1,.2,.1},{},settings);
    d.decode({0,0}); Bits syndrome{1,1};
    fail_next_allocation=true;auto failure=d.decode(syndrome,true);
    assert(!failure.valid && failure.summary.exit_reason==ExitReason::ResourceFailure);
    assert(d.decode(syndrome).valid);
    std::cout<<compared<<" native hybrid comparisons, branch partitions and allocation recovery passed\n";
}
