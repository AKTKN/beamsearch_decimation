"""Measure a bounded live AF-BP decode on a BB144 d12/R1 DEM."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import resource
import threading
import time

import numpy as np
import psutil

from qec_bp_benchmark.af_bp_service import AFBPConfig, AFBPDecoder
from qec_bp_benchmark.circuits import apply_noise, make_template, select_z_detectors
from qec_bp_benchmark.config import Multipliers
from qec_bp_benchmark.dem.model import convert_dem


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    template = make_template("bb144", 12, rounds=1)
    eligible = tuple(sorted((*template.data_qubits, *template.check_sectors)))
    circuit = apply_noise(template.circuit, .001, Multipliers(), eligible)
    view = select_z_detectors(circuit, template)
    problem = convert_dem(view.circuit.detector_error_model(
        decompose_errors=False, approximate_disjoint_errors=False))
    process = psutil.Process()
    prepared_rss = process.memory_info().rss
    decoder = AFBPDecoder(problem.H, problem.A, problem.probabilities,
                          AFBPConfig(initial_iteration_budget=0,
                                     transformed_iteration_budget=0,
                                     graph_rounds=2, n_fact=2,
                                     factorization_policy="shen_cycle_count"))
    constructed_rss = process.memory_info().rss
    syndrome = np.asarray(problem.H[:, 0].toarray().ravel(), dtype=np.uint8)
    readings = [constructed_rss]
    stop = threading.Event()

    def poll() -> None:
        while not stop.is_set():
            readings.append(process.memory_info().rss)
            time.sleep(0.001)

    watcher = threading.Thread(target=poll, daemon=True)
    watcher.start()
    try:
        result = decoder.decode(syndrome, diagnostics=False)
    finally:
        stop.set()
        watcher.join()
    after_rss = process.memory_info().rss
    evidence = {
        "code": "BB144", "distance": 12, "rounds": 1, "physical_rate": .001,
        "H_shape": list(problem.H.shape), "H_nnz": int(problem.H.nnz),
        "A_shape": list(problem.A.shape), "A_nnz": int(problem.A.nnz),
        "prepared_rss_bytes": prepared_rss,
        "constructed_rss_bytes": constructed_rss,
        "sampled_decode_peak_rss_bytes": max(readings),
        "after_decode_rss_bytes": after_rss,
        "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "rss_poll_interval_ms": 1,
        "status": result.status,
        "graph_instances": result.graph_instances,
        "factorizations": result.factorizations,
        "total_iterations": result.total_iterations,
        "measurement_scope": "whole Python process; includes prepared circuit/DEM and imports",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, sort_keys=True))


if __name__ == "__main__":
    main()
