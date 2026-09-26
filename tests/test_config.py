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


def test_every_top_level_config_is_active_or_analysis():
    paths = sorted((ROOT / 'config').glob('*.yaml.example'))
    assert {path.name for path in paths} == {
        'baselines.yaml.example', 'baselines_workers2.yaml.example',
        'bposd_cs0_smoke.yaml.example', 'relay_bp_smoke.yaml.example',
        'af_bp_smoke.yaml.example', 'af_bp_variants.yaml.example',
        'af_bp_factorization.yaml.example', 'af_bp_n_fact.yaml.example',
        'bb144_tiny.yaml.example',
        'all_decoders_full.yaml.example',
        'af_bp_phase1_schedule_budget.yaml.example',
        'af_bp_phase2_factorization_policy.yaml.example',
        'af_bp_phase3a_failure_top_k.yaml.example',
        'af_bp_phase3b_residual_radius.yaml.example',
        'af_bp_phase3c_distance_decay.yaml.example',
        'af_bp_phase4_failure_weights.yaml.example',
        'af_bp_phase5_feedback_frequency.yaml.example',
        'af_bp_phase6a_qdither_control.yaml.example',
        'af_bp_phase6b_qdither_interval.yaml.example',
        'af_bp_phase6c_qdither_rho.yaml.example',
        'af_bp_phase6d_qdither_chains.yaml.example',
        'af_bp_phase6e_qdither_chain_iterations.yaml.example',
        'analysis.yaml.example',
    }
    for path in paths:
        if path.name == 'analysis.yaml.example':
            continue
        config = load_config(path)
        assert all(decoder.profile in ('beam8', 'bposd', 'relay_bp', 'af_bp') for decoder in config.decoders)


def test_full_decoder_template_lists_every_supported_field():
    import yaml
    from qec_bp_benchmark.config import AFBP, RelayBP, Beam, Bposd

    path = ROOT / 'config/all_decoders_full.yaml.example'
    raw = yaml.safe_load(path.read_text())
    expected_models = {'af_bp': AFBP, 'relay_bp': RelayBP,
                       'beam8': Beam, 'bposd': Bposd}
    assert {entry['profile'] for entry in raw['decoders']} == set(expected_models)
    for entry in raw['decoders']:
        assert set(entry) == set(expected_models[entry['profile']].model_fields)
    config = load_config(path)
    assert config.sampling.shots_per_point == 2
    assert [(d.profile, d.name) for d in config.decoders] == [
        ('af_bp', 'af_bp'), ('relay_bp', 'relay_bp'),
        ('beam8', 'beam8'), ('bposd', 'bposd')]
    af, relay, beam, bposd = config.decoders
    assert (af.initial_iteration_budget, af.transformed_iteration_budget,
            af.graph_rounds, af.n_fact) == (30, 20, 5, 1)
    assert (relay.pre_iter, relay.num_sets, relay.set_max_iter) == (30, 50, 1)
    assert (beam.max_rounds, beam.initial_iters, beam.iters_per_round) == (8, 30, 20)
    assert (bposd.max_iter, bposd.osd_order) == (30, 5)


def test_phase_templates_preserve_main_physical_setup():
    import yaml
    paths = sorted((ROOT / 'config').glob('af_bp_phase*.yaml.example'))
    assert len(paths) == 12
    phase1 = yaml.safe_load(paths[0].read_text())
    main_path = ROOT / 'config/main.yaml'
    reference = yaml.safe_load(main_path.read_text()) if main_path.is_file() else phase1
    def physical(config):
        return {key: value for key, value in config.items() if key != 'decoders'} | {
            'experiment': {key: value for key, value in config['experiment'].items()
                           if key not in ('name', 'purpose')}}
    for path in paths:
        raw = yaml.safe_load(path.read_text())
        assert physical(raw) == physical(reference), path.name
        assert load_config(path).sampling.shots_per_point == 10000
        assert len({d['name'] for d in raw['decoders']}) == len(raw['decoders'])


def test_phase1_plain_bp_controls_have_no_graph_rewrite():
    config = load_config(ROOT / 'config/af_bp_phase1_schedule_budget.yaml.example')
    by_name = {decoder.name: decoder for decoder in config.decoders}
    for schedule in ('parallel', 'serial'):
        for budget in (30, 130):
            decoder = by_name[f'bp_{schedule}_{budget}']
            assert decoder.profile == 'af_bp'
            assert decoder.initial_iteration_budget == budget
            assert decoder.initial_parallel == (schedule == 'parallel')
            assert decoder.graph_rounds == decoder.n_fact == 0
    assert (by_name['bposd'].max_iter, by_name['bposd'].osd_order) == (30, 5)


