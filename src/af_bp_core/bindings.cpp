#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "decoder.hpp"
namespace py = pybind11;
using namespace af_bp_core;

PYBIND11_MODULE(_af_bp_service, m) {
    m.doc() = "Native AF-BP-1.0 decoder service without simulator or truth input.";
    m.def("build_identity", []() {
        py::dict out;
        out["kind"] = KIND;
        out["profile"] = PROFILE;
        out["name"] = NAME;
        out["algorithm_version"] = ALGORITHM_VERSION;
        out["source_sha256"] = AF_BP_SERVICE_SOURCE_HASH;
        out["flags"] = "-O3 -std=c++17 -fno-fast-math -ffp-contract=off";
        return out;
    });
    py::class_<FailureSettings>(m, "FailureSettings")
        .def(py::init<>())
        .def_readwrite("residual_radius", &FailureSettings::residual_radius)
        .def_readwrite("distance_decay", &FailureSettings::distance_decay)
        .def_readwrite("uncertainty_weight", &FailureSettings::uncertainty_weight)
        .def_readwrite("oscillation_weight", &FailureSettings::oscillation_weight)
        .def_readwrite("selection", &FailureSettings::selection)
        .def_readwrite("top_k", &FailureSettings::top_k)
        .def_readwrite("threshold", &FailureSettings::threshold);
    py::class_<DecoderSettings>(m, "DecoderSettings")
        .def(py::init<>())
        .def_readwrite("initial_parallel", &DecoderSettings::initial_parallel)
        .def_readwrite("initial_iteration_budget", &DecoderSettings::initial_iteration_budget)
        .def_readwrite("transformed_iteration_budget", &DecoderSettings::transformed_iteration_budget)
        .def_readwrite("bp_variant", &DecoderSettings::bp_variant)
        .def_readwrite("serial_order", &DecoderSettings::serial_order)
        .def_readwrite("scaling_factor", &DecoderSettings::scaling_factor)
        .def_readwrite("history_window", &DecoderSettings::history_window)
        .def_readwrite("graph_rounds", &DecoderSettings::graph_rounds)
        .def_readwrite("n_fact", &DecoderSettings::n_fact)
        .def_readwrite("factorization_policy", &DecoderSettings::factorization_policy)
        .def_readwrite("failure", &DecoderSettings::failure)
        .def_readwrite("atanh_epsilon", &DecoderSettings::atanh_epsilon)
        .def_readwrite("phase1_iterations", &DecoderSettings::phase1_iterations)
        .def_readwrite("num_chains", &DecoderSettings::num_chains)
        .def_readwrite("chain_iterations", &DecoderSettings::chain_iterations)
        .def_readwrite("alpha", &DecoderSettings::alpha)
        .def_readwrite("beta", &DecoderSettings::beta)
        .def_readwrite("rho", &DecoderSettings::rho)
        .def_readwrite("seed", &DecoderSettings::seed)
        .def_readwrite("seed_policy", &DecoderSettings::seed_policy)
        .def_readwrite("qdither_handoff", &DecoderSettings::qdither_handoff);
    py::class_<Biclique>(m, "Biclique")
        .def_readonly("variables", &Biclique::variables)
        .def_readonly("checks", &Biclique::checks);
    py::class_<BpCallRecord>(m, "BpCallRecord")
        .def_readonly("graph_index", &BpCallRecord::graph_index)
        .def_readonly("variant", &BpCallRecord::variant)
        .def_readonly("budget", &BpCallRecord::budget)
        .def_readonly("actual_iterations", &BpCallRecord::actual_iterations)
        .def_readonly("variable_count", &BpCallRecord::variable_count)
        .def_readonly("check_count", &BpCallRecord::check_count)
        .def_readonly("native_success", &BpCallRecord::native_success)
        .def_readonly("physical_valid", &BpCallRecord::physical_valid)
        .def_readonly("budget_truncated", &BpCallRecord::budget_truncated)
        .def_readonly("phase1_iterations", &BpCallRecord::phase1_iterations)
        .def_readonly("chain_iterations", &BpCallRecord::chain_iterations)
        .def_readonly("seed", &BpCallRecord::seed)
        .def_readonly("q_init", &BpCallRecord::q_init)
        .def_readonly("final_llrs", &BpCallRecord::final_llrs);
    py::class_<TransformRecord>(m, "TransformRecord")
        .def_readonly("biclique", &TransformRecord::biclique)
        .def_readonly("new_variable", &TransformRecord::new_variable)
        .def_readonly("inherited_llr", &TransformRecord::inherited_llr);
    py::class_<DecodeResult>(m, "DecodeResult")
        .def_readonly("valid", &DecodeResult::valid)
        .def_readonly("correction", &DecodeResult::correction)
        .def_readonly("prediction", &DecodeResult::prediction)
        .def_readonly("last_physical_hard", &DecodeResult::last_physical_hard)
        .def_readonly("total_iterations", &DecodeResult::total_iterations)
        .def_readonly("graph_instances", &DecodeResult::graph_instances)
        .def_readonly("factorizations", &DecodeResult::factorizations)
        .def_readonly("status", &DecodeResult::status)
        .def_readonly("calls", &DecodeResult::calls)
        .def_readonly("transforms", &DecodeResult::transforms);
    py::class_<Decoder>(m, "Decoder")
        .def(py::init<Rows, Rows, Reals, DecoderSettings>(),
             py::arg("h0_rows"), py::arg("observable_rows"),
             py::arg("probabilities"), py::arg("settings"))
        .def("decode", &Decoder::decode, py::arg("syndrome"), py::arg("diagnostics")=false,
             py::call_guard<py::gil_scoped_release>());
}
