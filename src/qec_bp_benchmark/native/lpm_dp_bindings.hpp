#ifndef QEC_LPM_DP_BINDINGS_HPP
#define QEC_LPM_DP_BINDINGS_HPP

#include "lpm_dp_decoder.hpp"
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace qec::lpm_dp_bp {
namespace py = pybind11;

inline void bind_lpm_dp(py::module_& m) {
    py::class_<DecoderSettings>(m, "LPMDPBPSettings")
        .def(py::init<>())
        .def_readwrite("history_window", &DecoderSettings::history_window)
        .def_readwrite("history_clip", &DecoderSettings::history_clip)
        .def_readwrite("pool_size", &DecoderSettings::pool_size)
        .def_readwrite("local_check_limit", &DecoderSettings::local_check_limit)
        .def_readwrite("max_fixations", &DecoderSettings::max_fixations)
        .def_readwrite("candidates_per_parent", &DecoderSettings::candidates_per_parent)
        .def_readwrite("retained_mass_target", &DecoderSettings::retained_mass_target)
        .def_readwrite("proposal_clip", &DecoderSettings::proposal_clip)
        .def_readwrite("initial_iterations", &DecoderSettings::initial_iterations)
        .def_readwrite("candidate_iterations", &DecoderSettings::candidate_iterations)
        .def_readwrite("retained_parents", &DecoderSettings::retained_parents)
        .def_readwrite("max_cycles", &DecoderSettings::max_cycles)
        .def_readwrite("scaling_factor", &DecoderSettings::min_sum_scaling)
        .def_readwrite("osd_fallback", &DecoderSettings::osd_fallback);
    py::class_<DecodeResult>(m, "LPMDPBPResult")
        .def_readonly("valid", &DecodeResult::valid)
        .def_readonly("correction", &DecodeResult::correction)
        .def_readonly("prediction", &DecodeResult::prediction)
        .def_readonly("physical_cost", &DecodeResult::physical_cost)
        .def_readonly("osd_called", &DecodeResult::osd_called);
    py::class_<Decoder>(m, "LPMDPBPDecoder")
        .def(py::init<const Rows&, int, const Reals&, const Rows&, DecoderSettings>(),
             py::arg("rows"), py::arg("n"), py::arg("probabilities"),
             py::arg("observables"), py::arg("settings"))
        .def("decode", &Decoder::decode, py::arg("syndrome"),
             py::call_guard<py::gil_scoped_release>());
}

} // namespace qec::lpm_dp_bp
#endif
