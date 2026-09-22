"""Saved-data hybrid stage accounting and paired hypothesis estimates.

All durations are nanoseconds. Groups retain run, sampling, model, execution and
instrumentation identities. Replays remain separate timing trials: no pooled LER
interval treats repeated physical shot IDs as new independent observations.
"""
from __future__ import annotations
from collections import defaultdict
from itertools import combinations
from typing import Callable,Iterable,Sequence
import numpy as np
from .config import Analysis
from .statistics import GROUP_KEYS,_checked_groups,_metric
from .bootstrap import PairedBootstrap, STAGES

PAIR_KEYS=tuple(k for k in GROUP_KEYS if k!='decoder_id')


def terminal(row: dict) -> str:
    """Return mutually exclusive exit stratum, separating empty syndromes."""
    return 'zero_syndrome' if row['exit_reason']=='zero_syndrome' else row['exit_stage']


def stage_statistics(records: Iterable[dict], rounds: Iterable[dict]=(), *, confidence: float=.95) -> list[dict]:
    """Summarize exit/reach, valid-only accuracy, disjoint costs and cycle rescue.

    Each rate includes its numerator, denominator and Wilson interval. Cycle rates
    condition on entering that cycle; failure contributions always use all shots.
    """
    event_groups=defaultdict(list); seen=set()
    for event in rounds:
        key=(event['run_id'],event['shot_id'],event['decoder_id'],event['cycle_index'])
        if key in seen: raise ValueError('duplicate cycle observation')
        seen.add(key); event_groups[(event['run_id'],event['shot_id'],event['decoder_id'])].append(event)
    output=[]
    for rows in _checked_groups(records):
        if rows[0].get('algorithm_version') is None: continue
        n=len(rows); first=rows[0]
        stages={}
        for stage in STAGES:
            selected=[r for r in rows if terminal(r)==stage]
            valid=[r for r in selected if not r['decoding_failure']]
            stages[stage]={'exit':_metric(len(selected),n,confidence),
                'conditional_valid_mismatch':_metric(sum(bool(r['valid_logical_mismatch']) for r in valid),len(valid),confidence),
                'failure_contribution':_metric(sum(r['block_failure'] for r in selected),n,confidence)}
        bp=[r for r in rows if r['bp_attempts']>0]; osd=[r for r in rows if r['osd_entered']]
        cycles=defaultdict(list)
        for row in rows:
            for event in event_groups[(row['run_id'],row['shot_id'],row['decoder_id'])]: cycles[event['cycle_index']].append(event)
        cycle_output=[]
        for index,events in sorted(cycles.items()):
            attempts=sum(e['bp_entered'] for e in events)
            cycle_output.append({'cycle_index':index,'entered':len(events),'all_shots':n,
                'search_rescue':_metric(sum(e['result']=='search_exit' for e in events),len(events),confidence),
                'bp_rescue':_metric(sum(e['result']=='bp_exit' for e in events),attempts,confidence),
                'expansions':sum(e['expanded'] for e in events),'generated':sum(e['generated'] for e in events),
                'bp_iterations':sum(e['iterations'] for e in events),'bp_attempts':attempts,
                'hint_ones':sum(e['hint_ones'] or 0 for e in events),'hint_zeros':sum(e['hint_zeros'] or 0 for e in events),
                'node_cap':_metric(sum(e['node_cap_hit'] for e in events),len(events),confidence),
                'prefix_cap':_metric(sum(e['prefix_cap_hit'] for e in events),len(events),confidence)})
        costs={}
        for clock in ('cpu','wall'):
            costs[clock]={}
            for phase in ('search','bp_transition','bp_iterations','prefix_other','osd','service_other'):
                values=[r[f'{phase}_{clock}_ns'] for r in rows]
                costs[clock][phase]=None if any(v is None for v in values) else sum(values)/n
        output.append({**{k:first[k] for k in GROUP_KEYS},'decoder_profile':first['decoder_profile'],
            'decoder_name':first['decoder_name'],'shots':n,'stages':stages,
            'bp_reach':_metric(len(bp),n,confidence),'osd_reach':_metric(len(osd),n,confidence),
            'bp_rescue':_metric(sum(r['exit_stage']=='guided_bp' for r in bp),len(bp),confidence),
            'osd_success':_metric(sum(r['exit_stage']=='osd' for r in osd),len(osd),confidence),
            'disjoint_mean_cost_ns':costs,'cycles':cycle_output,
            'cycle_data_available':first['profiling']=='phases'})
    return output


