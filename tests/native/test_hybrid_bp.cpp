#include "stateful_min_sum.hpp"
#include "osd0_bridge.hpp"
#include <cassert>
#include <iostream>
using namespace ldpc::hybrid;
int main() {
    // Exhaustive tiny matrices, all syndromes, signed/tied supplied LLRs. Compare
    // the bridge with two actual pinned OsdDecoder methods, without any BP call.
    uint64_t comparisons=0;
    for(int code=0;code<64;++code) {
        Rows rows(2); for(int a=0;a<2;++a) for(int i=0;i<3;++i) if(code&(1<<(a*3+i))) rows[a].push_back(i);
        auto graph=std::make_shared<Graph>(rows,3,Reals{.1,.2,.3}); Osd0Bridge bridge(graph);
        ldpc::bp::BpSparse pcm(2,3); for(int a=0;a<2;++a) for(int i:rows[a]) pcm.insert_entry(a,i);
        Reals p{.1,.2,.3}; ldpc::osd::OsdDecoder cs(pcm,ldpc::osd::COMBINATION_SWEEP,0,p);
        ldpc::osd::OsdDecoder zero(pcm,ldpc::osd::OSD_0,0,p);
        for(Reals llr: {Reals{-9,2,-1},Reals{0,0,0},Reals{-0.0,0.0,2},Reals{4,-4,0}})
            for(int syndrome=0;syndrome<4;++syndrome) {
                Bits s{uint8_t(syndrome&1),uint8_t((syndrome>>1)&1)};
                auto out=bridge.decode(s,llr); auto x=cs.decode(s,llr); auto y=zero.decode(s,llr);
                assert(out.correction==x && x==y && out.valid==graph->valid(x,s));
                assert(bridge.candidate_count()==0 && cs.osd_candidate_strings.empty()); ++comparisons;
            }
    }
    std::cout<<comparisons<<" direct pinned OSD comparisons passed\n";
}
