"""Run bounded hybrid E2E acceptance with fresh artifacts and saved-data consumers."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def main() -> None:
    """Create a new output tree; fail on any CLI, identity or scientific mismatch.

    Executes four shots each of surface d=3 and BB72 R=6 per timing trial. The
    output contains configs, logs, immutable run paths and a verification index.
    Existing directories are rejected; no production rates or sweeps are selected.
    """
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True,help='New exclusive acceptance directory')
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    from qec_bp_benchmark.config import load_config
    from qec_bp_benchmark.runner import configure_execution
    config=load_config(ROOT/'config/hybrid_smoke.yaml.example')
    configure_execution(config)
    import yaml
    from analysis.io import load_run
    from analysis.validation import compare_runs
    from qec_bp_benchmark.storage import atomic_json,sha256
    base=config.model_dump(mode='json')
    base['output']['root']=str(output/'runs');base['circuit']['cache']=str(output/'fresh_circuits')
    base['analysis']['output']=str(output/'reports')
    paths={};commands=[]
    def command(name: str, script: str, *arguments: str | Path) -> str:
        argv=[sys.executable,str(ROOT/'python_scripts'/script),*map(str,arguments)]
        commands.append(argv)
        print(f'Running {name}',file=sys.stderr,flush=True)
        with (output/f'{name}.stdout').open('x') as stdout,(output/f'{name}.stderr').open('x') as stderr:
            subprocess.run(argv,cwd=ROOT,stdout=stdout,stderr=stderr,check=True)
        return (output/f'{name}.stdout').read_text().strip()
    for name in ('single','latency','multi','replay','none','ablations'):
        data=json.loads(json.dumps(base))
        data['execution']['workers']=2 if name in ('multi','replay') else 1
        data['timing']['mode']='isolated_latency' if name in ('latency','none','ablations') else 'throughput'
        data['timing']['profiling']='none' if name=='none' else 'phases'
        if name=='ablations':
            data['decoders']=load_config(ROOT/'config/hybrid_ablations.yaml.example').model_dump(mode='json')['decoders']
        path=output/f'{name}.yaml';path.write_text(yaml.safe_dump(data,sort_keys=False))
        if name in ('replay','none'):
            paths[name]=command(name,'replay_samples.py',paths['single'],path,'--verbose')
        else: paths[name]=command(name,'run_benchmark.py',path,'--verbose')
    runs={name:load_run(path) for name,path in paths.items()}
    comparisons={name:compare_runs(runs['single'],runs[name]) for name in ('latency','multi','replay','none')}
    counts={}
    for name,run in runs.items():
        assert run.samples.num_rows==8
        assert run.decodes.num_rows==8*(4 if name=='ablations' else 3)
        assert all(len(r['actual_observables'])==12 for r in run.samples.to_pylist() if r['family']=='bb72')
        assert all(r['rounds']==6 for r in run.samples.to_pylist() if r['family']=='bb72')
        for row in run.decodes.to_pylist():
            if row['algorithm_version']:
                assert row['timing_accounting_ok'] is (None if name=='none' else True)
        counts[name]={'samples':run.samples.num_rows,'decodes':run.decodes.num_rows,
            'rounds':run.hybrid_rounds.num_rows,'phases':run.decoder_phases.num_rows}
    report=Path(command('analysis','analyze_benchmark.py',output/'ablations.yaml','--run',paths['ablations']))
    manifest=json.loads((report/'manifest.json').read_text())
    assert manifest['status']=='complete'
    assert all(sha256(report/name)==digest for name,digest in manifest['files'].items())
    pairs=json.loads((report/'paired.json').read_text())['groups']
    assert len(pairs)==12 and all(p['noninferiority'] is None for p in pairs)
    assert all(t['difference_ns']==t['four_term_sum_ns'] for p in pairs for t in p['integer_totals'].values())
    notebook=Path(command('notebook','execute_notebook.py',output/'single.yaml','--run',paths['single'],
        '--notebook',ROOT/'notebook/benchmark_analysis.ipynb.example','--output',output/'executed.ipynb'))
    cells=json.loads(notebook.read_text())['cells']
    assert all(c['execution_count'] is not None and not any(o['output_type']=='error' for o in c['outputs']) for c in cells if c['cell_type']=='code')
    atomic_json(output/'verification.json',{'status':'passed','commands':commands,'runs':paths,'counts':counts,
        'comparisons':comparisons,'all_12_bb_labels':True,'report':str(report),'report_files':len(manifest['files']),
        'paired_groups':len(pairs),'notebook':str(notebook),'notebook_sha256':sha256(notebook),
        'limits':'Bounded software checks in the existing environment; no scientific performance claim.'},exclusive=True)
    print(output/'verification.json',flush=True)


if __name__=='__main__': main()
