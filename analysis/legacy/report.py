"""One reusable report workflow shared by CLI and notebook consumers."""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
from typing import Sequence
import uuid
from qec_bp_benchmark.legacy.decimation.config import Analysis
from qec_bp_benchmark.identity import content_hash
from qec_bp_benchmark.storage import atomic_json,sha256
from .io import load_run,select_records
from .statistics import aggregate_failures,aggregate_timings
from .plots import plot_failure_rates,plot_timings,plot_hybrid
from .hybrid import stage_statistics,paired_statistics


def create_report(run_paths: Sequence[str | Path], output_root: str | Path, *, settings: Analysis | None=None,
                  allow_incomplete: bool=False, families: Sequence[str] | None=None,
                  distances: Sequence[int] | None=None, decoder_ids: Sequence[str] | None=None,
                  timing_modes: Sequence[str] | None=None) -> Path:
    """Validate/select explicit runs, export finite summaries and standalone figures.

    Creates an exclusive timestamped output folder; failures leave status incomplete.
    All run/scientific/decoder/execution groups remain separate. Source runs are read
    only. No decoder execution or circuit sampling occurs. Bootstrap resamples saved pairs.
    """
    settings=settings or Analysis(); stamp=datetime.now(timezone.utc)
    output=Path(output_root).resolve()/(stamp.strftime('%Y%m%dT%H%M%S.%fZ')+'_'+uuid.uuid4().hex[:10])
    output.mkdir(parents=True,exist_ok=False)
    manifest={'schema_version':1,'status':'incomplete','created_utc':stamp.isoformat(),'settings':settings.model_dump(mode='json'),
        'purpose':'Descriptive software validation; smoke sample sizes do not establish decoder superiority',
        'pooling':'none across runs, scientific instances, sampling plans, decoder IDs or execution contexts',
        'sources':[],'files':{},'allow_incomplete':allow_incomplete,
        'selection':{'families':families,'distances':distances,'decoder_ids':decoder_ids,'timing_modes':timing_modes}}
    atomic_json(output/'manifest.json',manifest,exclusive=True)
    try:
        runs=[load_run(path,allow_incomplete=allow_incomplete) for path in run_paths]
        records=select_records(runs,families=families,distances=distances,decoder_ids=decoder_ids,timing_modes=timing_modes)
        if not records: raise ValueError('selection contains no committed decode rows')
        for run in runs:
            manifest['sources'].append({'path':str(run.path),'run_id':run.manifest['run_id'],'status':run.manifest['status'],
                                       'manifest_sha256':sha256(run.path/'manifest.json')})
        failures=aggregate_failures(records,confidence=settings.confidence)
        timings=aggregate_timings(records,quantiles=settings.quantiles,stratify=settings.stratify_timing,
                                 min_expected_tail_count=settings.min_expected_tail_count)
        atomic_json(output/'failures.json',{'schema_version':1,'groups':failures},exclusive=True)
        atomic_json(output/'timings.json',{'schema_version':1,'groups':timings},exclusive=True)
        atomic_json(output/'decoder_profiles.json',{d['id']:d for run in runs for d in run.manifest['decoders']},exclusive=True)
        rounds=[r for run in runs for r in run.hybrid_rounds.to_pylist()]
        stages=stage_statistics(records,rounds,confidence=settings.confidence)
        pairs=paired_statistics(records,settings=settings)
        atomic_json(output/'hybrid_stages.json',{'schema_version':1,'groups':stages},exclusive=True)
        atomic_json(output/'paired.json',{'schema_version':1,'groups':pairs},exclusive=True)
        physical={}
        for r in records: physical.setdefault((r['shot_id'],r['decoder_id']),set()).add(r['run_id'])
        manifest['physical_trial_policy']={'pooling':'none; separate intervals for each timing trial',
            'unique_shot_decoder_observations':len(physical),
            'repeated_trial_observations':sum(len(v)-1 for v in physical.values()),
            'warning':'Repeated replay intervals are dependent and must not be combined as independent LER evidence.'}
        figures=plot_hybrid(stages,pairs,timings,failures,output/'figures')
        for plot in settings.plots:
            if plot=='failure_rate': figures.extend(plot_failure_rates(failures,output/'figures'))
            else:
                field='cpu_ns' if plot.startswith('cpu_') else 'wall_ns'
                figures.extend(plot_timings(records,output/'figures',timer=field,survival=plot.endswith('survival'),
                    stratify=settings.stratify_timing,min_expected_tail_count=settings.min_expected_tail_count))
        for path in [output/'failures.json',output/'timings.json',output/'decoder_profiles.json',output/'hybrid_stages.json',output/'paired.json',*figures]:
            manifest['files'][str(path.relative_to(output))]=sha256(path)
        manifest.update(status='complete',decode_rows=len(records),failure_groups=len(failures),timing_groups=len(timings),
                        completed_utc=datetime.now(timezone.utc).isoformat())
        atomic_json(output/'manifest.json',manifest)
    except BaseException as error:
        manifest['error']={'type':type(error).__name__,'message':str(error)}
        atomic_json(output/'manifest.json',manifest)
        raise
    return output
