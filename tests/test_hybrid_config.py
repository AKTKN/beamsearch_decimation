"""Stage 1 contracts: resolved settings, honest dispatch and bootstrap boundaries."""
from copy import deepcopy
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from pydantic import ValidationError

from qec_bp_benchmark.config import (
    Bposd, Bposd0, Config, Hybrid, HYBRID_PROFILES, load_config,
    require_available_decoder,
)
from qec_bp_benchmark.identity import decoder_identity, run_identity

ROOT = Path(__file__).resolve().parents[1]


def test_resolved_budgets_and_ablation_identities():
    scalar = Hybrid()
    explicit = Hybrid(search={'expansions_per_cycle': [8, 8, 8]},
                      bp={'iterations_per_cycle': [6, 6, 6]})
    assert scalar == explicit
    assert decoder_identity(scalar, {}) == decoder_identity(explicit, {})
    serialized = scalar.model_dump(mode='json')
    assert serialized['search']['expansions_per_cycle'] == [8, 8, 8]
    assert serialized['bp']['iterations_per_cycle'] == [6, 6, 6]
    assert Hybrid.model_validate_json(scalar.model_dump_json()) == scalar
    serialized['search']['expansions_per_cycle'][0] = 99
    assert scalar.search.expansions_per_cycle == (8, 8, 8)
    profiles = [Hybrid(profile=p) for p in HYBRID_PROFILES]
    assert [(p.bp.enabled, p.bp.warm_start) for p in profiles] == [(True, True), (False, False), (True, False)]
    assert profiles[1].bp.iterations_per_cycle == (0, 0, 0)
    assert len({decoder_identity(p, {}) for p in profiles}) == 3
    assert len({p.name for p in profiles}) == 3
    zero = Hybrid(search={'max_cycles': 0, 'max_depth': 0})
    assert zero.search.expansions_per_cycle == zero.bp.iterations_per_cycle == ()
    assert Hybrid(search={'max_depth': 0, 'expansions_per_cycle': 0}).search.max_depth == 0
    c = Config(noise={'sweep': {'kind': 'linear', 'start': .001, 'stop': .003, 'count': 3}},
               decoders=profiles, timing={'profiling': 'phases'})
    assert c.resolved()['decoders'][0]['search']['expansions_per_cycle'] == [8, 8, 8]
    assert c.noise.expanded_rates == (.001, .002, .003)


@pytest.mark.parametrize('patch', [
    {'unknown': 1}, {'kind': 'beam'}, {'algorithm_version': 'future'},
    {'search': {'max_depth': -1}}, {'search': {'max_depth': 2**31}},
    {'search': {'max_cycles': -1}}, {'search': {'max_cycles': 65537}},
    {'search': {'max_cycles': True}}, {'search': {'max_cycles': 2.0}},
    {'search': {'expansions_per_cycle': [1, 2]}},
    {'search': {'max_cycles': 0, 'expansions_per_cycle': [8]}},
    {'search': {'expansions_per_cycle': -1}},
    {'search': {'expansions_per_cycle': [1, True, 1]}},
    {'search': {'expansions_per_cycle': 2**64 - 1}},
    {'search': {'max_generated_nodes': 0}}, {'search': {'max_generated_nodes': 2**64}},
    {'search': {'prefix_cpu_budget_ns': 0}}, {'search': {'prefix_cpu_budget_ns': 2**63}},
    {'search': {'prefix_cpu_budget_ns': float('inf')}},
    {'search': {'detector_order': 'random'}}, {'search': {'branch_order': 'posterior'}},
    {'search': {'heuristic': 'none'}}, {'search': {'goal_test': 'on_pop'}},
    {'search': {'guidance_selection': 'all_patterns'}},
    {'bp': {'enabled': False}}, {'bp': {'warm_start': False}},
    {'bp': {'enabled': 1}}, {'bp': {'method': 'sum_product'}},
    {'bp': {'schedule': 'serial'}}, {'bp': {'iterations_per_cycle': [1, 1]}},
    {'bp': {'iterations_per_cycle': 0}}, {'bp': {'iterations_per_cycle': 2**31}},
    {'bp': {'llr_clip': 0}}, {'bp': {'llr_clip': float('inf')}},
    {'bp': {'llr_clip': '25'}}, {'bp': {'scaling_factor': 1.1}},
    {'bp': {'scaling_factor': float('nan')}}, {'bp': {'hint_margin_llr': -1}},
    {'bp': {'hint_margin_llr': float('inf')}}, {'bp': {'hard_decision_zero': 'zero'}},
    {'bp': {'replace_previous_hint': False}}, {'bp': {'hint_policy': 'hard_fixation'}},
    {'fallback': {'backend': 'BpOsdDecoder'}}, {'fallback': {'osd_order': 1}},
    {'fallback': {'osd_order': False}}, {'fallback': {'osd_method': 'OSD_E'}},
    {'fallback': {'llr_source': 'channel_only'}}, {'fallback': {'ordering': 'absolute_llr'}},
    {'numerics': {'dtype': 'float32'}}, {'numerics': {'fast_math': True}},
    {'numerics': {'heuristic_reduction': 'unordered'}}, {'native_threads': 2},
    {'profile': 'search_osd0_v1', 'bp': {'enabled': True}},
    {'profile': 'search_osd0_v1', 'bp': {'iterations_per_cycle': 6}},
    {'profile': 'hybrid_search_soft_ms_osd0_cold_v1', 'bp': {'warm_start': True}},
])
def test_invalid_hybrid_options(patch):
    with pytest.raises(ValidationError):
        Hybrid.model_validate(patch)