@pytest.mark.parametrize(('suffix', 'varying'), [
    ('phase2_factorization_policy', {'factorization_policy'}),
    ('phase3a_failure_top_k', {'U_top_k'}),
    ('phase3b_residual_radius', {'residual_radius'}),
    ('phase3c_distance_decay', {'distance_decay'}),
    ('phase4_failure_weights', {'uncertainty_weight', 'oscillation_weight'}),
    ('phase5_feedback_frequency', {'n_fact', 'graph_rounds'}),
    ('phase6b_qdither_interval', {'qdither_alpha', 'qdither_beta'}),
    ('phase6c_qdither_rho', {'qdither_rho'}),
    ('phase6d_qdither_chains', {'qdither_chains'}),
    ('phase6e_qdither_chain_iterations', {'qdither_iterations_per_chain'}),
])
def test_phase_templates_change_only_the_named_parameters(suffix, varying):
    config = load_config(ROOT / f'config/af_bp_{suffix}.yaml.example')
    settings = [decoder.model_dump(exclude={'name'}) for decoder in config.decoders]
    reference = settings[0]
    differences = {key for candidate in settings[1:] for key in reference
                   if candidate[key] != reference[key]}
    assert differences == varying


@pytest.mark.parametrize('profile', [
    'screened_reference', 'hybrid_search_soft_ms_osd0_v1', 'search_osd0_v1',
    'hybrid_search_soft_ms_osd0_cold_v1', 'search_bp', 'lpm_dp_bp_v1',
    'beam32', 'bposd_ms30_cs0', 'bposd_ms30_cs10', 'af_bp_v1',
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


def test_relay_config_exposes_upstream_parameters_and_rejects_unpinned_gamma_arrays():
    settings = {'profile': 'relay_bp', 'alpha': .8,
                'alpha_iteration_scaling_factor': .95, 'gamma0': None,
                'pre_iter': 3, 'num_sets': 4, 'set_max_iter': 5,
                'gamma_dist_interval': [-.2, .4], 'stop_nconv': 2, 'seed': 17}
    config = Config.model_validate({'noise': {'rates': [.001]}, 'decoders': [settings]})
    resolved = config.resolved()['decoders'][0]
    for key, value in settings.items():
        assert resolved[key] == value
    assert resolved['kind'] == 'relay_bp'
    for bad in ({'explicit_gammas': [[0.1]]}, {'seed': -1},
                {'gamma_dist_interval': [.2, .2]}, {'pre_iter': 0}):
        with pytest.raises(ValidationError):
            Config.model_validate({'noise': {'rates': [.001]},
                                   'decoders': [{**settings, **bad}]})


def test_af_bp_config_exposes_every_native_scientific_setting():
    from qec_bp_benchmark.config import AFBP
    expected = {
        'history_window', 'residual_radius', 'distance_decay',
        'uncertainty_weight', 'oscillation_weight', 'U_selection', 'U_top_k',
        'U_threshold', 'factorization_policy', 'n_fact', 'graph_rounds',
        'bp_variant', 'initial_parallel', 'initial_iteration_budget',
        'transformed_iteration_budget', 'ms_scaling_factor', 'serial_order',
        'atanh_epsilon', 'qdither_phase1_iterations', 'qdither_chains',
        'qdither_iterations_per_chain', 'qdither_alpha', 'qdither_beta',
        'qdither_rho', 'qdither_handoff', 'seed', 'seed_policy',
    }
    assert set(AFBP.model_fields) == expected | {'profile', 'kind', 'name', 'enabled'}
    settings = {'profile': 'af_bp', 'U_selection': 'threshold', 'U_threshold': .2,
                'factorization_policy': 'shen_cycle_count', 'n_fact': 2,
                'bp_variant': 'serial', 'initial_parallel': False,
                'serial_order': 'natural', 'ms_scaling_factor': .8,
                'seed': 19, 'seed_policy': 'fixed'}
    config = Config.model_validate({'noise': {'rates': [.001]}, 'decoders': [settings]})
    assert config.decoders[0].kind == 'af_bp'
    for key, value in settings.items():
        assert config.resolved()['decoders'][0][key] == value
    for bad in ({'q': 2}, {'U_selection': 'all'},
                {'uncertainty_weight': 0, 'oscillation_weight': 0},
                {'qdither_alpha': .8, 'qdither_beta': .2},
                {'ms_scaling_factor': 1.1}, {'history_window': 0},
                {'bp_variant': 'qdither', 'qdither_handoff': 'paper'},
                {'initial_iteration_budget': 2**31}):
        with pytest.raises(ValidationError):
            Config.model_validate({'noise': {'rates': [.001]},
                                   'decoders': [{**settings, **bad}]})


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
