from datetime import datetime, timezone
from pathlib import Path
import pytest
from pydantic import ValidationError
from qec_bp_benchmark.config import Config, load_config
from qec_bp_benchmark.identity import scientific_identity, sampling_identity, decoder_identity, run_identity
from qec_bp_benchmark import _native

ROOT = Path(__file__).resolve().parents[1]


def test_native_import():
    assert "binary64" in _native.build_identity()


def test_examples_and_paths():
    c = load_config(ROOT / "config/smoke.yaml")
    assert c.circuit.cache == ROOT / "simulation_data"
    assert c.noise.expanded_rates == (.001,)
    assert c.execution.max_pending == 8
    assert len(c.resolved()["experiment"]["instances"]) == 4
    assert load_config(ROOT / "config/latency_smoke.yaml").execution.workers == 1
    sweep = load_config(ROOT / "config/decoder_sweep.yaml")
    assert sweep.noise.expanded_rates == (.0005, .001)
    assert sweep.decoders[-1].beam_width == 32
    with pytest.raises(ValidationError, match="nonempty"):
        load_config(ROOT / "config/production_template.yaml")


@pytest.mark.parametrize("patch", [
    {"noize": {}}, {"execution": {"workers": 1.2}}, {"execution": {"native_threads": 2}},
    {"noise": {"rates": [.001, .001]}}, {"noise": {"rates": [float("nan")]}},
    {"noise": {"rates": [.001], "sweep": {"kind": "linear", "start": .001, "stop": .1, "count": 3}}},
    {"noise": {"sweep": {"kind": "log", "start": 0, "stop": .1, "count": 3}}},
    {"noise": {"rates": [.5], "multipliers": {"idle": 3}}},
    {"dem": {"decompose_errors": True}}, {"timing": {"mode": "isolated_latency"}},
    {"decoders": [{"profile": "beam8", "bp_method": "sum_product"}]},
    {"decoders": [{"profile": "screened_reference", "q": 0}]},
    {"decoders": [{"profile": "screened_reference", "q": 17}]},
    {"decoders": [{"profile": "screened_reference", "Lmax": 31}]},
    {"experiment": {"codes": [{"family": "bb72", "distances": [12]}]}},
])
def test_reject(patch):
    with pytest.raises(ValidationError):
        Config.model_validate({"noise": {"rates": [.001]}, **patch})


def test_yaml_duplicate_and_unsafe(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("noise: {rates: [0.001], rates: [0.002]}")
    with pytest.raises(ValueError, match="duplicate"):
        load_config(path)
    path.write_text("!!python/object/apply:os.system ['false']")
    import yaml
    with pytest.raises(yaml.YAMLError):
        load_config(path)


def test_identity_separation():
    c = load_config(ROOT / "config/smoke.yaml")
    data = c.model_dump()
    data["execution"]["workers"] = 2
    data["decoders"] = list(reversed(data["decoders"]))
    data["output"]["root"] = Path("/tmp/other")
    other = Config.model_validate(data)
    instance = {"family": "surface", "distance": 5, "rounds": 5, "p": .001}
    assert scientific_identity(instance, {"circuit": "abc"}, c) == scientific_identity(instance, {"circuit": "abc"}, other)
    assert sampling_identity(c, "1") == sampling_identity(other, "1")
    assert scientific_identity(instance, {}, c) != scientific_identity({**instance, "p": .0010000000000001}, {}, c)
    assert decoder_identity(c.decoders[0], {"commit": "a"}) != decoder_identity(c.decoders[0], {"commit": "b"})
    now = datetime.now(timezone.utc)
    assert run_identity(c, now, "a") != run_identity(other, now, "a")
    assert sampling_identity(c, "1") != sampling_identity(c, "2")


def test_linear_grid():
    c = Config.model_validate({"noise": {"sweep": {"kind": "linear", "start": 0, "stop": .02, "count": 3}}})
    assert c.noise.expanded_rates == (0, .01, .02)