def test_effective_options_and_profiling_are_identified():
    from datetime import datetime, timezone
    base = Hybrid().model_dump()
    changes = [('search', 'max_depth', 3), ('search', 'max_cycles', 2),
               ('search', 'expansions_per_cycle', [9, 8, 8]),
               ('search', 'max_generated_nodes', 4000),
               ('search', 'prefix_cpu_budget_ns', 100000),
               ('bp', 'iterations_per_cycle', [7, 6, 6]), ('bp', 'scaling_factor', .8),
               ('bp', 'llr_clip', 30.), ('bp', 'hint_margin_llr', 9.)]
    for group, key, value in changes:
        data = deepcopy(base)
        data[group][key] = value
        if key == 'max_cycles':
            data['search']['expansions_per_cycle'] = 8
            data['bp']['iterations_per_cycle'] = 6
        assert decoder_identity(Hybrid.model_validate(data), {}) != decoder_identity(Hybrid(), {})
    config = Config(noise={'rates': [.001]}, decoders=[Hybrid()])
    data = config.model_dump()
    data['timing']['profiling'] = 'phases'
    profiled = Config.model_validate(data)
    now = datetime.now(timezone.utc)
    assert run_identity(config, now, 'same') != run_identity(profiled, now, 'same')
    # Profiling is an execution context, not a different correction algorithm.
    assert decoder_identity(config.decoders[0], {}) == decoder_identity(profiled.decoders[0], {})


def test_explicit_dispatch_and_pending_hybrid_storage(tmp_path):
    from qec_bp_benchmark.decoders import DecoderAdapter, implementation_identity
    from qec_bp_benchmark.runner.pipeline import run_benchmark
    for profile in ('screened_reference', 'bposd_ms30_cs0', 'bposd_ms30_cs10', 'beam8', 'beam32'):
        require_available_decoder(profile)
    for profile in HYBRID_PROFILES:
        require_available_decoder(profile)
        assert implementation_identity(profile)['fork_build']['profile']=='HSBP-ALG-1.0'
    with pytest.raises(ValueError, match='unsupported'):
        implementation_identity('future_decoder')


