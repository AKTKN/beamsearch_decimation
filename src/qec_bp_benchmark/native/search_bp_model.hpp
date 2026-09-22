#ifndef QEC_SEARCH_BP_MODEL_HPP
#define QEC_SEARCH_BP_MODEL_HPP
#include "hybrid_model.hpp"
#include <optional>

namespace qec::search_bp {
using qec::hybrid::Bits;using qec::hybrid::Key;using qec::hybrid::Model;
using qec::hybrid::Packed;using qec::hybrid::Reals;using qec::hybrid::Rows;

enum class GoalTest { OnGeneration,OnPop };
enum class RetentionScore { ResidualThenPhysical,PhysicalOnly };
enum class Inheritance { RetainedAncestor,Cold };
enum class StopMode { FirstValid,BoundedImprove };
enum class LlrPolicy { BestRetained,ChannelOnly };

struct Settings {
    int64_t max_depth=-1,det_beam=-1,prefix_cpu_budget_ns=0;
    uint64_t max_cycles=8,expansions_per_cycle=8;
    uint64_t beam_width=2,max_iteration=20,post_solution_cycles=1;
    double alpha=1;
    bool bp_enabled=true,trace_search_nodes=false,profiling=false;
    GoalTest goal_test=GoalTest::OnGeneration;
    RetentionScore retention=RetentionScore::ResidualThenPhysical;
    Inheritance inheritance=Inheritance::RetainedAncestor;
    StopMode stop_mode=StopMode::FirstValid;
    LlrPolicy llr_policy=LlrPolicy::BestRetained;

    void validate() const {
        if(max_cycles>65536||max_depth < -1||det_beam < -1||prefix_cpu_budget_ns<0||post_solution_cycles<1)
            throw std::invalid_argument("invalid search_bp decoder limits");
        if(bp_enabled) {
            if(!beam_width) throw std::invalid_argument("enabled BP requires positive beam width");
        } else if(beam_width||max_iteration)
            throw std::invalid_argument("disabled BP requires zero state and work settings");
        if(!std::isfinite(alpha)||alpha<=0||alpha>1)
            throw std::invalid_argument("min-sum scaling must be finite and in (0,1]");
    }
};
}
#endif
