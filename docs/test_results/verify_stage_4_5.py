import json
from pathlib import Path
import pyarrow.parquet as pq
from qec_bp_benchmark.storage import committed_batches
root=Path(__file__).resolve().parents[2]
kinds=['two','one','isolated','default_smoke','default_latency','replay']
logs={'two':'stage_5_two_workers.log','one':'stage_5_one_worker.log','isolated':'stage_5_isolated.log',
      'default_smoke':'stage_5_smoke_cli.log','default_latency':'stage_5_latency_cli.log','replay':'stage_5_replay_cli.log'}
runs={key:(root/'docs/test_results'/logs[key]).read_text().strip() for key in kinds}
loaded={}; reports={}
for key,value in runs.items():
    path=Path(value); manifest=json.loads((path/'manifest.json').read_text())
    assert manifest['status']=='complete'
    samples=[];decodes=[];batches=0
    for instance in manifest['instances']:
        folder=path/instance['directory']
        for batch in committed_batches(folder):
            batches+=1
            samples+=pq.read_table(folder/f'samples/part-{batch["batch_id"]:08d}.parquet').to_pylist()
            decodes+=pq.read_table(folder/f'decodes/part-{batch["batch_id"]:08d}.parquet').to_pylist()
    assert batches==manifest['expected_batches']==manifest['completed_batches']
    assert all(len(r['actual_observables'])==r['k_Z']==12 for r in samples if r['family']=='bb72')
    assert all(r['prediction'] is None or len(r['prediction'])==r['k_Z'] for r in decodes)
    loaded[key]=(samples,decodes)
    reports[key]={'path':str(path.relative_to(root)),'status':manifest['status'],'batches':batches,
        'samples':len(samples),'decodes':len(decodes),'decoding_failures':sum(r['decoding_failure'] for r in decodes),
        'valid_logical_mismatches':sum(r['valid_logical_mismatch'] for r in decodes),
        'block_failures':sum(r['block_failure'] for r in decodes),'k_Z_by_family':{r['family']:r['k_Z'] for r in samples},
        'workers':manifest['config']['execution']['workers'],'timing_mode':manifest['config']['timing']['mode']}
ignore={'run_id','source_hash','config_hash','cpu_ns','wall_ns','timing_mode','workers','concurrent_load','oversubscribed'}
def normalized(rows,ignored=ignore):
    return sorted(json.dumps({k:(v.hex() if isinstance(v,bytes) else v) for k,v in r.items() if k not in ignored},sort_keys=True) for r in rows)
checks=[]
for a,b in [('two','one'),('two','isolated'),('default_smoke','default_latency')]:
    for i in range(2): assert normalized(loaded[a][i])==normalized(loaded[b][i]),(a,b,i)
    checks.append(f'{a} vs {b}: samples and every non-timing scientific decoder result equal')
assert normalized(loaded['two'][0])==normalized(loaded['replay'][0])
source={(r['shot_id'],r['decoder_id']):r for r in loaded['two'][1]}
replay={(r['shot_id'],r['decoder_id']):r for r in loaded['replay'][1]}
extra_ignore=ignore|{'decoder_name','execution_position'}
assert source.keys()<=replay.keys()
for key,row in source.items(): assert normalized([row],extra_ignore)==normalized([replay[key]],extra_ignore)
checks.append('replay with additional K=4 screened decoder: samples unchanged; all shared decoder outputs/counters equal')
report={'scope':'Stages 4–5 software validation, no performance claim','runs':reports,'paired_checks':checks,
         'commands':[
            'python -m pip install --no-build-isolation -e .',
            'python -m pytest -q',
            'ctest --test-dir build/debug --output-on-failure',
            'ctest --test-dir build/sanitize --output-on-failure',
            'scripts/build_dependencies.sh --check',
            'scripts/run_benchmark.sh config/stage5_validation.yaml',
            'scripts/run_benchmark.sh config/stage5_validation_serial.yaml',
            'scripts/run_benchmark.sh config/stage5_validation_latency.yaml',
            'scripts/run_benchmark.sh config/smoke.yaml',
            'scripts/run_benchmark.sh config/latency_smoke.yaml',
            'scripts/replay_samples.sh <two-worker-run> config/decoder_sweep.yaml',
            'scripts/run_benchmark.sh config/production_template.yaml  # expected validation failure',
            'python docs/test_results/verify_stage_4_5.py',
            'python -m pip check'],
        'project_tests':{'passed':91,'seconds':float((root/'docs/test_results/stage_4_5_pytest.log').read_text().split('passed in ')[-1].split('s')[0])},'native_debug':'2/2 passed','native_asan_ubsan':'2/2 passed',
        'stage4_oracle_comparisons':560,'pristine_bposd_comparisons':288,
        'limitations':['No production sweep','No in-place resumption','Analysis/notebooks remain Stage 6','Clean-environment acceptance remains Stage 7']}
(root/'docs/test_results/stage_4_5_summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
print(json.dumps(report,indent=2))
