#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "search.hpp"
#include "hybrid_bindings.hpp"
#include "search_bp_bindings.hpp"
namespace py=pybind11;
PYBIND11_MODULE(_native, m) {
    qec::hybrid::bind_hybrid(m);
    qec::search_bp::bind_search_bp(m);
    m.doc()="Exact native exhaustive screening using the forked ldpc reference BP kernel.";
    m.def("build_identity", [](){return "qec-bp-benchmark/0.1.0;c++17;binary64;no-fast-math";});
    m.def("source_identity", [](){py::dict d; d["search_sha256"]=QEC_SEARCH_HASH; d["binding_sha256"]=QEC_BINDING_HASH; d["cmake_sha256"]=QEC_CMAKE_HASH; d["bp_header_sha256"]=QEC_BP_HASH; return d;});
    py::class_<qec::Settings>(m,"Settings").def(py::init<>())
        .def_readwrite("T0",&qec::Settings::T0).def_readwrite("Tpost",&qec::Settings::Tpost)
        .def_readwrite("window",&qec::Settings::window).def_readwrite("M",&qec::Settings::M)
        .def_readwrite("q",&qec::Settings::q).def_readwrite("K",&qec::Settings::K).def_readwrite("limit",&qec::Settings::limit);
    py::class_<qec::Pattern>(m,"Pattern").def_readonly("id",&qec::Pattern::id)
        .def_readonly("g",&qec::Pattern::g).def_readonly("h",&qec::Pattern::h).def_readonly("f",&qec::Pattern::f)
        .def_readonly("rho",&qec::Pattern::rho).def_readonly("rejected",&qec::Pattern::rejected);
    py::class_<qec::Screen>(m,"Screen").def_readonly("pool",&qec::Screen::pool)
        .def_readonly("retained",&qec::Screen::retained).def_readonly("enumerated",&qec::Screen::enumerated).def_readonly("rejected",&qec::Screen::rejected);
    py::class_<qec::SearchResult>(m,"SearchResult")
        .def_readonly("status",&qec::SearchResult::status).def_readonly("correction",&qec::SearchResult::correction)
        .def_readonly("selected_pattern",&qec::SearchResult::selected_pattern).def_readonly("cost",&qec::SearchResult::cost)
        .def_readonly("valid",&qec::SearchResult::valid).def_readonly("initial_success",&qec::SearchResult::initial_success)
        .def_readonly("initial_iterations",&qec::SearchResult::initial_iterations).def_readonly("post_iterations",&qec::SearchResult::post_iterations)
        .def_readonly("completions",&qec::SearchResult::completions).def_readonly("successes",&qec::SearchResult::successes)
        .def_readonly("screening",&qec::SearchResult::screening).def_readonly("history",&qec::SearchResult::history)
        .def_readonly("completion_decisions",&qec::SearchResult::completion_decisions).def_readonly("completion_statuses",&qec::SearchResult::completion_statuses)
        .def_readonly("phases",&qec::SearchResult::phases)
        .def("diagnostics",[](const qec::SearchResult& r) {
            py::dict d;
            d["history"]=r.history; d["pool"]=r.screening.pool;
            py::list retained;
            for(const auto& p:r.screening.retained) {
                py::dict item;
                item["id"]=p.id; item["g"]=p.g; item["h"]=p.h;
                item["f"]=p.f; item["rho"]=p.rho;
                retained.append(item);
            }
            d["retained"]=retained;
            d["completion_decisions"]=r.completion_decisions;
            d["completion_statuses"]=r.completion_statuses;
            return d;
        });
    py::class_<qec::ScreenedDecoder>(m,"ScreenedDecoder")
        .def(py::init<std::vector<qec::Bits>,int,const qec::Beliefs&,qec::Settings>())
        .def("decode",&qec::ScreenedDecoder::decode,py::arg("syndrome"),py::arg("diagnostics")=false,py::arg("profiling")=false,py::call_guard<py::gil_scoped_release>())
        .def("screen",&qec::ScreenedDecoder::screen,py::call_guard<py::gil_scoped_release>())
        .def("pool",&qec::ScreenedDecoder::pool).def("score",&qec::ScreenedDecoder::score).def("cost",&qec::ScreenedDecoder::cost);
}
