from datetime import datetime, timezone
from pathlib import Path
import pytest
from pydantic import ValidationError

from qec_bp_benchmark.config import Config, load_config, require_available_decoder
from qec_bp_benchmark.identity import scientific_identity, sampling_identity, decoder_identity, run_identity

ROOT = Path(__file__).resolve().parents[1]


def test_active_example_and_paths():
    config = load_config(ROOT / 'config/baselines.yaml.example')
    assert config.circuit.cache == ROOT / 'simulation_data'
    assert config.output.root == ROOT / 'assets/runs'
    assert {d.profile for d in config.decoders} == {'beam8', 'bposd'}
    assert config.decoders[1].osd_order == 10
    assert config.execution.max_pending == 2


def test_every_top_level_config_is_an_active_baseline():
    paths = sorted((ROOT / 'config').glob('*.yaml.example'))
    assert {path.name for path in paths} == {
        'baselines.yaml.example', 'baselines_workers2.yaml.example',
        'bposd_cs0_smoke.yaml.example', 'analysis.yaml.example',
    }
    for path in paths:
        if path.name == 'analysis.yaml.example':
            continue
        config = load_config(path)
        assert all(decoder.profile in ('beam8', 'bposd') for decoder in config.decoders)


@pytest.mark.parametrize('profile', [
    'screened_reference', 'hybrid_search_soft_ms_osd0_v1', 'search_osd0_v1',
    'hybrid_search_soft_ms_osd0_cold_v1', 'search_bp', 'lpm_dp_bp_v1',
    'beam32', 'bposd_ms30_cs0', 'bposd_ms30_cs10', 'af_bp', 'relay_bp',
])
def test_legacy_and_future_profiles_are_not_active(profile):
    with pytest.raises(ValueError):
        require_available_decoder(profile)
    with pytest.raises(ValidationError):
        Config.model_validate({'noise': {'rates': [.001]}, 'decoders': [{'profile': profile}]})


@pytest.mark.parametrize('patch', [
    {'noize': {}}, {'execution': {'workers': 1.2}}, {'execution': {'native_threads': 2}},
    {'noise': {'rates': [.001, .001]}}, {'noise': {'rates': [float('nan')]}},
    {'noise': {'rates': [.001], 'sweep': {'kind': 'linear', 'start': .001, 'stop': .1, 'count': 3}}},
    {'noise': {'sweep': {'kind': 'log', 'start': 0, 'stop': .1, 'count': 3}}},
    {'noise': {'rates': [.5], 'multipliers': {'idle': 3}}},
    {'dem': {'decompose_errors': True}}, {'timing': {'mode': 'isolated_latency'}},
    {'decoders': [{'profile': 'beam8', 'bp_method': 'sum_product'}]},
    {'decoders': [{'profile': 'beam8', 'beam_width': 32}]},
    {'decoders': [{'profile': 'bposd', 'osd_order': -1}]},
    {'experiment': {'codes': [{'family': 'bb72', 'distances': [12]}]}},
    {'experiment': {'codes': [{'family': 'bb144', 'distances': [6]}]}},
    {'analysis': {'input': '../assets/runs'}},
])
def test_reject(patch):
    with pytest.raises(ValidationError):
        Config.model_validate({'noise': {'rates': [.001]}, **patch})


def test_osd_order_is_configurable():
    for order in (0, 2, 10):
        config = Config.model_validate({'noise': {'rates': [.001]},
            'decoders': [{'profile': 'bposd', 'osd_order': order}]})
        assert config.decoders[0].osd_order == order
        assert config.resolved()['decoders'][0]['osd_order'] == order


def test_yaml_duplicate_and_unsafe(tmp_path):
    path = tmp_path / 'bad.yaml'
    path.write_text('noise: {rates: [0.001], rates: [0.002]}')
    with pytest.raises(ValueError, match='duplicate'):
        load_config(path)
    path.write_text("!!python/object/apply:os.system ['false']")
    import yaml
    with pytest.raises(yaml.YAMLError):
        load_config(path)


def test_identity_separation():
    c = load_config(ROOT / 'config/baselines.yaml.example')
    data = c.model_dump()
    data['execution']['workers'] = 2
    data['decoders'] = list(reversed(data['decoders']))
    data['output']['root'] = Path('/tmp/other')
    other = Config.model_validate(data)
    instance = {'family': 'surface', 'distance': 5, 'rounds': 5, 'p': .001}
    assert scientific_identity(instance, {'circuit': 'abc'}, c) == scientific_identity(instance, {'circuit': 'abc'}, other)
    assert sampling_identity(c, '1') == sampling_identity(other, '1')
    assert scientific_identity(instance, {}, c) != scientific_identity({**instance, 'p': .0010000000000001}, {}, c)
    assert decoder_identity(c.decoders[0], {'commit': 'a'}) != decoder_identity(c.decoders[0], {'commit': 'b'})
    now = datetime.now(timezone.utc)
    assert run_identity(c, now, 'a') != run_identity(other, now, 'a')
    assert sampling_identity(c, '1') != sampling_identity(c, '2')


def test_linear_grid_and_bb144():
    c = Config.model_validate({'noise': {'sweep': {'kind': 'linear', 'start': 0, 'stop': .02, 'count': 3}}})
    assert c.noise.expanded_rates == (0, .01, .02)
    config = Config.model_validate({'noise': {'rates': [.001]},
        'experiment': {'codes': [{'family': 'bb144', 'distances': [12]}]}})
    assert config.resolved()['experiment']['instances'] == [
        {'family': 'bb144', 'distance': 12, 'rounds': 12, 'round_override': False}]
