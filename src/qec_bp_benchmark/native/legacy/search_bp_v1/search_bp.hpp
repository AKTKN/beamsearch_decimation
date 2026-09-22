#ifndef QEC_SEARCH_BP_HPP
#define QEC_SEARCH_BP_HPP
#include "search_bp_telemetry.hpp"
#include "hard_fixed_min_sum.hpp"
#include "osd0_bridge.hpp"
#include <atomic>

namespace qec::search_bp {
struct Result {
    bool valid=false;Bits correction,prediction;double cost=0;
    const char* status="resource_error";const char* prefix_stop_reason="resource_error";
    std::optional<SolutionSource> first_source,winner_source;
    std::optional<uint64_t> first_event,winner_event;bool osd_entered=false;
};

class Decoder {
    struct Candidate {
        uint64_t node=0,latest_update=0;HardSnapshot state;
        uint64_t residual=0;bool evaluated=false;size_t update_index=SIZE_MAX;
    };
    std::shared_ptr<const Model> model_;Settings settings_;SearchSession search_;
    HardFixedMinSumSession bp_;ldpc::hybrid::Osd0Bridge osd_;
    std::atomic_flag busy_=ATOMIC_FLAG_INIT;uint64_t shot_token_=0;
    Bits syndrome_;Telemetry telemetry_;Result result_;std::vector<Candidate> beam_;
    std::optional<Bits> incumbent_;std::optional<uint64_t> incumbent_event_;
    int64_t prefix_start_=0,prefix_wall_start_=0;
    struct Guard {std::atomic_flag& f;explicit Guard(std::atomic_flag& x):f(x){if(f.test_and_set())throw std::logic_error("search_bp decoder is non-reentrant");}~Guard(){f.clear();}};

