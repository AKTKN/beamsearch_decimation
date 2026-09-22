#ifndef QEC_FRONTIER_BINDINGS_HPP
#define QEC_FRONTIER_BINDINGS_HPP
#include "frontier.hpp"
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
namespace py=pybind11;

namespace qec::frontier {
inline py::object optional_u64(const std::optional<uint64_t>& value){return value?py::cast(*value):py::none();}
inline py::object optional_u32(const std::optional<uint32_t>& value){return value?py::cast(*value):py::none();}
inline py::object measured_time(bool profiled,int64_t value){return profiled?py::cast(value):py::none();}
inline py::dict result_summary(const Result& result,const Telemetry& telemetry) {
    py::dict d;d["algorithm_version"]="HSBP-FB-2.0";d["status"]=result.status;
    d["prefix_stop_reason"]=result.prefix_stop_reason;d["osd_entered"]=result.osd_entered;
    d["first_solution_source"]=result.first_source?py::cast(source_name(*result.first_source)):py::none();
    d["winner_source"]=result.winner_source?py::cast(source_name(*result.winner_source)):py::none();
    d["first_solution_event_id"]=optional_u64(result.first_event);d["winner_solution_event_id"]=optional_u64(result.winner_event);
    const auto& s=telemetry.search;const auto& c=s.counts;py::dict search;
    search["root_nodes"]=c.roots;search["generated_nodes"]=c.generated;search["expanded_nodes"]=c.expanded;
    search["queue_pops"]=c.queue_pops;search["stale_pops"]=c.stale_pops;search["terminal_pops"]=c.terminal_pops;
    search["locally_infeasible_nodes"]=c.locally_infeasible;search["depth_limited_nodes"]=c.depth_limited;
    search["det_beam_discards"]=c.det_beam_discards;search["truncated_parents"]=c.truncated_parents;
    search["ungenerated_siblings"]=c.ungenerated_siblings;search["frontier_peak"]=c.frontier_peak;
    search["guidance_peak"]=c.guidance_peak;search["frontier_final"]=s.frontier_final;search["guidance_final"]=s.guidance_final;
    search["max_depth_reached"]=c.max_depth;search["direct_solution_events"]=c.direct_solutions;
    search["node_cap_hit"]=c.node_cap_hit;search["expansion_cap_hit"]=c.expansion_cap_hit;
    search["prefix_cpu_cap_hit"]=s.prefix_cpu_cap_hit;search["generation_frozen"]=c.generation_frozen;search["rho_min_final"]=c.rho_min;
    search["search_cpu_ns"]=measured_time(telemetry.profiled,s.cpu);search["search_wall_ns"]=measured_time(telemetry.profiled,s.wall);
    search["prefix_cpu_overshoot_ns"]=measured_time(s.prefix_cpu_cap_hit,s.overshoot);
    d["search_summary"]=search;
    const auto& b=telemetry.bp;py::dict bp;
    bp["cycles_started"]=b.cycles_started;bp["cycles_completed"]=b.cycles_completed;bp["proposals"]=b.proposals;
    bp["admissions"]=b.admissions;bp["evaluated_visits"]=b.visits;bp["planned_iteration_tokens"]=b.planned_tokens;
    bp["actual_iterations"]=b.iterations;bp["cold_initializations"]=b.cold_initializations;bp["cold_resets"]=b.cold_resets;
    bp["ancestor_inheritances"]=b.ancestor_inheritances;bp["own_continuations"]=b.own_continuations;
    bp["snapshot_copies"]=b.snapshot_copies;bp["copied_bytes"]=b.copied_bytes;bp["hint_transitions"]=b.hint_transitions;
    bp["evictions"]=b.evictions;bp["retired_solved"]=b.retired;bp["transition_solution_events"]=b.transition_solutions;
    bp["iteration_solution_events"]=b.iteration_solutions;bp["peak_live_states"]=b.peak_live_states;
    bp["retained_final"]=b.retained_final;bp["best_retained_node_id"]=optional_u64(b.best_node);
    bp["best_retained_residual"]=optional_u64(b.best_residual);bp["bp_prepare_cpu_ns"]=measured_time(telemetry.profiled,b.prepare_cpu);
    bp["bp_prepare_wall_ns"]=measured_time(telemetry.profiled,b.prepare_wall);bp["bp_iter_cpu_ns"]=measured_time(telemetry.profiled,b.iterations_cpu);
    bp["bp_iter_wall_ns"]=measured_time(telemetry.profiled,b.iterations_wall);bp["rank_cpu_ns"]=measured_time(telemetry.profiled,b.rank_cpu);
    bp["rank_wall_ns"]=measured_time(telemetry.profiled,b.rank_wall);
    d["bp_summary"]=bp;return d;
}
inline py::dict telemetry_dict(const Telemetry& telemetry) {
    py::dict out;py::list cycles,patterns,updates,memberships,solutions,osd,nodes,phases;
    for(const auto& r:telemetry.cycles){py::dict x;x["cycle_index"]=r.cycle;x["frontier_before"]=r.frontier_before;x["frontier_after"]=r.frontier_after;
        x["guidance_before"]=r.guidance_before;x["guidance_after"]=r.guidance_after;x["beam_before"]=r.beam_before;x["beam_after"]=r.beam_after;
        x["expansion_budget"]=r.expansion_budget;x["expansions_actual"]=r.expansions;x["generated_actual"]=r.generated;
        x["bp_pool_budget"]=r.pool_budget;x["bp_available_budget"]=r.available_budget;x["proposals"]=r.proposals;
        x["tentative_pool_size"]=r.pool_size;x["allocated_tokens"]=r.allocated;x["bp_actual_iterations"]=r.actual;
        x["admissions_actual"]=r.admissions;x["visits_actual"]=r.visits;x["best_bp_residual_after"]=optional_u64(r.best_residual);
        x["incumbent_event_id_after"]=optional_u64(r.incumbent);x["outcome"]=r.outcome;x["completed"]=r.completed;
        x["span_cpu_ns"]=measured_time(telemetry.profiled,r.span_cpu);x["span_wall_ns"]=measured_time(telemetry.profiled,r.span_wall);cycles.append(x);}
    for(const auto& r:telemetry.patterns){py::dict x;x["node_id"]=r.node_id;x["parent_node_id"]=r.parent_id;x["admitted_cycle"]=r.cycle;
        x["admission_ordinal"]=r.admission_ordinal;x["fixed_zero_indices"]=r.zeros;x["fixed_one_indices"]=r.ones;x["ones_depth"]=r.depth;
        x["search_residual_weight"]=r.rho;x["g"]=r.g;x["h"]=r.h;x["f"]=r.f;patterns.append(x);}
    for(const auto& r:telemetry.updates){py::dict x;x["update_id"]=r.id;x["cycle_index"]=r.cycle;x["node_id"]=r.node_id;
        x["evaluation_position"]=r.position;x["visit_kind"]=r.visit_kind;x["donor_kind"]=r.donor_kind;x["donor_node_id"]=optional_u64(r.donor_node);
        x["donor_update_id"]=optional_u64(r.donor_update);x["donor_lineage_iterations"]=r.donor_lineage;x["lineage_iterations_after"]=r.lineage_after;
        x["quota"]=r.quota;x["actual_iterations"]=r.actual;x["residual_before"]=optional_u64(r.residual_before);
        x["residual_after"]=optional_u64(r.residual_after);x["hint_disagreements_after"]=optional_u64(r.disagreements);
        x["state_usable"]=r.usable;x["syndrome_valid_after"]=r.valid?py::cast(*r.valid):py::none();x["rank_before_pruning"]=optional_u64(r.rank);
        x["disposition"]=r.disposition;x["solution_event_id"]=optional_u64(r.solution_event);x["posterior_sha256"]=py::none();
        x["prepare_cpu_ns"]=measured_time(telemetry.profiled,r.prepare_cpu);x["prepare_wall_ns"]=measured_time(telemetry.profiled,r.prepare_wall);
        x["iterations_cpu_ns"]=measured_time(telemetry.profiled,r.iterations_cpu);x["iterations_wall_ns"]=measured_time(telemetry.profiled,r.iterations_wall);updates.append(x);}
    for(const auto& r:telemetry.membership){py::dict x;x["cycle_index"]=r.cycle;x["node_id"]=r.node_id;x["latest_update_id"]=r.latest_update;
        x["retention_rank"]=r.rank;x["evaluated_this_cycle"]=r.evaluated;x["bp_residual_weight"]=r.residual;
        x["search_f"]=r.search_f;x["lineage_iterations"]=r.lineage;memberships.append(x);}
    for(const auto& r:telemetry.solutions){py::dict x;x["solution_event_id"]=r.id;x["cycle_index"]=optional_u32(r.cycle);x["source"]=source_name(r.source);
        x["node_id"]=optional_u64(r.node_id);x["bp_update_id"]=optional_u64(r.update_id);x["osd_call_id"]=optional_u64(r.osd_call_id);
        x["correction"]=r.correction;x["prediction"]=r.prediction;x["physical_cost"]=r.cost;x["hint_disagreements"]=optional_u64(r.hint_disagreements);
        x["incumbent_improved"]=r.improved;x["incumbent_event_id_after"]=r.incumbent_after;
        x["elapsed_cpu_ns"]=measured_time(telemetry.profiled,r.elapsed_cpu);x["elapsed_wall_ns"]=measured_time(telemetry.profiled,r.elapsed_wall);solutions.append(x);}
    for(const auto& r:telemetry.osd_calls){py::dict x;x["osd_call_id"]=0;x["trigger"]=r.trigger;x["llr_policy"]=r.policy;
        x["llr_actual_source"]=r.actual_source;x["source_node_id"]=optional_u64(r.node_id);x["source_update_id"]=optional_u64(r.update_id);
        x["status"]=r.valid?"valid":"nonconverged";x["syndrome_valid"]=r.valid;x["solution_event_id"]=optional_u64(r.solution_event);
        x["_llrs_for_digest"]=r.llrs;x["osd_cpu_ns"]=measured_time(telemetry.profiled,r.cpu);
        x["osd_wall_ns"]=measured_time(telemetry.profiled,r.wall);osd.append(x);}
    for(const auto& r:telemetry.search_nodes){py::dict x;x["node_id"]=r.node_id;x["parent_node_id"]=optional_u64(r.parent_id);
        x["generated_cycle"]=optional_u32(r.cycle);x["selected_one_index"]=r.selected?py::cast(*r.selected):py::none();
        x["added_zero_indices"]=r.zeros;x["ones_depth"]=r.depth;x["search_residual_weight"]=r.rho;x["g"]=r.g;
        x["h"]=r.h?py::cast(*r.h):py::none();x["f"]=r.f?py::cast(*r.f):py::none();x["construction_status"]=r.construction;
        x["search_final_status"]=r.final_status;x["bp_admitted"]=r.admitted;nodes.append(x);}
    out["cycles"]=cycles;out["patterns"]=patterns;out["bp_updates"]=updates;out["bp_beam_membership"]=memberships;
    if(telemetry.profiled&&(telemetry.search.cpu||telemetry.search.wall)){py::dict x;x["phase"]="search";x["scope_count"]=telemetry.bp.cycles_started;
        x["exclusive_cpu_ns"]=telemetry.search.cpu;x["exclusive_wall_ns"]=telemetry.search.wall;phases.append(x);}
    if(telemetry.profiled&&(telemetry.bp.prepare_cpu||telemetry.bp.prepare_wall)){py::dict x;x["phase"]="bp_prepare";x["scope_count"]=telemetry.bp.visits;
        x["exclusive_cpu_ns"]=telemetry.bp.prepare_cpu;x["exclusive_wall_ns"]=telemetry.bp.prepare_wall;phases.append(x);}
    if(telemetry.profiled&&(telemetry.bp.iterations_cpu||telemetry.bp.iterations_wall)){py::dict x;x["phase"]="bp_iter";x["scope_count"]=telemetry.bp.visits;
        x["exclusive_cpu_ns"]=telemetry.bp.iterations_cpu;x["exclusive_wall_ns"]=telemetry.bp.iterations_wall;phases.append(x);}
    if(telemetry.profiled&&(telemetry.bp.rank_cpu||telemetry.bp.rank_wall)){py::dict x;x["phase"]="rank";x["scope_count"]=telemetry.bp.cycles_started;
        x["exclusive_cpu_ns"]=telemetry.bp.rank_cpu;x["exclusive_wall_ns"]=telemetry.bp.rank_wall;phases.append(x);}
    if(telemetry.profiled&&(telemetry.timing.solution_cpu||telemetry.timing.solution_wall)){py::dict x;x["phase"]="solution";x["scope_count"]=telemetry.solutions.size();
        x["exclusive_cpu_ns"]=telemetry.timing.solution_cpu;x["exclusive_wall_ns"]=telemetry.timing.solution_wall;phases.append(x);}
    if(telemetry.profiled&&(telemetry.timing.osd_cpu||telemetry.timing.osd_wall)){py::dict x;x["phase"]="osd";x["scope_count"]=telemetry.osd_calls.size();
        x["exclusive_cpu_ns"]=telemetry.timing.osd_cpu;x["exclusive_wall_ns"]=telemetry.timing.osd_wall;phases.append(x);}
    out["solution_events"]=solutions;out["osd_calls"]=osd;out["phase_timings"]=phases;out["search_nodes"]=nodes;return out;
}
inline void bind_frontier(py::module_& module) {
    py::class_<Settings>(module,"FrontierSettings").def(py::init<>())
        .def_readwrite("max_depth",&Settings::max_depth).def_readwrite("hint_max_depth",&Settings::hint_max_depth)
        .def_readwrite("det_beam",&Settings::det_beam).def_readwrite("prefix_cpu_budget_ns",&Settings::prefix_cpu_budget_ns)
        .def_readwrite("expansions",&Settings::expansions).def_readwrite("admissions",&Settings::admissions)
        .def_readwrite("max_expansions",&Settings::max_expansions)
        .def_readwrite("max_generated_nodes",&Settings::max_generated_nodes).def_readwrite("max_total_iterations",&Settings::max_total_iterations)
        .def_readwrite("beam_width",&Settings::beam_width).def_readwrite("max_iterations_per_visit",&Settings::max_iterations_per_visit)
        .def_readwrite("post_solution_cycles",&Settings::post_solution_cycles).def_readwrite("alpha",&Settings::alpha)
        .def_readwrite("clip",&Settings::clip).def_readwrite("margin",&Settings::margin).def_readwrite("bp_enabled",&Settings::bp_enabled)
        .def_readwrite("trace_search_nodes",&Settings::trace_search_nodes).def_readwrite("profiling",&Settings::profiling)
        .def("set_goal_test",[](Settings& s,const std::string& x){s.goal_test=x=="on_generation"?GoalTest::OnGeneration:GoalTest::OnPop;})
        .def("set_retention",[](Settings& s,const std::string& x){s.retention=x=="residual_then_physical"?RetentionScore::ResidualThenPhysical:RetentionScore::PhysicalOnly;})
        .def("set_inheritance",[](Settings& s,const std::string& x){s.inheritance=x=="retained_ancestor"?Inheritance::RetainedAncestor:Inheritance::Cold;})
        .def("set_hint_mode",[](Settings& s,const std::string& x){s.hint_mode=x=="soft"?HintMode::Soft:HintMode::None;})
        .def("set_stop_mode",[](Settings& s,const std::string& x){s.stop_mode=x=="first_valid"?StopMode::FirstValid:StopMode::BoundedImprove;})
        .def("set_llr_policy",[](Settings& s,const std::string& x){s.llr_policy=x=="best_retained_guided"?LlrPolicy::BestRetainedGuided:
            x=="channel_only"?LlrPolicy::ChannelOnly:LlrPolicy::BestRetainedRelease;});
    py::class_<Result>(module,"FrontierResult").def_readonly("valid",&Result::valid).def_readonly("correction",&Result::correction)
        .def_readonly("prediction",&Result::prediction).def_readonly("cost",&Result::cost).def_readonly("status",&Result::status);
    py::class_<Decoder>(module,"FrontierDecoder")
        .def(py::init<const Rows&,int,const Reals&,const Rows&,Settings,bool>(),py::arg("rows"),py::arg("n"),py::arg("probabilities"),
             py::arg("observables"),py::arg("settings"),py::arg("reference")=false)
        .def("decode",&Decoder::decode,py::call_guard<py::gil_scoped_release>())
        .def("summary",[](Decoder& decoder,const Result& result){return result_summary(result,decoder.export_telemetry());})
        .def("export_telemetry",[](Decoder& decoder){return telemetry_dict(decoder.export_telemetry());});
}
}
#endif
