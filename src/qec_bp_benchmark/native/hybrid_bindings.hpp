#ifndef QEC_HYBRID_BINDINGS_HPP
#define QEC_HYBRID_BINDINGS_HPP
#include "hybrid.hpp"
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <iomanip>
#include <sstream>
namespace qec::hybrid {
namespace py=pybind11;
inline py::dict summary_dict(const Summary& s) {
    py::dict d;
    d["algorithm_version"]="HSBP-ALG-1.0";d["exit_stage"]=stage_name(s.exit_stage);d["exit_reason"]=reason_name(s.exit_reason);
    d["fallback_reason"]=s.osd_entered?py::cast(fallback_name(s.fallback_reason)):py::none();
    d["osd_llr_source"]=s.osd_entered?py::cast(llr_name(s.osd_llr_source)):py::none();
    d["input_syndrome_weight"]=s.input_weight;d["cycles_started"]=s.cycles_started;d["cycles_completed"]=s.cycles_completed;
    d["search_slices"]=s.search_slices;d["search_expanded_nodes"]=s.search.expanded;d["search_generated_nodes"]=s.search.generated;
    d["search_rejected_local"]=s.search.rejected;d["search_depth_limited"]=s.search.depth_limited;
    d["search_frontier_peak"]=s.search.frontier_peak;d["search_guidance_peak"]=s.search.guidance_peak;d["search_max_depth_reached"]=s.search.max_depth;
    d["bp_attempts"]=s.bp_attempts;d["bp_iterations"]=s.bp_iterations;d["bp_warm_transitions"]=s.bp_warm_transitions;
    d["selected_hint_node_id"]=s.hint_id;d["selected_hint_ones"]=s.hint_ones;d["selected_hint_zeros"]=s.hint_zeros;
    d["hint_disagreements_final"]=s.hint_disagreements;d["osd_entered"]=s.osd_entered;d["osd_calls"]=s.osd_calls;
    d["effective_osd_order"]=s.osd_entered?py::cast(0):py::none();d["prefix_cap_hit"]=s.prefix_cap_hit;d["node_cap_hit"]=s.node_cap_hit;
    d["native_prefix_cpu_ns"]=s.prefix_cpu;d["native_prefix_wall_ns"]=s.prefix_wall;
    for(int p=0;p<4;++p) {
        std::string name=phase_name(Phase(p));
        d[(name+"_cpu_ns").c_str()]=s.prefix_cpu?py::cast(s.phase_cpu[p]):py::none();
        d[(name+"_wall_ns").c_str()]=s.prefix_wall?py::cast(s.phase_wall[p]):py::none();
    }
    d["prefix_other_cpu_ns"]=s.prefix_cpu?py::cast(*s.prefix_cpu-s.phase_cpu[0]-s.phase_cpu[1]-s.phase_cpu[2]):py::none();
    d["prefix_other_wall_ns"]=s.prefix_wall?py::cast(*s.prefix_wall-s.phase_wall[0]-s.phase_wall[1]-s.phase_wall[2]):py::none();
    return d;
}
inline py::dict telemetry_dict(const Telemetry& t) {
    py::dict d;py::list phases,rounds;
    for(size_t i=0;i<t.phases.size();++i) {
        const auto& p=t.phases[i];py::dict x;
        x["phase_index"]=i;x["phase"]=phase_name(p.phase);x["cycle_index"]=p.cycle<0?py::none():py::cast(p.cycle);
        x["cpu_ns"]=p.cpu;x["wall_ns"]=p.wall;x["native_wall_start_ns"]=p.start;x["native_wall_end_ns"]=p.end;
        x["work"]=p.work;x["result"]=p.result;x["candidate_syndrome_valid"]=(p.phase==Phase::Search && !p.valid)?py::none():py::cast(p.valid);
        phases.append(x);
    }
    for(const auto& r:t.rounds) {
        py::dict x;
        x["cycle_index"]=r.cycle;x["start_cpu_ns"]=r.start_cpu;x["end_cpu_ns"]=r.end_cpu;
        x["start_wall_ns"]=r.start_wall;x["end_wall_ns"]=r.end_wall;
        x["frontier_before"]=r.frontier_before;x["frontier_after"]=r.frontier_after;
        x["guidance_before"]=r.guidance_before;x["guidance_after"]=r.guidance_after;
        x["expansion_budget"]=r.expansion_budget;x["iteration_budget"]=r.iteration_budget;
        x["expanded"]=r.expanded;x["generated"]=r.generated;x["iterations"]=r.iterations;
        x["hint_node_id"]=r.hint_id;x["hint_ones"]=r.hint_ones;x["hint_zeros"]=r.hint_zeros;x["hint_depth"]=r.hint_depth;
        x["hint_g"]=r.hint_g;x["hint_h"]=r.hint_h;x["hint_f"]=r.hint_f;x["hint_residual_weight"]=r.hint_residual;
        if(r.hint_digest) {std::ostringstream s;s<<std::hex<<std::setfill('0')<<std::setw(16)<<*r.hint_digest;x["hint_digest"]=s.str();}
        else x["hint_digest"]=py::none();
        x["bp_entered"]=r.bp_entered;x["warm"]=r.warm;x["residual_before"]=r.residual_before;x["residual_after"]=r.residual_after;
        x["node_cap_hit"]=r.node_cap;x["prefix_cap_hit"]=r.cpu_cap;x["result"]=r.result;rounds.append(x);
    }
    d["rounds"]=rounds;d["phases"]=phases;return d;
}
inline void bind_hybrid(py::module_& m) {
    m.def("hybrid_source_identity",[](){py::dict d;d["project_sha256"]=QEC_HYBRID_HASH;d["fork_sha256"]=QEC_HYBRID_FORK_HASH;return d;});
    py::class_<Settings>(m,"HybridSettings").def(py::init<>())
        .def_readwrite("max_depth",&Settings::max_depth).def_readwrite("expansions",&Settings::expansions)
        .def_readwrite("iterations",&Settings::iterations).def_readwrite("max_generated_nodes",&Settings::max_generated_nodes)
        .def_readwrite("prefix_cpu_budget_ns",&Settings::prefix_cpu_budget_ns).def_readwrite("alpha",&Settings::alpha)
        .def_readwrite("clip",&Settings::clip).def_readwrite("margin",&Settings::margin)
        .def_readwrite("bp_enabled",&Settings::bp_enabled).def_readwrite("warm",&Settings::warm);
    py::class_<Result>(m,"HybridResult").def_readonly("valid",&Result::valid)
        .def_readonly("correction",&Result::correction).def_readonly("prediction",&Result::prediction).def_readonly("cost",&Result::cost)
        .def_property_readonly("summary",[](const Result& r){return summary_dict(r.summary);});
    py::class_<Decoder>(m,"HybridDecoder")
        .def(py::init<const Rows&,int,const Reals&,const Rows&,Settings,bool>(),py::arg("rows"),py::arg("n"),py::arg("probabilities"),
             py::arg("observables"),py::arg("settings"),py::arg("reference")=false)
        .def("decode",&Decoder::decode,py::arg("syndrome"),py::arg("profiling")=false,py::call_guard<py::gil_scoped_release>())
        .def("export_telemetry",[](Decoder& d){return telemetry_dict(d.export_telemetry());});
    m.def("hybrid_score",[](const Rows& rows,int n,const Reals& p,const Bits& s,const Key& key,bool reference){
        auto model=std::make_shared<Model>(rows,n,p,Rows{});SearchSession search(model,Settings{},reference);
        auto node=search.evaluate(s,key);py::dict d;d["g"]=node.g;d["h"]=node.h;d["f"]=node.f;d["rho"]=node.rho;return d;
    },py::arg("rows"),py::arg("n"),py::arg("probabilities"),py::arg("syndrome"),py::arg("pattern"),py::arg("reference")=false);
}
}
#endif
