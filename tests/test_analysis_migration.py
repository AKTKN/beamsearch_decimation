"""Consumer migration: frozen legacy parity, independent settings and entry points."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from analysis import load_analysis_config
from analysis.hybrid import summarize_pair
from analysis.legacy.hybrid import summarize_pair as legacy_summarize_pair
from qec_bp_benchmark.config import Analysis
from test_hybrid_analysis import pair
from test_analysis import saved_run

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('unit', ['shot', 'batch'])
@pytest.mark.parametrize('large', [False, True])
def test_bootstrap_matches_frozen_legacy_for_unequal_batches(unit, large):
    pairs = [pair(i, reached=i % 3 == 0, failed=i % 5 == 0,
                  mismatch=i % 4 == 0, hybrid_time=80 + 17*i,
                  baseline_time=0 if i < 2 else 100 + 31*i) for i in range(13)]
    for i, (h, b) in enumerate(pairs):
        h['batch_id'] = b['batch_id'] = i // 5
        if large:
            for clock in ('cpu', 'wall'):
                # Force Python-integer reduction, preserving tiny differences
                # and signed residuals even when sums exceed signed int64.
                h[f'{clock}_ns'] += 2**62
                b[f'{clock}_ns'] += 2**62
                h[f'service_other_{clock}_ns'] += 2**62
    settings = Analysis(bootstrap_count=61, bootstrap_seed=78, bootstrap_unit=unit,
                        accuracy_margin_absolute=.05)
    original = copy.deepcopy(pairs)
    assert summarize_pair(pairs, settings=settings) == legacy_summarize_pair(pairs, settings=settings)
    assert pairs == original


def test_bootstrap_null_measurements_zero_baseline_and_permutation():
    pairs = [pair(i, baseline_time=0) for i in range(5)]
    for h, _ in pairs:
        for key in h:
            if key.endswith('_ns') and key not in ('cpu_ns', 'wall_ns'):
                h[key] = None
        h['timing_accounting_ok'] = None
    settings = Analysis(bootstrap_count=20)
    result = summarize_pair(pairs, settings=settings)
    assert result == legacy_summarize_pair(pairs, settings=settings)
    assert result == summarize_pair(list(reversed(pairs)), settings=settings)
    assert result['estimates']['cpu_ratio'] is None
    assert result['estimates']['cpu_prefix_ns'] is None


def test_analysis_only_config_strict_paths_and_full_config_compatibility(tmp_path):
    path = tmp_path/'analysis.yaml'
    path.write_text('analysis:\n  input: saved\n  output: reports\n  bootstrap_count: 7\n')
    config = load_analysis_config(path)
    assert config.analysis.input == tmp_path/'saved'
    assert config.analysis.output == tmp_path/'reports'
    assert config.analysis.bootstrap_count == 7
    full = load_analysis_config(ROOT/'config/hybrid_smoke.yaml.example')
    assert full.analysis.input == ROOT/'assets/runs'
    for text in ('analysis:\n  typo: true\n', 'analysis:\n  bootstrap_count: 0\n',
                 'analysis: {}\nanalysis: {}\n', 'analysis: {}\ndecoders: [{profile: invalid}]\n'):
        path.write_text(text)
        with pytest.raises(ValueError):
            load_analysis_config(path)


def test_legacy_python_snapshot_is_byte_preserved():
    snapshot = json.loads((ROOT/'analysis/legacy/snapshot.json').read_text())
    for name, digest in snapshot['sha256'].items():
        if name.startswith('analysis/'):
            assert hashlib.sha256((ROOT/'analysis/legacy'/Path(name).name).read_bytes()).hexdigest() == digest


def test_analysis_settings_do_not_import_runner_or_decoders():
    subprocess.run([sys.executable, '-c',
        'from analysis import load_analysis_config; import sys; '
        f'load_analysis_config({str(ROOT / "config/analysis.yaml.example")!r}); '
        'assert not any(k in sys.modules for k in '
        '("qec_bp_benchmark.runner", "ldpc", "stim", "qldpc", "beam_search_decoder"))'], check=True)


def test_notebook_rejects_mixed_acceptance_configuration(monkeypatch):
    import qec_bp_benchmark.config as config
    monkeypatch.setattr(config, '__file__', str(ROOT/'analysis/legacy/hybrid.py'))
    # Simulate a current analysis import alongside a stale acceptance Config.
    # The diagnostic must precede run loading or YAML validation.
    notebook = json.loads((ROOT/'notebook/benchmark_analysis.ipynb.example').read_text())
    cell = next(c for c in notebook['cells'] if c['cell_type'] == 'code')
    monkeypatch.chdir(ROOT)
    with pytest.raises(RuntimeError, match='Configuration package loaded from another checkout'):
        exec(''.join(cell['source']), {})


def test_current_and_legacy_consumers_execute_saved_data(saved_run, tmp_path):
    settings = tmp_path/'analysis.yaml'
    settings.write_text(f'analysis:\n  output: {tmp_path}/reports\n  plots: []\n  bootstrap_count: 5\n')
    command = [sys.executable, str(ROOT/'python_scripts/analyze_benchmark.py'), str(settings), '--run', str(saved_run)]
    done = subprocess.run(command+['--verbose'], check=True, text=True, capture_output=True)
    report = Path(done.stdout.strip())
    manifest = json.loads((report/'manifest.json').read_text())
    assert manifest['status'] == 'complete' and manifest['decode_rows'] == 9
    assert manifest['analysis_runtime']['python_executable'] == sys.executable
    assert 'Validating saved run' in done.stderr
    assert len(done.stdout.splitlines()) == 1
    from analysis.legacy import load_run, create_report
    assert load_run(saved_run).samples.num_rows == 3
    old_report = create_report([saved_run], tmp_path/'legacy', settings=Analysis(plots=()))
    assert json.loads((old_report/'manifest.json').read_text())['status'] == 'complete'
    output = tmp_path/'executed.ipynb'
    subprocess.run([sys.executable, str(ROOT/'python_scripts/execute_notebook.py'), str(settings),
                    '--run', str(saved_run), '--output', str(output)], check=True, capture_output=True, text=True)
    notebook = json.loads(output.read_text())
    code = [c for c in notebook['cells'] if c['cell_type'] == 'code']
    assert all(c['execution_count'] is not None for c in code)
    assert not any(o['output_type'] == 'error' for c in code for o in c['outputs'])
    assert notebook['metadata']['kernelspec']['name'] == 'search_decimation'