def test_cs0_identity_and_legacy_parameters():
    from analysis.plots import decoder_label
    from qec_bp_benchmark.decoders import implementation_identity
    assert Bposd().osd_order == 10
    assert Bposd(osd_order=2).osd_order == 2  # Preserve the legacy configurable order.
    assert Bposd0().osd_order == 0
    with pytest.raises(ValidationError):
        Bposd0(osd_order=10)
    impl0 = implementation_identity('bposd_ms30_cs0')
    impl10 = implementation_identity('bposd_ms30_cs10')
    assert impl0 == impl10  # Same real upstream library, distinct complete settings.
    assert decoder_identity(Bposd0(), impl0) != decoder_identity(Bposd(), impl10)
    assert decoder_identity(Bposd0(), impl0) != decoder_identity(Bposd(osd_order=0), impl10)
    for decoder in (Bposd0(), Bposd()):
        label = decoder_label({'decoder_profile': decoder.profile, 'decoder_name': decoder.name,
                               'decoder_id': 'test', 'decoder_parameters': decoder.model_dump()})
        assert f'OSD_CS({decoder.osd_order})' in label and 'beam' not in label
    with pytest.raises(ValueError, match='unsupported'):
        decoder_label({'decoder_profile': 'future'})
    for template in (ROOT / 'config').rglob('*.yaml.example'):
        if template.name == 'analysis.yaml.example':
            from analysis import load_analysis_config
            assert load_analysis_config(template).analysis.bootstrap_count == 2000
        elif ('production' in template.name or 'hybrid_frontier' in template.name or
              'search_bp_v1' in str(template) or 'search_bp_v2' in str(template)):
            with pytest.raises(ValidationError):
                load_config(template)
        else:
            loaded = load_config(template)
            assert Config.model_validate_json(loaded.model_dump_json()) == loaded


def test_analysis_config_is_independent_from_simulation_yaml(tmp_path):
    from analysis import load_analysis_config

    settings = load_analysis_config(ROOT / "config/analysis.yaml.example")
    assert settings.analysis.input == ROOT / "assets/runs"
    with pytest.raises(ValidationError):
        load_analysis_config(ROOT / "config/search_bp.yaml.example")
    duplicate = tmp_path / "analysis.yaml"
    duplicate.write_text("analysis: {confidence: 0.9, confidence: 0.8}\n")
    with pytest.raises(ValueError, match="duplicate"):
        load_analysis_config(duplicate)


def test_setup_preserves_local_edits_and_symlinks(tmp_path):
    (tmp_path / 'scripts').mkdir()
    for directory in ('config', 'notebook'):
        shutil.copytree(ROOT / directory, tmp_path / directory,
                        ignore=lambda path, names: [n for n in names if (Path(path)/n).is_file() and not n.endswith('.example')])
    script = tmp_path / 'scripts/setup_local_files.sh'
    shutil.copyfile(ROOT / 'scripts/setup_local_files.sh', script)
    local = tmp_path / 'config/search_bp.yaml'
    local.write_text('noise: {rates: [0.0123, 0.0234]}\n# local experiment\n')
    legacy_local = tmp_path / 'config/legacy/smoke.yaml'
    legacy_local.write_text('noise: {rates: [0.013]}\n# preserved legacy experiment\n')
    symlink = tmp_path / 'config/bposd_cs0_smoke.yaml'
    symlink.symlink_to(tmp_path / 'absent-user-file')
    for _ in range(2):
        subprocess.run(['bash', str(script)], check=True)
    assert local.read_text() == 'noise: {rates: [0.0123, 0.0234]}\n# local experiment\n'
    assert symlink.is_symlink() and not symlink.exists()
    assert legacy_local.read_text() == 'noise: {rates: [0.013]}\n# preserved legacy experiment\n'
    for template in (tmp_path / 'config').rglob('*.yaml.example'):
        target = template.with_suffix('')
        if target not in (local, symlink, legacy_local):
            assert target.read_bytes() == template.read_bytes()


def test_bootstrap_imports_no_heavy_libraries():
    code = '''
import sys
from qec_bp_benchmark.config import Config
from qec_bp_benchmark.identity import decoder_identity
from qec_bp_benchmark.runner.pipeline import run_benchmark
from qec_bp_benchmark.runner.worker import initialize
c = Config(noise={"rates": [.001]}, decoders=[{"profile": "hybrid_search_soft_ms_osd0_v1"}])
decoder_identity(c.decoders[0], {})
for name in ("numpy", "scipy", "stim", "ldpc", "pyarrow", "qldpc", "beam_search_decoder"):
    assert name not in sys.modules, name
'''
    subprocess.run([sys.executable, '-c', code], check=True, cwd=ROOT)
