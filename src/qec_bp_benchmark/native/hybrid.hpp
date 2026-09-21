#ifndef QEC_HYBRID_HPP
#define QEC_HYBRID_HPP
#include "hybrid_telemetry.hpp"
#include "stateful_min_sum.hpp"
#include "osd0_bridge.hpp"
#include <atomic>
namespace qec::hybrid {
struct Result {
    bool valid=false;
    Bits correction,prediction;
    double cost=0;
    Summary summary;
};
// Complete C++ shot service. All mutable buffers stay in this object; independent
// objects can run concurrently. Callers must export owned telemetry before reuse.
class Decoder {
    std::shared_ptr<const Model> model_;
    Settings settings_;
    SearchSession search_;
    ldpc::hybrid::StatefulMinSumSession bp_;
    ldpc::hybrid::Osd0Bridge osd_;
    std::atomic_flag busy_=ATOMIC_FLAG_INIT;
    Telemetry telemetry_;
    Stamp start_{};
    int64_t budget_start_=0;
    bool profiling_=false,bp_started_=false,prefix_closed_=false;
    Result result_;
    Key last_hint_;
    struct Guard {
        std::atomic_flag& flag;
        explicit Guard(std::atomic_flag& f):flag(f) {if(flag.test_and_set()) throw std::logic_error("hybrid session is non-reentrant");}
        ~Guard(){flag.clear();}
    };
    bool cap() {return settings_.prefix_cpu_budget_ns && cpu_ns()-budget_start_>=settings_.prefix_cpu_budget_ns;}
    template<class F> auto phase(Phase kind,int cycle,F&& function) {
        Stamp begin=profiling_ ? stamp() : Stamp{};
        auto record=[&](const char* reason) {
        if(profiling_) {
            auto end=stamp(); int index=int(kind);
            result_.summary.phase_cpu[index]+=end.cpu-begin.cpu;
            result_.summary.phase_wall[index]+=end.wall-begin.wall;
            telemetry_.phases.push_back({kind,cycle,end.cpu-begin.cpu,end.wall-begin.wall,
                                         begin.wall-start_.wall,end.wall-start_.wall,0,false,reason});
        }
        };
        try {auto out=function(); record("nonconverged"); return out;}
        catch(...) {record("exception");throw;}
    }
    void phase_result(bool valid,uint64_t work,const char* reason) {
        if(profiling_) {auto& p=telemetry_.phases.back(); p.valid=valid; p.work=work; p.result=reason;}
    }
    void close_prefix() {
        if(!prefix_closed_ && profiling_) {auto end=stamp(); result_.summary.prefix_cpu=end.cpu-start_.cpu; result_.summary.prefix_wall=end.wall-start_.wall;}
        prefix_closed_=true;
    }
    void finish_round(RoundRecord& row,const SearchCounts& before,const char* result) {
        if(!profiling_) return;
        auto end=stamp(); row.end_cpu=end.cpu-start_.cpu; row.end_wall=end.wall-start_.wall;
        row.frontier_after=search_.frontier_size();row.guidance_after=search_.guidance_size();
        row.expanded=search_.counts.expanded-before.expanded; row.generated=search_.counts.generated-before.generated;
        row.node_cap=result_.summary.node_cap_hit; row.cpu_cap=result_.summary.prefix_cap_hit; row.result=result;
        if(!telemetry_.rounds.empty() && telemetry_.rounds.back().cycle==row.cycle) telemetry_.rounds.back()=row;
        else telemetry_.rounds.push_back(row);
    }
    Result finish(const Bits& e,ExitStage stage,ExitReason reason) {
        close_prefix(); result_.summary.search=search_.counts;
        if(model_->graph->valid(e,syndrome_)) {
            result_.valid=true; result_.correction=e; result_.prediction=model_->predict(e); result_.cost=model_->cost(e);
            result_.summary.exit_stage=stage;result_.summary.exit_reason=reason;
            if(result_.summary.hint_id) {
                uint64_t disagreements=0; for(auto [i,b]:last_hint_) disagreements+=e[i]!=b;
                result_.summary.hint_disagreements=disagreements;
            }
        } else {result_.summary.exit_stage=ExitStage::Failed; result_.summary.exit_reason=ExitReason::OsdInvalid;}
        return result_;
    }
    Bits syndrome_;
public:
    Decoder(const Rows& rows,int n,const Reals& probabilities,const Rows& observables,Settings settings,bool reference=false):
        model_(std::make_shared<Model>(rows,n,probabilities,observables)),settings_(std::move(settings)),
        search_(model_,settings_,reference),bp_(model_->graph,settings_.clip,settings_.alpha),osd_(model_->graph) {
        settings_.validate();
        syndrome_.reserve(model_->graph->m);
        telemetry_.rounds.reserve(settings_.expansions.size());
        telemetry_.phases.reserve(settings_.expansions.size()*3+1);
    }
    Result decode(const Bits& s,bool profiling=false) {
        Guard guard(busy_);
        profiling_=profiling; start_=profiling ? stamp() : Stamp{};
        budget_start_=settings_.prefix_cpu_budget_ns ? (profiling ? start_.cpu : cpu_ns()) : 0;
        result_={};telemetry_.rounds.clear();telemetry_.phases.clear();search_.clear();last_hint_.clear();
        bp_started_=false;prefix_closed_=false;
        // Invalid caller input propagates; all earlier telemetry/search state is gone.
        binary(s,model_->graph->m);
        auto& summary=result_.summary;
        for(auto x:s) summary.input_weight+=x;
        try {
            syndrome_=s;
            // BP buffers are logically reset now and physically cleared on first
            // attempt. No path can read previous-shot BP state while bp_started_=false.
            if(model_->graph->inconsistent_empty_row(s)) {
                close_prefix();summary.exit_reason=ExitReason::Inconsistent;return result_;
            }
            if(!summary.input_weight) return finish(Bits(model_->graph->n,0),ExitStage::Search,ExitReason::ZeroSyndrome);
            search_.reset(s);
            summary.fallback_reason=FallbackReason::CycleBudget;
            for(size_t c=0;c<settings_.expansions.size();++c) {
                ++summary.cycles_started; RoundRecord round;round.cycle=int(c);
                if(profiling_) {auto now=stamp();round.start_cpu=now.cpu-start_.cpu;round.start_wall=now.wall-start_.wall;}
                round.frontier_before=search_.frontier_size();round.guidance_before=search_.guidance_size();
                round.expansion_budget=settings_.expansions[c];round.iteration_budget=settings_.iterations[c];
                auto before=search_.counts;
                uint64_t block_start=0;
                bool block_active=false;
                try {
                if(search_.frontier_size()) {
                    ++summary.search_slices;
                    auto step=phase(Phase::Search,int(c),[&](){return search_.advance(settings_.expansions[c],[this](){return cap();});});
                    phase_result(step.goal,search_.counts.expanded-before.expanded,step.goal?"valid":"slice_complete");
                    if(step.goal) {finish_round(round,before,"search_exit");summary.fallback_reason=FallbackReason::None;return finish(step.correction,ExitStage::Search,ExitReason::SearchGoal);}
                    summary.node_cap_hit=step.node_cap;summary.prefix_cap_hit=step.cpu_cap;
                }
                if(!summary.node_cap_hit && !summary.prefix_cap_hit && settings_.bp_enabled && search_.guidance_size()) {
                    if(cap()) summary.prefix_cap_hit=true;
                    else {
                        auto id=search_.take_hint();const auto& hint=search_.node(id);last_hint_=hint.key;
                        bool warm=bp_started_ && settings_.warm;
                        round.bp_entered=true;round.warm=warm;round.hint_id=id;round.hint_digest=pattern_digest(hint.key);
                        round.hint_ones=hint.depth;round.hint_zeros=hint.key.size()-hint.depth;round.hint_depth=hint.depth;
                        round.hint_g=hint.g;round.hint_h=hint.h;round.hint_f=hint.f;round.hint_residual=hint.rho;
                        summary.hint_id=id;summary.hint_ones=hint.depth;summary.hint_zeros=hint.key.size()-hint.depth;
                        ++summary.bp_attempts;summary.bp_warm_transitions+=warm;
                        bool valid=phase(Phase::Transition,int(c),[&](){
                            if(profiling_) round.residual_before=model_->graph->residual_weight(
                                bp_started_?bp_.decision():model_->channel_decision,s);
                            if(!warm) bp_.reset(s);
                            return bp_.replace_hint(hint.key,settings_.margin);
                        });
                        bp_started_=true;
                        phase_result(valid,0,valid?"valid":"nonconverged");
                        if(valid) {round.residual_after=0;finish_round(round,before,"bp_exit");summary.fallback_reason=FallbackReason::None;return finish(bp_.decision(),ExitStage::GuidedBP,ExitReason::BPTransition);}
                        block_start=bp_.completed_iterations();block_active=true;
                        auto block=phase(Phase::Iterations,int(c),[&](){return bp_.advance(settings_.iterations[c],[this](){return cap();});});
                        block_active=false;
                        summary.bp_iterations+=block.iterations;round.iterations=block.iterations;
                        if(profiling_) round.residual_after=model_->graph->residual_weight(bp_.decision(),s);
                        phase_result(block.valid,block.iterations,block.valid?"valid":block.cap_hit?"prefix_cpu_cap":"nonconverged");
                        if(block.valid) {finish_round(round,before,"bp_exit");summary.fallback_reason=FallbackReason::None;return finish(bp_.decision(),ExitStage::GuidedBP,ExitReason::BPIteration);}
                        summary.prefix_cap_hit=block.cap_hit;
                    }
                }
                if(summary.node_cap_hit||summary.prefix_cap_hit) {
                    summary.fallback_reason=summary.node_cap_hit?FallbackReason::NodeCap:FallbackReason::CpuCap;
                    finish_round(round,before,"fallback");break;
                }
                ++summary.cycles_completed;
                bool exhausted=!search_.frontier_size() && (!settings_.bp_enabled||!search_.guidance_size());
                if(exhausted) summary.fallback_reason=FallbackReason::Exhausted;
                bool fallback=exhausted || c+1==settings_.expansions.size();
                finish_round(round,before,fallback?"fallback":"continue"); if(fallback) break;
                } catch(...) {
                    if(block_active) {
                        round.iterations=bp_.completed_iterations()-block_start;
                        summary.bp_iterations+=round.iterations;
                        phase_result(false,round.iterations,"exception");
                    } else if(profiling_ && !telemetry_.phases.empty() && telemetry_.phases.back().phase==Phase::Search) {
                        phase_result(false,search_.counts.expanded-before.expanded,"exception");
                    }
                    finish_round(round,before,"failed");throw;
                }
            }
            close_prefix();summary.osd_entered=true;summary.osd_calls=1;
            summary.osd_llr_source=bp_started_?LlrSource::LastBP:LlrSource::Channel;
            auto osd=phase(Phase::Osd,-1,[&](){
                if(bp_started_) return osd_.decode(s,bp_.llrs());
                auto fields=model_->graph->weights;for(auto& x:fields) x=std::min(x,settings_.clip);
                return osd_.decode(s,fields);
            });
            phase_result(osd.valid,1,osd.valid?"valid":"invalid");
            return finish(osd.correction,ExitStage::Osd,ExitReason::OsdValid);
        } catch(const std::bad_alloc&) {summary.exit_reason=ExitReason::ResourceFailure;}
          catch(const std::length_error&) {summary.exit_reason=ExitReason::ResourceFailure;}
          catch(const std::overflow_error&) {summary.exit_reason=ExitReason::NumericalFailure;}
        close_prefix();summary.search=search_.counts;summary.exit_stage=ExitStage::Failed;
        result_.valid=false;result_.correction.clear();result_.prediction.clear();return result_;
    }
    Telemetry export_telemetry() {Guard guard(busy_);return telemetry_;}
};
}
#endif