def paired_rows(records: Iterable[dict], hybrid_id: str, baseline_id: str) -> list[tuple[dict,dict]]:
    """Join exactly one compatible run/context by shot, rejecting missing pairs.

    This low-level API rejects mixed contexts rather than silently pooling them.
    Use paired_statistics to split multiple saved runs/instances safely.
    """
    if hybrid_id==baseline_id: raise ValueError('pair requires distinct decoder identities')
    rows=[r for r in records if r['decoder_id'] in (hybrid_id,baseline_id)]
    groups=_checked_groups(rows)
    if not groups: return []
    if len({tuple(r[k] for k in PAIR_KEYS) for r in rows})!=1: raise ValueError('incompatible paired scientific/execution contexts')
    sides={d:{r['shot_id']:r for r in rows if r['decoder_id']==d} for d in (hybrid_id,baseline_id)}
    if sides[hybrid_id].keys()!=sides[baseline_id].keys(): raise ValueError('missing paired shot')
    return [(sides[hybrid_id][s],sides[baseline_id][s]) for s in sorted(sides[hybrid_id])]


def summarize_pair(pairs: Sequence[tuple[dict,dict]], *, settings: Analysis | None=None,
                   progress: Callable[[str], None] | None=None) -> dict:
    """Exact integer accounting plus paired percentile bootstrap of mean statistics.

    Resamples entire paired shots or whole physical batches with replacement. The
    accuracy criterion is the upper one-sided bootstrap confidence bound strictly
    below the predeclared absolute margin. No margin means no equivalence claim.
    Empty inputs have null estimates and zero denominators.
    """
    settings=settings or Analysis()
    metadata={'seed':settings.bootstrap_seed,'count':settings.bootstrap_count,'unit':settings.bootstrap_unit,
        'confidence':settings.confidence,'method':'paired percentile bootstrap',
        'ler_trials':'unique physical shots within this run only; replay trials never pooled'}
    if not pairs: return {'shots':0,'estimates':{},'intervals':{},'bootstrap':metadata,'noninferiority':None}
    # Validate identity before floating-point aggregation or any resampling.
    joined=paired_rows([r for pair in pairs for r in pair],pairs[0][0]['decoder_id'],pairs[0][1]['decoder_id'])
    for h,b in joined:
        if h.get('algorithm_version') is None: raise ValueError('first decoder is not an instrumented hybrid')
        for clock in ('cpu','wall'):
            p=h[f'native_prefix_{clock}_ns']
            if p is None: continue
            if not h['timing_accounting_ok']: raise ValueError('flagged timing accounting error')
            th=h[f'{clock}_ns']; tb=b[f'{clock}_ns']; f=int(h['osd_entered']); a=1-f
            o=h[f'osd_{clock}_ns']; v=h[f'service_other_{clock}_ns']
            if th-tb!=p+v-a*tb+f*(o-tb) or (not f and o!=0): raise ValueError('paired cost identity mismatch')
    integer_totals={}
    for clock in ('cpu','wall'):
        if all(h[f'native_prefix_{clock}_ns'] is not None for h,b in joined):
            difference=sum(h[f'{clock}_ns']-b[f'{clock}_ns'] for h,b in joined)
            terms=sum(h[f'native_prefix_{clock}_ns']+h[f'service_other_{clock}_ns']-
                (not h['osd_entered'])*b[f'{clock}_ns']+
                h['osd_entered']*(h[f'osd_{clock}_ns']-b[f'{clock}_ns']) for h,b in joined)
            if difference!=terms: raise ValueError('aggregate paired cost identity mismatch')
            integer_totals[clock]={'difference_ns':difference,'four_term_sum_ns':terms,'shots':len(joined)}
    total=sum(int(h['block_failure'])-int(b['block_failure']) for h,b in joined)
    components=sum((not h['osd_entered'])*(int(h['block_failure'])-int(b['block_failure']))+
        h['osd_entered']*(int(h['block_failure'])-int(b['block_failure'])) for h,b in joined)
    if total!=components: raise ValueError('paired error identity mismatch')
    pairs=joined
    bootstrap=PairedBootstrap(pairs, settings.bootstrap_unit)
    estimates=bootstrap.estimates()
    distributions=bootstrap.distributions(seed=settings.bootstrap_seed, count=settings.bootstrap_count, progress=progress)
    alpha=(1-settings.confidence)/2
    intervals={k:{'low':float(np.quantile(v,alpha)),'high':float(np.quantile(v,1-alpha)),
        'valid_resamples':len(v)} if v else {'low':None,'high':None,'valid_resamples':0} for k,v in distributions.items()}
    discordance={f'h{h}_b{b}':sum(int(x['block_failure'])==h and int(y['block_failure'])==b for x,y in pairs)
                 for h in (0,1) for b in (0,1)}
    margin=settings.accuracy_margin_absolute
    upper=float(np.quantile(distributions['failure_difference'],settings.confidence))
    n=len(pairs); first,base=pairs[0]
    accuracy={}
    for side,index in [('hybrid',0),('baseline',1)]:
        rows=[p[index] for p in pairs]; valid=[r for r in rows if not r['decoding_failure']]
        accuracy[side]={'block_failure':_metric(sum(r['block_failure'] for r in rows),n,settings.confidence),
            'conditional_valid_mismatch':_metric(sum(bool(r['valid_logical_mismatch']) for r in valid),len(valid),settings.confidence)}
    return {**{k:first[k] for k in PAIR_KEYS},'hybrid_id':first['decoder_id'],'baseline_id':base['decoder_id'],
        'hybrid_profile':first['decoder_profile'],'baseline_profile':base['decoder_profile'],
        'shots':n,'independent_physical_shots':len({h['shot_id'] for h,b in pairs}),
        'estimates':estimates,'intervals':intervals,'discordance':discordance,'accuracy':accuracy,
        'bootstrap':dict(metadata,units=bootstrap.units),
        'pre_osd_failures':sum(not h['osd_entered'] and h['decoding_failure'] for h,b in pairs),
        'osd_reach':_metric(sum(h['osd_entered'] for h,b in pairs),n,settings.confidence),
        'accounting':'integer identity checked per shot and in totals; displayed means use binary64',
        'integer_totals':integer_totals,
        'noninferiority':None if margin is None else {'margin_absolute':margin,'confidence':settings.confidence,
            'one_sided_upper':upper,'criterion':'upper < predeclared margin','criterion_met':upper<margin,
            'caution':'Bootstrap resolution and sample size limit evidence; smoke is not a scientific conclusion.'}}


def paired_statistics(records: Iterable[dict], *, settings: Analysis | None=None,
                      progress: Callable[[str], None] | None=None) -> list[dict]:
    """Return separate hybrid/baseline and warm/cold/no-BP paired comparisons."""
    records=list(records); _checked_groups(records)
    contexts=defaultdict(list)
    for row in records: contexts[tuple(row[k] for k in PAIR_KEYS)].append(row)
    output=[]
    for _,rows in sorted(contexts.items(),key=lambda item:repr(item[0])):
        profiles={r['decoder_id']:r for r in rows}
        for left,right in combinations(sorted(profiles),2):
            if profiles[left].get('algorithm_version') is None:
                left,right=right,left
            if profiles[left].get('algorithm_version') is None: continue
            if progress is not None:
                progress(f"Paired comparison: {profiles[left]['decoder_name']} / {profiles[right]['decoder_name']}")
            output.append(summarize_pair(paired_rows(rows,left,right),settings=settings,progress=progress))
    return output
