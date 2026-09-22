#ifndef QEC_SEARCH_BP_BINDINGS_HPP
#define QEC_SEARCH_BP_BINDINGS_HPP
#include "search_bp_stage3.hpp"
#include "search_bp_decoder.hpp"
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace qec::search_bp2 {
namespace py = pybind11;
inline void bind_stage3(py::module_& m) {
    py::class_<Settings>(m, "SearchBPStage3Settings")
        .def(py::init<>())
        .def_readwrite("initial_iterations", &Settings::initial_iterations)
        .def_readwrite("history_window", &Settings::history_window)
        .def_readwrite("history_clip", &Settings::history_clip)
        .def_readwrite("scaling_factor", &Settings::scaling_factor)
        .def_readwrite("selected_checks", &Settings::selected_checks)
        .def_readwrite("local_variables", &Settings::local_variables)
        .def_readwrite("max_fixations", &Settings::max_fixations)
        .def_readwrite("local_variable_policy", &Settings::local_variable_policy)
        .def_readwrite("beta", &Settings::beta)
        .def_readwrite("guidance_strength", &Settings::guidance_strength);
    py::class_<Candidate>(m, "SearchBPCandidate")
        .def_readonly("parent_id", &Candidate::parent_id)
        .def_readonly("delta", &Candidate::delta)
        .def_property_readonly("depth", &Candidate::depth)
        .def_readonly("f_solve", &Candidate::f_solve)
        .def_readonly("f_guide", &Candidate::f_guide)
        .def_property_readonly("tie_key", [](const Candidate& c) { return py::make_tuple(c.delta, c.parent_id); });
    py::class_<Scores>(m, "SearchBPPatternScores")
        .def_readonly("g", &Scores::g).def_readonly("h", &Scores::h)
        .def_readonly("f_solve", &Scores::f_solve).def_readonly("j_var", &Scores::j_var)
        .def_readonly("g_amb", &Scores::g_amb).def_readonly("f_guide", &Scores::f_guide);
    py::class_<ParentScores>(m, "SearchBPParentScores")
        .def_readonly("mean", &ParentScores::mean)
        .def_readonly("fixed", &ParentScores::fixed)
        .def_readonly("residual", &ParentScores::residual)
        .def_readonly("confidence", &ParentScores::confidence)
        .def_readonly("probability", &ParentScores::probability)
        .def_readonly("ambiguity", &ParentScores::ambiguity)
        .def_readonly("objective", &ParentScores::objective)
        .def("select_checks", &select_checks, py::arg("count"))
        .def("select_variables", &select_variables, py::arg("check"), py::arg("count"))
        // Explicit formula inspection only. Per-candidate production paths return
        // compact scalars, not these copied residual/probability vectors.
        .def("inspect_pattern", [](const ParentScores& p, const Pattern& d, double lambda) {
            Scorer scratch(p);
            const auto scores = scratch.evaluate(d, lambda, true);
            return py::make_tuple(scores, scratch.residual, scratch.probability);
        }, py::arg("delta"), py::arg("guidance_strength"));
    py::class_<LocalResult>(m, "SearchBPLocalResult")
        .def_readonly("valid", &LocalResult::valid)
        .def_readonly("correction", &LocalResult::correction)
        .def_readonly("candidates", &LocalResult::candidates);
    py::class_<Stage3Result>(m, "SearchBPStage3Result")
        .def_readonly("valid", &Stage3Result::valid)
        .def_readonly("initial_success", &Stage3Result::initial_success)
        .def_readonly("correction", &Stage3Result::correction)
        .def_readonly("prediction", &Stage3Result::prediction)
        .def_property_readonly("bp", [](const Stage3Result& r) {
            py::module_::import("ldpc.hybrid_bp"); return py::cast(r.bp);
        })
        .def_property_readonly("parent_state", [](const Stage3Result& r) {
            py::module_::import("ldpc.hybrid_bp"); return py::cast(r.parent_state);
        })
        .def_readonly("parent_scores", &Stage3Result::parent_scores)
        .def_readonly("candidates", &Stage3Result::candidates);
    py::class_<Stage3>(m, "SearchBPStage3")
        .def(py::init<const Rows&, int, const Reals&, const Rows&, Settings>(),
             py::arg("rows"), py::arg("n"), py::arg("probabilities"), py::arg("observables"), py::arg("settings"))
        .def("run_initial", &Stage3::run_initial, py::arg("syndrome"), py::arg("parent_id") = 0,
             py::call_guard<py::gil_scoped_release>())
        .def("summarize", &Stage3::summarize, py::arg("syndrome"), py::arg("fixed"), py::arg("mean_llr"),
             py::call_guard<py::gil_scoped_release>())
        .def("expand", &Stage3::expand, py::arg("parent"), py::arg("parent_id") = 0,
             py::call_guard<py::gil_scoped_release>())
        .def("expand_parent", &Stage3::expand_parent, py::arg("snapshot"), py::arg("parent_id") = 0,
             py::call_guard<py::gil_scoped_release>());
    m.def("search_bp_pattern_bound", &pattern_bound, py::arg("m"), py::arg("q"));
    py::class_<DecoderSettings, Settings>(m, "SearchBP2Settings")
        .def(py::init<>())
        .def_readwrite("candidate_iterations", &DecoderSettings::candidate_iterations)
        .def_readwrite("k_run", &DecoderSettings::k_run)
        .def_readwrite("k_keep", &DecoderSettings::k_keep)
        .def_readwrite("max_cycles", &DecoderSettings::max_cycles)
        .def_readwrite("osd_fallback", &DecoderSettings::osd_fallback);
    py::class_<DecodeResult>(m, "SearchBP2Result")
        .def_readonly("valid", &DecodeResult::valid)
        .def_readonly("correction", &DecodeResult::correction)
        .def_readonly("prediction", &DecodeResult::prediction)
        .def_readonly("physical_cost", &DecodeResult::physical_cost)
        .def_readonly("osd_called", &DecodeResult::osd_called)
        .def_readonly("correction_by_search", &DecodeResult::correction_by_search);
    py::class_<Decoder>(m, "SearchBP2Decoder")
        .def(py::init<const Rows&, int, const Reals&, const Rows&, DecoderSettings>(),
             py::arg("rows"), py::arg("n"), py::arg("probabilities"), py::arg("observables"), py::arg("settings"))
        .def("decode", &Decoder::decode, py::arg("syndrome"), py::call_guard<py::gil_scoped_release>());
}
}
#endif
