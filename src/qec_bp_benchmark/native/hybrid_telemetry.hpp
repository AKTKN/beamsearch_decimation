#ifndef QEC_HYBRID_TELEMETRY_HPP
#define QEC_HYBRID_TELEMETRY_HPP
#include "hybrid_search.hpp"
#include <ctime>
#include <optional>
#include <string>
namespace qec::hybrid {
inline int64_t clock_ns(clockid_t kind) {
    timespec t{}; if(clock_gettime(kind,&t)!=0) throw std::runtime_error("native clock_gettime failed");
    return int64_t(t.tv_sec)*1000000000+t.tv_nsec;
}
inline int64_t cpu_ns() {return clock_ns(CLOCK_PROCESS_CPUTIME_ID);}
inline int64_t wall_ns() {return clock_ns(CLOCK_MONOTONIC);}
struct Stamp {int64_t cpu=0,wall=0;};
inline Stamp stamp() {return {cpu_ns(),wall_ns()};}
enum class Phase { Search,Transition,Iterations,Osd };
inline const char* phase_name(Phase p) {
    switch(p) {case Phase::Search:return "search";case Phase::Transition:return "bp_transition";
        case Phase::Iterations:return "bp_iterations";case Phase::Osd:return "osd";}
    throw std::logic_error("unknown phase");
}
struct PhaseRecord {
    Phase phase;
    int cycle=-1;
    int64_t cpu=0,wall=0,start=0,end=0;
    uint64_t work=0;
    bool valid=false;
    const char* result="nonconverged";
};
struct RoundRecord {
    int cycle=0;
    int64_t start_cpu=0,start_wall=0,end_cpu=0,end_wall=0;
    uint64_t frontier_before=0,frontier_after=0,guidance_before=0,guidance_after=0;
    uint64_t expansion_budget=0,iteration_budget=0,expanded=0,generated=0,iterations=0;
    std::optional<uint64_t> hint_id,hint_digest,hint_ones,hint_zeros,hint_depth,hint_residual;
    std::optional<double> hint_g,hint_h,hint_f;
    std::optional<uint64_t> residual_before,residual_after;
    bool bp_entered=false,warm=false,node_cap=false,cpu_cap=false;
    const char* result="continue";
};
enum class ExitStage { Search,GuidedBP,Osd,Failed };
enum class ExitReason { ZeroSyndrome,SearchGoal,BPTransition,BPIteration,OsdValid,Inconsistent,OsdInvalid,NumericalFailure,ResourceFailure };
enum class FallbackReason { None,CycleBudget,Exhausted,NodeCap,CpuCap };
enum class LlrSource { None,LastBP,Channel };
inline const char* stage_name(ExitStage s) {
    switch(s) {case ExitStage::Search:return "search";case ExitStage::GuidedBP:return "guided_bp";
        case ExitStage::Osd:return "osd";case ExitStage::Failed:return "failed";}
    throw std::logic_error("invalid exit stage");
}
inline const char* reason_name(ExitReason r) {
    switch(r) {case ExitReason::ZeroSyndrome:return "zero_syndrome";case ExitReason::SearchGoal:return "search_goal_generated";
        case ExitReason::BPTransition:return "bp_transition_valid";case ExitReason::BPIteration:return "bp_iteration_valid";
        case ExitReason::OsdValid:return "osd_valid";case ExitReason::Inconsistent:return "inconsistent_syndrome";
        case ExitReason::OsdInvalid:return "osd_invalid";case ExitReason::NumericalFailure:return "numerical_failure";
        case ExitReason::ResourceFailure:return "resource_failure";}
    throw std::logic_error("invalid exit reason");
}
inline const char* fallback_name(FallbackReason r) {
    switch(r) {case FallbackReason::None:return "";case FallbackReason::CycleBudget:return "cycle_budget";
        case FallbackReason::Exhausted:return "frontier_and_hints_exhausted";
        case FallbackReason::NodeCap:return "node_cap";case FallbackReason::CpuCap:return "prefix_cpu_cap";}
    throw std::logic_error("invalid fallback reason");
}
inline const char* llr_name(LlrSource s) {
    switch(s) {case LlrSource::None:return "";case LlrSource::LastBP:return "last_guided_bp";case LlrSource::Channel:return "clipped_channel";}
    throw std::logic_error("invalid LLR source");
}
struct Summary {
    ExitStage exit_stage=ExitStage::Failed;
    ExitReason exit_reason=ExitReason::ResourceFailure;
    FallbackReason fallback_reason=FallbackReason::None;
    LlrSource osd_llr_source=LlrSource::None;
    uint64_t input_weight=0,cycles_started=0,cycles_completed=0,search_slices=0;
    SearchCounts search;
    uint64_t bp_attempts=0,bp_iterations=0,bp_warm_transitions=0,osd_calls=0;
    std::optional<uint64_t> hint_id,hint_ones,hint_zeros,hint_disagreements;
    bool osd_entered=false,prefix_cap_hit=false,node_cap_hit=false;
    // Null means unmeasured; measured but absent phases are zero.
    std::optional<int64_t> prefix_cpu,prefix_wall;
    int64_t phase_cpu[4]{},phase_wall[4]{};
};
// FNV-1a over little-endian uint32 index + uint8 bit, sorted canonical pairs.
// Diagnostic digest only: node identity/comparison always uses full canonical keys.
inline uint64_t pattern_digest(const Key& key) {
    uint64_t h=14695981039346656037ULL;
    for(auto [i,b]:key) {for(int k=0;k<4;++k) {h^=(uint32_t(i)>>(8*k))&255; h*=1099511628211ULL;} h^=b; h*=1099511628211ULL;}
    return h;
}
struct Telemetry {std::vector<RoundRecord> rounds;std::vector<PhaseRecord> phases;};
}
#endif
