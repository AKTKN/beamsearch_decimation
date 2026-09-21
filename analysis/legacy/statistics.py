"""Count-based block uncertainty and per-shot timing; never treat BB bits as trials."""
from __future__ import annotations
from collections import defaultdict
import math
from statistics import NormalDist
from typing import Iterable,Sequence
import numpy as np

# Runs, sampling plans and execution modes never pool implicitly. instance_id also
# protects exact circuit/DEM/noise/round conventions and the observable mapping.
GROUP_KEYS=('run_id','instance_id','sampling_id','decoder_id','family','distance','n','k_Z','rounds',
            'physical_p','noise_id','model_hash','timing_mode','workers','native_threads','blas_threads',
            'concurrent_load','oversubscribed','profiling','execution_id','comparison_id','run_status')
DEFAULT_QUANTILES=(.5,.9,.95,.99,.999)
MIN_EXPECTED_TAIL_COUNT=10


def wilson_interval(failures: int, shots: int, confidence: float=.95) -> tuple[float | None,float | None]:
    """Two-sided Wilson score interval for one Bernoulli block per physical shot.

    Return null endpoints for a zero conditional denominator. Invalid counts or
    confidence raise ValueError. No continuity correction or pseudo-count rate.
    """
    if type(failures) is not int or type(shots) is not int or not 0<=failures<=shots:
        raise ValueError('counts must be integers with 0 <= failures <= shots')
    if not math.isfinite(confidence) or not 0<confidence<1: raise ValueError('confidence must be in (0,1)')
    if shots==0: return None,None
    z=NormalDist().inv_cdf((1+confidence)/2); p=failures/shots
    denominator=1+z*z/shots
    center=(p+z*z/(2*shots))/denominator
    half=z*math.sqrt(p*(1-p)/shots+z*z/(4*shots*shots))/denominator
    return (0.0 if failures==0 else max(0.0,center-half),
            1.0 if failures==shots else min(1.0,center+half))


def _group_key(row: dict) -> tuple:
    try: return tuple(row[key] for key in GROUP_KEYS)
    except KeyError as error: raise ValueError(f'missing protected grouping field: {error}') from error


def _checked_groups(records: Iterable[dict]) -> list[list[dict]]:
    groups=defaultdict(list); seen=set()
    for row in records:
        key=(row['run_id'],row['shot_id'],row['decoder_id'])
        if key in seen: raise ValueError('duplicate shot/decoder; replay cannot increase sample size')
        seen.add(key); groups[_group_key(row)].append(row)
    return [rows for _,rows in sorted(groups.items(),key=lambda item:repr(item[0]))]


def _metric(count: int, denominator: int, confidence: float) -> dict:
    low,high=wilson_interval(count,denominator,confidence)
    return {'count':count,'denominator':denominator,'rate':count/denominator if denominator else None,
            'low':low,'high':high,'confidence':confidence,'interval':'two-sided Wilson',
            'zero_observed':count==0 and denominator>0}


def summarize_failure_group(records: Sequence[dict], *, confidence: float=.95) -> dict:
    """Summarize one compatible run/instance/decoder group by summing shot counts.

    Reject mixed scientific/execution identities or duplicate shots. Components
    use all shots; conditional logical mismatch uses valid outputs. Per-observable
    counts are retained but never averaged into independent block trials.
    """
    groups=_checked_groups(records)
    if len(groups)!=1: raise ValueError('expected one nonempty compatible scientific/execution group')
    rows=groups[0]; first=rows[0]; k=first['k_Z']
    if type(k) is not int or k<1: raise ValueError('invalid observable count')
    failures=mismatches=blocks=0; observable=[0]*k; total_observable=[0]*k
    for row in rows:
        failed=bool(row['decoding_failure']); mismatch=bool(row['valid_logical_mismatch'])
        if failed and mismatch: raise ValueError('valid-output mismatch cannot be true on failure')
        if row['block_failure']!=(failed or mismatch): raise ValueError('inconsistent block failure')
        bits=row['observable_mismatch']; totals=row['observable_total_failure']
        if len(totals)!=k: raise ValueError('observable dimension mismatch')
        if failed:
            if bits is not None or row['prediction'] is not None or not all(totals): raise ValueError('failed decode must have null mismatch/prediction')
        else:
            if bits is None or len(bits)!=k or any(bits)!=mismatch or list(bits)!=list(totals): raise ValueError('invalid per-observable mismatch')
            observable=[a+int(b) for a,b in zip(observable,bits)]
        total_observable=[a+int(b) for a,b in zip(total_observable,totals)]
        failures+=failed; mismatches+=mismatch; blocks+=row['block_failure']
    n=len(rows); valid=n-failures
    result={key:first[key] for key in GROUP_KEYS}
    result.update(decoder_name=first['decoder_name'],decoder_profile=first['decoder_profile'],
        decoder_parameters=first.get('decoder_parameters',{}),shots=n,valid_outputs=valid,
        block_failure=_metric(int(blocks),n,confidence),decoding_failure=_metric(int(failures),n,confidence),
        valid_mismatch_contribution=_metric(int(mismatches),n,confidence),
        conditional_valid_mismatch=_metric(int(mismatches),valid,confidence),
        observable_mismatch_counts=observable,observable_total_failure_counts=total_observable,
        observable_valid_denominator=valid,observable_total_denominator=n)
    return result


