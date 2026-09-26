"""One-call Python/native AF-BP boundary without simulator registration."""
from __future__ import annotations

import numpy as np
import pytest
from scipy import sparse
from pathlib import Path

from qec_bp_benchmark.af_bp_service import (
    AFBPConfig, AFBPDecoder, FailureOptions, build_identity, source_digest,
)
from qec_bp_benchmark.config import Config
from qec_bp_benchmark.native_sources import AF_BP_SERVICE_FILES

ROOT = Path(__file__).resolve().parents[1]


def test_standalone_service_identity_truth_boundary_and_reset() -> None:
    h = sparse.csr_matrix(np.array([[1, 1], [1, 1]], dtype=np.uint8))
    a = sparse.csr_matrix(np.eye(2, dtype=np.uint8))
    config = AFBPConfig(initial_iteration_budget=0, transformed_iteration_budget=5,
                        graph_rounds=1, n_fact=1)
    decoder = AFBPDecoder(h, a, [0.1, 0.2], config)
    assert build_identity()["source_sha256"] == source_digest()
    cmake = (ROOT / "CMakeLists.txt").read_text()
    assert all(path in cmake for path in AF_BP_SERVICE_FILES)
    assert {key: build_identity()[key] for key in
            ("kind", "profile", "name", "algorithm_version")} == {
                "kind": "af_bp", "profile": "af_bp_v1", "name": "af_bp_v1",
                "algorithm_version": "AF-BP-1.0"}
    first = decoder.decode([1, 1], diagnostics=True)
    middle = decoder.decode([0, 0])
    replay = decoder.decode([1, 1])
    assert first.valid and first.status == "SUCCESS"
    assert first.total_iterations == 2 and first.factorizations == 1
    assert first.initial_bp_converged is False
    assert first.first_transform_converged is True
    assert first.graph_instances == 2 and len(first.calls) == 2
    assert first.correction is not None and first.prediction is not None
    np.testing.assert_array_equal((h @ first.correction) % 2, [1, 1])
    np.testing.assert_array_equal(first.prediction, (a @ first.correction) % 2)
    assert middle.valid and middle.total_iterations == 0
    assert middle.initial_bp_converged is True
    assert middle.first_transform_converged is None
    assert replay.valid and replay.total_iterations == first.total_iterations
    assert replay.initial_bp_converged is False
    assert replay.first_transform_converged is True
    np.testing.assert_array_equal(replay.correction, first.correction)
    assert replay.calls == () and replay.transforms == ()  # compact normal call
    with pytest.raises(TypeError):
        decoder.decode([1, 1], truth=[0, 0])
    with pytest.raises(ValueError, match="syndrome"):
        decoder.decode([1, 2])


def test_python_marshalling_rejects_invalid_inputs_and_unavailable_registry() -> None:
    h = np.array([[1, 1], [1, 1]], dtype=np.uint8)
    a = np.eye(2, dtype=np.uint8)
    with pytest.raises(ValueError, match="binary"):
        AFBPDecoder([[2, 0]], a, [0.1, 0.2])
    with pytest.raises(ValueError, match="probabilities"):
        AFBPDecoder(h, a, [0.0, 0.2])
    with pytest.raises(ValueError, match="graph_warm"):
        AFBPDecoder(h, a, [0.1, 0.2],
                    AFBPConfig(bp_variant="qdither", qdither_handoff="paper"))
    with pytest.raises(ValueError, match="decoder"):
        Config.model_validate({"noise": {"rates": [0.01]},
                               "decoders": [{"profile": "af_bp_v1"}]})
    zero_score = AFBPDecoder(h, a, [0.1, 0.2], AFBPConfig(
        initial_iteration_budget=0, transformed_iteration_budget=0,
        failure=FailureOptions(selection="threshold", threshold=0.0,
                               distance_decay=0.0)))
    failed = zero_score.decode([1, 1])
    assert not failed.valid and failed.status == "NONPOSITIVE_SCORE"
    assert failed.correction is None and failed.prediction is None
