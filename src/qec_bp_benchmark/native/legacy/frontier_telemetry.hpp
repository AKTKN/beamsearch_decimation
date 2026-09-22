#ifndef QEC_FRONTIER_TELEMETRY_HPP
#define QEC_FRONTIER_TELEMETRY_HPP
#include "frontier_search.hpp"
#include "hybrid_telemetry.hpp"
#include <optional>

namespace qec::frontier {
enum class SolutionSource { ZeroSyndrome,Search,BPTransition,BPIteration,Osd };
inline const char* source_name(SolutionSource value) {
    switch(value) {case SolutionSource::ZeroSyndrome:return "zero_syndrome";case SolutionSource::Search:return "search";
        case SolutionSource::BPTransition:return "bp_transition";case SolutionSource::BPIteration:return "bp_iteration";
        case SolutionSource::Osd:return "osd";}throw std::logic_error("invalid solution source");
}
struct SolutionEvent {
    uint64_t id=0;std::optional<uint32_t> cycle;SolutionSource source=SolutionSource::Search;
    std::optional<uint64_t> node_id,update_id,osd_call_id;Bits correction,prediction;
    double cost=0;std::optional<uint64_t> hint_disagreements;bool improved=false;uint64_t incumbent_after=0;
    int64_t elapsed_cpu=0,elapsed_wall=0;
};
struct PatternRecord {
    uint64_t node_id=0,parent_id=0,admission_ordinal=0;uint32_t cycle=0;
    std::vector<uint32_t> zeros,ones;uint64_t depth=0,rho=0;double g=0,h=0,f=0;
};
struct UpdateRecord {
    uint64_t id=0,node_id=0,donor_lineage=0,lineage_after=0,quota=0,actual=0;
    uint32_t cycle=0,position=0;const char* visit_kind="new";const char* donor_kind="cold_seed";
    std::optional<uint64_t> donor_node,donor_update,residual_before,residual_after,disagreements,rank,solution_event;
    bool usable=false;std::optional<bool> valid;const char* disposition="unusable_error";
    int64_t prepare_cpu=0,prepare_wall=0,iterations_cpu=0,iterations_wall=0;
};
struct MembershipRecord {
    uint32_t cycle=0;uint64_t node_id=0,latest_update=0,rank=0,residual=0,lineage=0;
    bool evaluated=false;double search_f=0;
};
struct CycleRecord {
    uint32_t cycle=0;uint64_t frontier_before=0,frontier_after=0,guidance_before=0,guidance_after=0;
    uint64_t beam_before=0,beam_after=0,expansion_budget=0,expansions=0,generated=0;
    uint64_t pool_budget=0,available_budget=0,proposals=0,pool_size=0,allocated=0,actual=0,admissions=0,visits=0;
    std::optional<uint64_t> best_residual,incumbent;const char* outcome="continued";bool completed=false;
    int64_t span_cpu=0,span_wall=0;
};
struct OsdRecord {
    const char* trigger="cycle_budget";const char* policy="best_retained_guided";
    const char* actual_source="clipped_channel";std::optional<uint64_t> node_id,update_id,solution_event;
    bool valid=false;Reals llrs;int64_t cpu=0,wall=0;
};
struct SearchNodeRecord {
    uint64_t node_id=0;std::optional<uint64_t> parent_id;std::optional<uint32_t> cycle,selected;
    std::vector<uint32_t> zeros;uint64_t depth=0,rho=0;double g=0;std::optional<double> h,f;
    const char* construction="root";const char* final_status="queued";bool admitted=false;
};
struct SearchSummary {SearchCounts counts;uint64_t frontier_final=0,guidance_final=0;bool prefix_cpu_cap_hit=false;
    int64_t cpu=0,wall=0,overshoot=0;};
struct BPSummary {
    uint64_t cycles_started=0,cycles_completed=0,proposals=0,admissions=0,visits=0,planned_tokens=0,iterations=0;
    uint64_t cold_initializations=0,cold_resets=0,ancestor_inheritances=0,own_continuations=0;
    uint64_t snapshot_copies=0,copied_bytes=0,hint_transitions=0,evictions=0,retired=0;
    uint64_t transition_solutions=0,iteration_solutions=0,peak_live_states=0,retained_final=0;
    std::optional<uint64_t> best_node,best_residual;
    int64_t prepare_cpu=0,prepare_wall=0,iterations_cpu=0,iterations_wall=0,rank_cpu=0,rank_wall=0;
};
struct TimingTotals {int64_t solution_cpu=0,solution_wall=0,osd_cpu=0,osd_wall=0;};
struct Telemetry {
    SearchSummary search;BPSummary bp;std::vector<CycleRecord> cycles;std::vector<PatternRecord> patterns;
    std::vector<UpdateRecord> updates;std::vector<MembershipRecord> membership;
    std::vector<SolutionEvent> solutions;std::vector<OsdRecord> osd_calls;
    std::vector<SearchNodeRecord> search_nodes;
    TimingTotals timing;bool profiled=false;
};
}
#endif