def aggregate_failures(records: Iterable[dict], *, confidence: float=.95) -> list[dict]:
    """Separate incompatible keys and sum counts within batches of each safe group."""
    wilson_interval(0,0,confidence)
    return [summarize_failure_group(rows,confidence=confidence) for rows in _checked_groups(records)]


def timing_path(row: dict) -> str:
    """Classify only available diagnostics; missing upstream counters stay unknown."""
    if row.get('exit_stage') is not None:
        return 'zero_syndrome' if row['exit_reason']=='zero_syndrome' else row['exit_stage']
    if row['decoding_failure']: return 'failure'
    if row.get('initial_success') is True or row.get('native_status') in ('INITIAL_CONVERGED','BP_CONVERGED'):
        return 'initial_bp_success'
    if row.get('initial_success') is False or row.get('native_status') in ('POST_CONVERGED','OSD_AFTER_BP_NONCONVERGENCE'):
        return 'postprocessing'
    return 'valid_output_unclassified'


def _durations(values: Iterable[int]) -> np.ndarray:
    values=list(values)
    if any(type(v) is not int or v<0 or v>2**63-1 for v in values): raise ValueError('durations must be nonnegative int64 nanoseconds')
    return np.asarray(values,dtype=np.int64)


def timing_statistics(values: Iterable[int], *, quantiles: Sequence[float]=DEFAULT_QUANTILES,
                      min_expected_tail_count: int=MIN_EXPECTED_TAIL_COUNT) -> dict:
    """Descriptive statistics of individual decode durations in ns, failures included.

    Linear interpolation is NumPy's explicit method='linear'. Standard quantiles
    are always reported, plus requested values. Tail support uses N*(1-q); at least
    ten by default is only a screening threshold, never a precision guarantee.
    """
    data=_durations(values)
    if type(min_expected_tail_count) is not int or min_expected_tail_count<1: raise ValueError('tail threshold must be positive')
    qs=sorted(set(DEFAULT_QUANTILES)|set(quantiles))
    if any(not math.isfinite(q) or not 0<=q<=1 for q in qs): raise ValueError('quantiles must be in [0,1]')
    n=len(data); estimates=np.quantile(data,qs,method='linear').tolist() if n else [None]*len(qs)
    stats=[{'q':q,'value_ns':None if q>=.999 and n*(1-q)<min_expected_tail_count else value,'expected_tail_count':n*(1-q),
        'insufficient_for_performance_claim':n*(1-q)<min_expected_tail_count} for q,value in zip(qs,estimates)]
    by_q={item['q']:item['value_ns'] for item in stats}
    return {'samples':n,'units':'ns','quantile_method':'linear','mean_ns':float(np.mean(data)) if n else None,
        'median_ns':by_q[.5],'p90_ns':by_q[.9],'p95_ns':by_q[.95],'p99_ns':by_q[.99],'p99_9_ns':by_q[.999],
        'max_ns':int(np.max(data)) if n else None,'min_ns':int(np.min(data)) if n else None,
        'quantiles':stats,'min_expected_tail_count':min_expected_tail_count,
        'tail_caution':'Tail-count threshold is necessary screening only; smoke estimates establish no performance advantage.'}


def aggregate_timings(records: Iterable[dict], *, quantiles: Sequence[float]=DEFAULT_QUANTILES,
                      stratify: bool=False, min_expected_tail_count: int=MIN_EXPECTED_TAIL_COUNT) -> list[dict]:
    """CPU/wall summaries by protected identity and optionally observed decode path."""
    summaries=[]
    for rows in _checked_groups(records):
        subsets={'all':rows}
        if stratify:
            for row in rows: subsets.setdefault(timing_path(row),[]).append(row)
        for stratum,group in subsets.items():
            for field in ('cpu_ns','wall_ns'):
                summaries.append({**{key:group[0][key] for key in GROUP_KEYS},'stratum':stratum,'timer':field,
                    'decoder_name':group[0]['decoder_name'],'decoder_profile':group[0]['decoder_profile'],
                    **timing_statistics([r[field] for r in group],quantiles=quantiles,min_expected_tail_count=min_expected_tail_count)})
    return summaries


def empirical_distribution(values: Iterable[int], *, survival: bool=False) -> tuple[np.ndarray,np.ndarray]:
    """Right-continuous empirical F(t)=P(T<=t), or strict survival P(T>t).

    Duplicate observations contribute their multiplicity; no positive epsilon is
    substituted for zero survival. Empty input returns two empty owned arrays.
    """
    data=_durations(values)
    x,counts=np.unique(data,return_counts=True)
    y=np.cumsum(counts,dtype=np.float64)/len(data) if len(data) else np.array([],dtype=float)
    return x,1-y if survival else y
