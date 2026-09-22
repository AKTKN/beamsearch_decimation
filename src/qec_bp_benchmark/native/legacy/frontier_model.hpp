#ifndef QEC_FRONTIER_MODEL_HPP
#define QEC_FRONTIER_MODEL_HPP
#include "hybrid_model.hpp"
#include <optional>

namespace qec::frontier {
using qec::hybrid::Bits;using qec::hybrid::Key;using qec::hybrid::Model;
using qec::hybrid::Packed;using qec::hybrid::Reals;using qec::hybrid::Rows;

enum class GoalTest { OnGeneration,OnPop };
enum class RetentionScore { ResidualThenPhysical,PhysicalOnly };
enum class Inheritance { RetainedAncestor,Cold };
enum class HintMode { Soft,None };
enum class StopMode { FirstValid,BoundedImprove };
enum class LlrPolicy { BestRetainedGuided,ChannelOnly,BestRetainedRelease };

struct Settings {
    int64_t max_depth=-1,hint_max_depth=10,det_beam=-1,prefix_cpu_budget_ns=0;
    std::vector<uint64_t> expansions,admissions;
    uint64_t max_expansions=64,max_generated_nodes=4096,max_total_iterations=160;
    uint64_t beam_width=2,max_iterations_per_visit=20,post_solution_cycles=1;
    double alpha=1,clip=25,margin=8;
    bool bp_enabled=true,trace_search_nodes=false,profiling=false;
    GoalTest goal_test=GoalTest::OnGeneration;
    RetentionScore retention=RetentionScore::ResidualThenPhysical;
    Inheritance inheritance=Inheritance::RetainedAncestor;
    HintMode hint_mode=HintMode::Soft;
    StopMode stop_mode=StopMode::FirstValid;
    LlrPolicy llr_policy=LlrPolicy::BestRetainedGuided;

    void validate() const {
        const size_t cycles=expansions.size();
        if(cycles>65536||admissions.size()!=cycles||
           max_depth < -1||hint_max_depth < -1||det_beam < -1||prefix_cpu_budget_ns<0||
           !max_generated_nodes||post_solution_cycles<1)
            throw std::invalid_argument("invalid frontier decoder limits");
        uint64_t total=0;
        for(size_t c=0;c<cycles;++c) {
            if(admissions[c]>beam_width) throw std::invalid_argument("admission budget exceeds beam width");
            if(expansions[c]>UINT64_MAX-total) throw std::invalid_argument("expansion budgets overflow uint64");
            total+=expansions[c];
        }
        if(bp_enabled) {
            if(!beam_width) throw std::invalid_argument("enabled BP requires positive beam width");
        } else if(beam_width||max_total_iterations||
                  std::any_of(admissions.begin(),admissions.end(),[](uint64_t x){return x!=0;})||
                  max_iterations_per_visit)
            throw std::invalid_argument("disabled BP requires zero state and work budgets");
        if(!cycles && max_total_iterations) throw std::invalid_argument("zero cycles require zero global BP work");
        if(!std::isfinite(alpha)||alpha<=0||alpha>1||!std::isfinite(clip)||clip<=0||
           !std::isfinite(margin)||margin<=0)
            throw std::invalid_argument("invalid finite min-sum numeric policy");
    }
};
}
#endif
