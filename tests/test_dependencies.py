from pathlib import Path
import numpy as np
import ldpc
from ldpc import BpOsdDecoder
from beam_search_decoder import BeamSearchDecoder

ROOT = Path(__file__).resolve().parents[1]


def test_fork_import_location():
    assert (ROOT / "external_lib/ldpc") in Path(ldpc.__file__).resolve().parents


def test_native_baseline_parameters():
    H = np.array([[1, 1, 0], [0, 1, 1]], dtype=np.uint8)
    p = [.1] * 3
    osd = BpOsdDecoder(H, error_channel=p, bp_method="minimum_sum", schedule="parallel",
                      max_iter=30, ms_scaling_factor=1.0, osd_method="OSD_CS", osd_order=10,
                      omp_thread_count=1)
    beam = BeamSearchDecoder(H, error_channel=p, max_rounds=10, beam_width=8,
                             num_results=1, initial_iters=30, iters_per_round=20)
    for key, expected in {"max_rounds": 10, "beam_width": 8, "num_results": 1,
                          "initial_iters": 30, "iters_per_round": 20}.items():
        assert getattr(beam, key) == expected
    for s in ([0, 0], [1, 0], [1, 1]):
        s = np.array(s, dtype=np.uint8)
        assert np.array_equal(H @ osd.decode(s) % 2, s)
        result = np.asarray(beam.decode(s))
        assert np.array_equal(H @ result.reshape(-1, 3)[0] % 2, s)


def test_bb_api_audit():
    from sympy.abc import x, y
    from qldpc import codes, circuits
    from qldpc.objects import Pauli
    code = codes.BBCode({x: 6, y: 6}, x**3 + y + y**2, y**3 + x + x**2)
    assert len(code) == 72 and code.dimension == 12
    c = circuits.get_memory_experiment(code, basis=Pauli.Z, num_rounds=6)
    assert c.num_observables == 12
    assert c.num_measurements == 6 * 72 + 72
    model = circuits.NoiseModel(clifford_1q_error=.001, clifford_2q_error=.001,
                               idle_error=.001, reset_error=.001, readout_error=.001)
    noisy = model.noisy_circuit(c)
    assert "DEPOLARIZE2" in str(noisy)
    noisy.detector_error_model(decompose_errors=False, approximate_disjoint_errors=False)


def test_pinned_provider_import_location():
    import qldpc
    import beam_search_decoder
    assert ROOT/'external_lib/qLDPC' in Path(qldpc.__file__).resolve().parents
    assert ROOT/'external_lib/BeamSearchDecoder/decoder' in Path(beam_search_decoder.__file__).resolve().parents