    bool cap() const {return settings_.prefix_cpu_budget_ns&&qec::hybrid::cpu_ns()-prefix_start_>=settings_.prefix_cpu_budget_ns;}
    qec::hybrid::Stamp measured_stamp() const {return settings_.profiling?qec::hybrid::stamp():qec::hybrid::Stamp{};}
    int64_t measured_cpu(const qec::hybrid::Stamp& value) const {return settings_.profiling?qec::hybrid::cpu_ns()-value.cpu:0;}
    int64_t measured_wall(const qec::hybrid::Stamp& value) const {return settings_.profiling?qec::hybrid::wall_ns()-value.wall:0;}
    bool better(const Bits& candidate,const Bits& incumbent) const {
        double a=model_->cost(candidate),b=model_->cost(incumbent);return a<b||(a==b&&candidate<incumbent);
    }
    bool submit(const Bits& bits,SolutionSource source,std::optional<uint32_t> cycle,
                std::optional<uint64_t> node,std::optional<uint64_t> update,std::optional<uint64_t> osd,
                std::optional<uint64_t> violations) {
        auto timing=measured_stamp();
        if(!model_->graph->valid(bits,syndrome_)) {
            telemetry_.timing.solution_cpu+=measured_cpu(timing);
            telemetry_.timing.solution_wall+=measured_wall(timing);return false;}
        SolutionEvent event;event.id=telemetry_.solutions.size();event.cycle=cycle;event.source=source;
        event.node_id=node;event.update_id=update;event.osd_call_id=osd;event.correction=bits;
        event.prediction=model_->predict(bits);event.cost=model_->cost(bits);event.fixed_assignment_violations=violations;
        event.improved=!incumbent_||better(bits,*incumbent_);
        if(event.improved) {incumbent_=bits;incumbent_event_=event.id;}
        event.incumbent_after=*incumbent_event_;
        if(settings_.profiling){event.elapsed_cpu=qec::hybrid::cpu_ns()-prefix_start_;
            event.elapsed_wall=qec::hybrid::wall_ns()-prefix_wall_start_;}telemetry_.solutions.push_back(std::move(event));
        if(!result_.first_event) {result_.first_event=telemetry_.solutions.back().id;result_.first_source=source;}
        telemetry_.timing.solution_cpu+=measured_cpu(timing);
        telemetry_.timing.solution_wall+=measured_wall(timing);
        return settings_.stop_mode==StopMode::FirstValid;
    }
    uint64_t violations(const Bits& bits,uint64_t node_id) const {
        uint64_t count=0;for(auto [i,b]:search_.node(node_id).order_pattern) count+=bits[size_t(i)]!=b;return count;
    }
    bool candidate_less(const Candidate& a,const Candidate& b) const {
        if(settings_.retention==RetentionScore::ResidualThenPhysical&&a.residual!=b.residual) return a.residual<b.residual;
        const auto& x=search_.node(a.node);const auto& y=search_.node(b.node);
        return x.f<y.f||(x.f==y.f&&a.node<b.node);
    }
    void add_pattern(uint64_t node_id,uint32_t cycle) {
        const auto& node=search_.node(node_id);PatternRecord row;row.node_id=node_id;row.parent_id=node.parent;
        row.admission_ordinal=telemetry_.patterns.size();row.cycle=cycle;row.depth=node.depth;row.rho=node.rho;
        row.g=node.g;row.h=node.h;row.f=node.f;
        for(auto [i,b]:node.order_pattern) (b?row.ones:row.zeros).push_back(uint32_t(i));
        telemetry_.patterns.push_back(std::move(row));
    }
    const Candidate* nearest_donor(const std::vector<Candidate>& frozen,uint64_t node) const {
        const Candidate* best=nullptr;
        for(const auto& candidate:frozen) if(search_.is_ancestor(candidate.node,node)&&
            (!best||search_.node(candidate.node).depth>search_.node(best->node).depth)) best=&candidate;
        return best;
    }
    void reconcile(std::vector<Candidate>& working,const std::vector<Candidate>& frozen,uint32_t cycle) {
        for(const auto& old:frozen) if(std::none_of(working.begin(),working.end(),[&](const Candidate& c){return c.node==old.node;})) {
            Candidate carried=old;carried.evaluated=false;working.push_back(std::move(carried));
        }
        std::sort(working.begin(),working.end(),[this](const Candidate& a,const Candidate& b){return candidate_less(a,b);});
        for(size_t rank=0;rank<working.size();++rank) if(working[rank].update_index!=SIZE_MAX)
            telemetry_.updates[working[rank].update_index].rank=rank;
        if(working.size()>settings_.beam_width) {
            for(size_t i=size_t(settings_.beam_width);i<working.size();++i) {
                ++telemetry_.bp.evictions;if(working[i].update_index!=SIZE_MAX)
                    telemetry_.updates[working[i].update_index].disposition="evicted";
            }
            working.resize(size_t(settings_.beam_width));
        }
        beam_.clear();beam_.reserve(working.size());
        for(size_t rank=0;rank<working.size();++rank) {
            auto candidate=std::move(working[rank]);
            if(candidate.update_index!=SIZE_MAX) telemetry_.updates[candidate.update_index].disposition="retained";
            telemetry_.membership.push_back({cycle,candidate.node,candidate.latest_update,rank,candidate.residual,
                candidate.state.iterations,candidate.evaluated,search_.node(candidate.node).f});
            candidate.evaluated=false;candidate.update_index=SIZE_MAX;beam_.push_back(std::move(candidate));
        }
        telemetry_.bp.peak_live_states=std::max<uint64_t>(telemetry_.bp.peak_live_states,
            uint64_t(frozen.size()+working.size()));
    }
    bool future_work(size_t next_cycle) const {
        for(size_t c=next_cycle;c<settings_.max_cycles;++c) {
            if(search_.frontier_size()&&((settings_.goal_test==GoalTest::OnPop)||
               settings_.expansions_per_cycle)) return true;
            if(settings_.bp_enabled&&settings_.max_iteration&&
               (!beam_.empty()||search_.guidance_size())) return true;
        }
        return false;
    }
    Result finish_incumbent(const char* reason) {
        result_.prefix_stop_reason=reason;
        if(incumbent_) {result_.valid=true;result_.status="valid";result_.correction=*incumbent_;
            result_.prediction=model_->predict(*incumbent_);result_.cost=model_->cost(*incumbent_);
            result_.winner_event=incumbent_event_;result_.winner_source=telemetry_.solutions[*incumbent_event_].source;}
        telemetry_.search.counts=search_.counts;telemetry_.search.frontier_final=search_.frontier_size();
        telemetry_.search.guidance_final=search_.guidance_size();telemetry_.bp.retained_final=beam_.size();
        if(telemetry_.search.prefix_cpu_cap_hit&&settings_.prefix_cpu_budget_ns)
            telemetry_.search.overshoot=std::max<int64_t>(0,qec::hybrid::cpu_ns()-prefix_start_-settings_.prefix_cpu_budget_ns);
        if(!beam_.empty()){telemetry_.bp.best_node=beam_[0].node;telemetry_.bp.best_residual=beam_[0].residual;}
        if(settings_.trace_search_nodes&&telemetry_.search_nodes.empty()) {
            for(const auto& node:search_.nodes()) {
                SearchNodeRecord row;row.node_id=node.id;if(node.parent!=UINT64_MAX)row.parent_id=node.parent;
                if(node.selected>=0)row.selected=uint32_t(node.selected);
                if(node.generation_cycle!=UINT32_MAX)row.cycle=node.generation_cycle;
                row.zeros=search_.added_zeros(node.id);
                row.depth=node.depth;row.rho=node.rho;row.g=node.g;row.admitted=node.admitted;
                if(node.construction!=ConstructionStatus::LocallyInfeasible){row.h=node.h;row.f=node.f;}
                switch(node.construction){case ConstructionStatus::Root:row.construction="root";break;
                    case ConstructionStatus::Feasible:row.construction="feasible";break;case ConstructionStatus::Goal:row.construction="goal";break;
                    case ConstructionStatus::LocallyInfeasible:row.construction="locally_infeasible";break;
                    case ConstructionStatus::DepthLimited:row.construction="depth_limited";break;}
                switch(node.search_status){case SearchStatus::Queued:row.final_status="queued";break;case SearchStatus::Expanded:row.final_status="expanded";break;
                    case SearchStatus::PartiallyExpanded:row.final_status="partially_expanded";break;case SearchStatus::Goal:row.final_status="goal";break;
                    case SearchStatus::LocallyInfeasible:row.final_status="locally_infeasible";break;case SearchStatus::DepthLimited:row.final_status="depth_limited";break;
                    case SearchStatus::DetBeamDiscarded:row.final_status="det_beam_discarded";break;}
                telemetry_.search_nodes.push_back(std::move(row));
            }
        }
        return result_;
    }
public:
    Decoder(const Rows& rows,int n,const Reals& probabilities,const Rows& observables,Settings settings,bool reference=false):
        model_(std::make_shared<Model>(rows,n,probabilities,observables)),settings_(std::move(settings)),
        search_(model_,settings_,reference),bp_(model_->graph,settings_.alpha),osd_(model_->graph) {settings_.validate();}
    Result decode(const Bits& syndrome) {
        Guard guard(busy_);result_={};telemetry_={};telemetry_.profiled=settings_.profiling;
        beam_.clear();incumbent_.reset();incumbent_event_.reset();
        // Clear the prior shot before every early-return path.  A zero syndrome and
        // direct-CS0 diagnostic construct no root and therefore report true zeros.
        search_.clear();
        ldpc::hybrid::binary(syndrome,size_t(model_->graph->m));syndrome_=syndrome;++shot_token_;
        prefix_start_=(settings_.profiling||settings_.prefix_cpu_budget_ns)?qec::hybrid::cpu_ns():0;
        prefix_wall_start_=settings_.profiling?qec::hybrid::wall_ns():0;
        if(model_->graph->inconsistent_empty_row(syndrome)) {result_.status="model_error";return finish_incumbent("model_error");}
        const bool zero=std::none_of(syndrome.begin(),syndrome.end(),[](uint8_t x){return x!=0;});
        if(zero) {Bits correction(size_t(model_->graph->n),0);submit(correction,SolutionSource::ZeroSyndrome,std::nullopt,
            std::nullopt,std::nullopt,std::nullopt,std::nullopt);return finish_incumbent("zero_syndrome");}
        try {
            if(settings_.max_cycles) search_.reset(syndrome);
            std::optional<uint32_t> first_cycle;
            for(uint32_t cycle=0;cycle<settings_.max_cycles;++cycle) {
                auto cycle_timing=measured_stamp();
                CycleRecord row;row.cycle=cycle;row.frontier_before=search_.frontier_size();row.guidance_before=search_.guidance_size();
                row.beam_before=beam_.size();row.expansion_budget=settings_.expansions_per_cycle;
                row.pool_budget=settings_.max_iteration;
                ++telemetry_.bp.cycles_started;auto before=search_.counts;search_.set_cycle(cycle);
                auto search_timing=measured_stamp();auto solution_cpu=telemetry_.timing.solution_cpu;
                auto solution_wall=telemetry_.timing.solution_wall;
                auto search_result=search_.advance(settings_.expansions_per_cycle,[this](){return cap();},
                    [&,cycle](const Bits& bits,uint64_t node){
                        bool stop=submit(bits,SolutionSource::Search,cycle,node,std::nullopt,std::nullopt,std::nullopt);
                        if(!first_cycle) first_cycle=cycle;
                        return stop;});
                telemetry_.search.cpu+=measured_cpu(search_timing)-(telemetry_.timing.solution_cpu-solution_cpu);
                telemetry_.search.wall+=measured_wall(search_timing)-(telemetry_.timing.solution_wall-solution_wall);
                row.expansions=search_.counts.expanded-before.expanded;row.generated=search_.counts.generated-before.generated;
                if(search_result.cpu_cap) {telemetry_.search.prefix_cpu_cap_hit=true;row.outcome="prefix_cpu_cap";
                    row.frontier_after=search_.frontier_size();row.guidance_after=search_.guidance_size();row.beam_after=beam_.size();
                    row.span_cpu=measured_cpu(cycle_timing);row.span_wall=measured_wall(cycle_timing);
                    telemetry_.cycles.push_back(row);return fallback_or_finish("prefix_cpu_cap");}
                if(search_result.stop) {row.outcome="first_valid";row.frontier_after=search_.frontier_size();row.guidance_after=search_.guidance_size();
                    row.beam_after=beam_.size();row.span_cpu=measured_cpu(cycle_timing);
                    row.span_wall=measured_wall(cycle_timing);telemetry_.cycles.push_back(row);return finish_incumbent("first_valid");}

                std::vector<Candidate> frozen=std::move(beam_);beam_.clear();
                auto proposed=search_.proposals(settings_.beam_width);telemetry_.bp.proposals+=proposed.size();row.proposals=proposed.size();
                std::vector<uint64_t> ids;ids.reserve(frozen.size()+proposed.size());
                for(const auto& c:frozen) ids.push_back(c.node);
                ids.insert(ids.end(),proposed.begin(),proposed.end());
                std::sort(ids.begin(),ids.end());ids.erase(std::unique(ids.begin(),ids.end()),ids.end());row.pool_size=ids.size();
                row.available_budget=settings_.bp_enabled?settings_.max_iteration:0;
                std::vector<Candidate> working;working.reserve(ids.size());bool terminal=false,cpu_stop=false;
                const size_t rotate=ids.empty()?0:size_t(cycle)%ids.size();
                for(size_t turn=0;turn<ids.size();++turn) {
                    size_t position=(rotate+turn)%ids.size();uint64_t id=ids[position];
                    auto old=std::find_if(frozen.begin(),frozen.end(),[&](const Candidate& c){return c.node==id;});
                    const bool fresh=old==frozen.end();
                    const uint64_t quota=settings_.bp_enabled?settings_.max_iteration:0;
                    if(!quota) continue;
                    if(cap()){cpu_stop=true;break;}
                    if(fresh){search_.admit(id);add_pattern(id,cycle);++telemetry_.bp.admissions;++row.admissions;}
                    ++telemetry_.bp.visits;++row.visits;UpdateRecord update;update.id=telemetry_.updates.size();update.cycle=cycle;
                    update.node_id=id;update.position=turn;update.visit_kind=fresh?"new":"continuation";update.quota=quota;
                    row.allocated+=quota;telemetry_.bp.planned_tokens+=quota;
                    auto prepare_timing=measured_stamp();solution_cpu=telemetry_.timing.solution_cpu;
                    solution_wall=telemetry_.timing.solution_wall;
                    Candidate candidate;candidate.node=id;candidate.latest_update=update.id;candidate.evaluated=true;
                    if(!fresh&&settings_.inheritance==Inheritance::RetainedAncestor) {
                        bp_.restore(old->state,shot_token_);update.donor_kind="own";update.donor_node=id;update.donor_update=old->latest_update;
                        update.donor_lineage=old->state.iterations;++telemetry_.bp.own_continuations;
                        ++telemetry_.bp.snapshot_copies;telemetry_.bp.copied_bytes+=bp_.snapshot_bytes();
                    } else if(fresh&&settings_.inheritance==Inheritance::RetainedAncestor) {
                        if(const Candidate* donor=nearest_donor(frozen,id)) {bp_.inherit(donor->state,search_.node(id).order_pattern,shot_token_);update.donor_kind="ancestor";
                            update.donor_node=donor->node;update.donor_update=donor->latest_update;update.donor_lineage=donor->state.iterations;
                            ++telemetry_.bp.ancestor_inheritances;++telemetry_.bp.snapshot_copies;telemetry_.bp.copied_bytes+=bp_.snapshot_bytes();}
                        else {bp_.reset(syndrome,search_.node(id).order_pattern,shot_token_);update.donor_kind="cold_seed";++telemetry_.bp.cold_initializations;}
                    } else {bp_.reset(syndrome,search_.node(id).order_pattern,shot_token_);update.donor_kind=fresh?"cold_seed":"cold_reset";
                        if(fresh)++telemetry_.bp.cold_initializations;else ++telemetry_.bp.cold_resets;}
                    bool valid=bp_.valid();++telemetry_.bp.hard_fixations;
                    update.residual_before=model_->graph->residual_weight(bp_.decision(),syndrome);
                    std::optional<uint64_t> event;
                    if(valid) {uint64_t d=violations(bp_.decision(),id);submit(bp_.decision(),SolutionSource::BPTransition,cycle,id,update.id,std::nullopt,d);
                        event=telemetry_.solutions.back().id;++telemetry_.bp.transition_solutions;}
                    update.prepare_cpu=measured_cpu(prepare_timing)-(telemetry_.timing.solution_cpu-solution_cpu);
                    update.prepare_wall=measured_wall(prepare_timing)-(telemetry_.timing.solution_wall-solution_wall);
                    telemetry_.bp.prepare_cpu+=update.prepare_cpu;telemetry_.bp.prepare_wall+=update.prepare_wall;
                    HardAdvance advanced;
                    if(!valid) {
                        auto iteration_timing=measured_stamp();solution_cpu=telemetry_.timing.solution_cpu;
                        solution_wall=telemetry_.timing.solution_wall;
                        uint64_t remaining=quota;
                        while(remaining&&!advanced.valid&&!advanced.cap_hit) {
                            auto part=bp_.advance(remaining,[this](){return cap();});
                            advanced.iterations+=part.iterations;advanced.valid=part.valid;advanced.cap_hit=part.cap_hit;
                            remaining-=part.iterations;
                        }
                        update.iterations_cpu=measured_cpu(iteration_timing)-(telemetry_.timing.solution_cpu-solution_cpu);
                        update.iterations_wall=measured_wall(iteration_timing)-(telemetry_.timing.solution_wall-solution_wall);
                        telemetry_.bp.iterations_cpu+=update.iterations_cpu;telemetry_.bp.iterations_wall+=update.iterations_wall;
                    }
                    update.actual=advanced.iterations;row.actual+=advanced.iterations;telemetry_.bp.iterations+=advanced.iterations;
                    if(advanced.valid) {uint64_t d=violations(bp_.decision(),id);submit(bp_.decision(),SolutionSource::BPIteration,cycle,id,update.id,std::nullopt,d);
                        event=telemetry_.solutions.back().id;++telemetry_.bp.iteration_solutions;valid=true;}
                    prepare_timing=measured_stamp();candidate.state=bp_.snapshot();
                    auto snapshot_cpu=measured_cpu(prepare_timing);
                    auto snapshot_wall=measured_wall(prepare_timing);
                    update.prepare_cpu+=snapshot_cpu;update.prepare_wall+=snapshot_wall;
                    telemetry_.bp.prepare_cpu+=snapshot_cpu;telemetry_.bp.prepare_wall+=snapshot_wall;
                    ++telemetry_.bp.snapshot_copies;telemetry_.bp.copied_bytes+=bp_.snapshot_bytes();
                    candidate.residual=model_->graph->residual_weight(candidate.state.decision,syndrome);
                    update.lineage_after=candidate.state.iterations;update.residual_after=candidate.residual;
                    update.violations=violations(candidate.state.decision,id);update.usable=true;update.valid=valid;update.solution_event=event;
                    update.disposition=valid?"retired_solved":"retained";candidate.update_index=telemetry_.updates.size();
                    telemetry_.updates.push_back(update);
                    if(valid) {++telemetry_.bp.retired;if(event&&settings_.stop_mode==StopMode::FirstValid){terminal=true;break;}}
                    else working.push_back(std::move(candidate));
                    if(advanced.cap_hit){cpu_stop=true;break;}
                }
                auto rank_timing=measured_stamp();reconcile(working,frozen,cycle);
                telemetry_.bp.rank_cpu+=measured_cpu(rank_timing);
                telemetry_.bp.rank_wall+=measured_wall(rank_timing);
                row.frontier_after=search_.frontier_size();row.guidance_after=search_.guidance_size();
                row.beam_after=beam_.size();if(!beam_.empty())row.best_residual=beam_[0].residual;if(incumbent_event_)row.incumbent=*incumbent_event_;
                row.span_cpu=measured_cpu(cycle_timing);row.span_wall=measured_wall(cycle_timing);
                if(cpu_stop){telemetry_.search.prefix_cpu_cap_hit=true;row.outcome="prefix_cpu_cap";telemetry_.cycles.push_back(row);return fallback_or_finish("prefix_cpu_cap");}
                if(terminal){row.outcome="first_valid";telemetry_.cycles.push_back(row);return finish_incumbent("first_valid");}
                row.completed=true;++telemetry_.bp.cycles_completed;
                if(incumbent_&&!first_cycle) first_cycle=cycle;
                if(first_cycle&&cycle+1>=uint64_t(*first_cycle)+settings_.post_solution_cycles) {
                    row.outcome="post_solution_cycles";telemetry_.cycles.push_back(row);return finish_incumbent("post_solution_cycles");}
                if(!future_work(size_t(cycle)+1)) {row.outcome="no_remaining_work";telemetry_.cycles.push_back(row);return fallback_or_finish("no_remaining_work");}
                telemetry_.cycles.push_back(row);
            }
            return fallback_or_finish("cycle_budget");
        } catch(const std::bad_alloc&) {result_.status="resource_error";return finish_incumbent("resource_error");}
          catch(const std::length_error&) {result_.status="resource_error";return finish_incumbent("resource_error");}
          catch(const std::overflow_error&) {result_.status="numerical_error";return finish_incumbent("numerical_error");}
    }
    Result fallback_or_finish(const char* reason) {
        if(incumbent_) return finish_incumbent(reason);
        result_.osd_entered=true;Reals llrs;OsdRecord call;call.trigger=reason;
        if(settings_.llr_policy==LlrPolicy::ChannelOnly||beam_.empty()) {
            llrs=model_->graph->weights;call.policy=settings_.llr_policy==LlrPolicy::ChannelOnly?"channel_only":"best_retained";
        } else {
            std::sort(beam_.begin(),beam_.end(),[this](const Candidate& a,const Candidate& b){return candidate_less(a,b);});
            auto& best=beam_.front();call.node_id=best.node;call.update_id=best.latest_update;
            llrs=best.state.llrs;call.policy="best_retained";call.actual_source="retained_hard_fixed";
        }
        call.llrs=llrs;auto osd_timing=measured_stamp();auto solution_cpu=telemetry_.timing.solution_cpu;
        auto solution_wall=telemetry_.timing.solution_wall;auto decoded=osd_.decode(syndrome_,llrs);call.valid=decoded.valid;
        if(decoded.valid) {submit(decoded.correction,SolutionSource::Osd,std::nullopt,std::nullopt,std::nullopt,0,std::nullopt);
            call.solution_event=telemetry_.solutions.back().id;}
        call.cpu=measured_cpu(osd_timing)-(telemetry_.timing.solution_cpu-solution_cpu);
        call.wall=measured_wall(osd_timing)-(telemetry_.timing.solution_wall-solution_wall);
        telemetry_.timing.osd_cpu+=call.cpu;telemetry_.timing.osd_wall+=call.wall;
        if(!decoded.valid) result_.status="nonconverged";
        telemetry_.osd_calls.push_back(call);return finish_incumbent(reason);
    }
    const Telemetry& telemetry_view() const noexcept{return telemetry_;}
    Telemetry export_telemetry(){Guard guard(busy_);return telemetry_;}
};
}
#endif
