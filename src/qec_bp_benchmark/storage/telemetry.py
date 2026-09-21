"""Post-service truth labeling and strict hybrid event/accounting validation."""
from __future__ import annotations
from .schema import HYBRID_FIELDS,DURATION_FIELDS,EVENT_KEY


def attach_telemetry(record: dict, summary: dict | None, events: dict | None) -> tuple[list[dict],list[dict]]:
    """Mutate an owned v2 decode row and return owned labeled rounds/phases.

    Call outside the service timer, before the adapter decodes another shot.
    Signed residuals use zero tolerance: any negative residual flags an error.
    """
    if summary is None: return [],[]
    if events is None: raise ValueError('hybrid summary requires an owned event export')
    record.update(summary)
    measured=record['profiling']=='phases'
    if measured:
        for clock in ('cpu','wall'):
            record[f'service_other_{clock}_ns']=(record[f'{clock}_ns']-
                record[f'native_prefix_{clock}_ns']-record[f'osd_{clock}_ns'])
        record['timing_accounting_ok']=all(record[n]>=0 for n in DURATION_FIELDS)
    key={f.name:record[f.name] for f in EVENT_KEY}
    rounds=[]; phases=[]
    for table,destination in [('rounds',rounds),('phases',phases)]:
        for event in events[table]:
            valid=(event.get('candidate_syndrome_valid') is True if table=='phases'
                   else event['result'] in ('search_exit','bp_exit'))
            destination.append(dict(key,**event,candidate_prediction=record['prediction'] if valid else None,
                candidate_logical_mismatch=record['valid_logical_mismatch'] if valid else None))
    return rounds,phases


def validate_events(decodes: list[dict], rounds: list[dict], phases: list[dict], profiling: str) -> None:
    """Reject orphan/duplicate events, inconsistent counters, timing and candidate labels."""
    if profiling not in ('none','phases') or any(r['profiling']!=profiling for r in decodes): raise ValueError('inconsistent event profiling policy')
    by_key={(r['shot_id'],r['decoder_id']):r for r in decodes}
    grouped={name:{} for name in ('rounds','phases')}
    for name,rows,index in [('rounds',rounds,'cycle_index'),('phases',phases,'phase_index')]:
        seen=set()
        for row in rows:
            key=(row['shot_id'],row['decoder_id']); full=(*key,row[index])
            if key not in by_key or full in seen: raise ValueError('orphan or duplicate telemetry event')
            seen.add(full); parent=by_key[key]
            if any(row[f.name]!=parent[f.name] for f in EVENT_KEY): raise ValueError('event foreign key mismatch')
            if parent['algorithm_version'] is None: raise ValueError('hybrid event attached to unrelated decoder')
            valid=(row.get('candidate_syndrome_valid') is True if name=='phases' else row['result'] in ('search_exit','bp_exit'))
            for field,terminal in [('candidate_prediction','prediction'),('candidate_logical_mismatch','valid_logical_mismatch')]:
                if row[field]!=(parent[terminal] if valid else None): raise ValueError('invalid candidate label')
            grouped[name].setdefault(key,[]).append(row)
    for key,row in by_key.items():
        rs=sorted(grouped['rounds'].get(key,[]),key=lambda r:r['cycle_index'])
        ps=sorted(grouped['phases'].get(key,[]),key=lambda r:r['phase_index'])
        if row['algorithm_version'] is None:
            if any(row[f.name] is not None for f in HYBRID_FIELDS): raise ValueError('fabricated nonhybrid telemetry')
            continue
        if row['exit_stage'] not in ('search','guided_bp','osd','failed'): raise ValueError('unknown terminal stage')
        reasons={'search':('zero_syndrome','search_goal_generated'),
            'guided_bp':('bp_transition_valid','bp_iteration_valid'),'osd':('osd_valid',),
            'failed':('inconsistent_syndrome','osd_invalid','numerical_failure','resource_failure')}
        if row['algorithm_version']!='HSBP-ALG-1.0' or row['exit_reason'] not in reasons[row['exit_stage']]: raise ValueError('unknown algorithm/terminal reason')
        if row['osd_entered']:
            if row['fallback_reason'] not in ('cycle_budget','frontier_and_hints_exhausted','node_cap','prefix_cpu_cap') or row['osd_llr_source'] not in ('last_guided_bp','clipped_channel'): raise ValueError('invalid OSD provenance')
        elif row['osd_llr_source'] is not None: raise ValueError('unentered OSD has LLR source')
        if row['cycles_completed']>row['cycles_started'] or row['bp_warm_transitions']>max(0,row['bp_attempts']-1): raise ValueError('invalid completed/warm counters')
        hint_fields=('selected_hint_node_id','selected_hint_ones','selected_hint_zeros')
        if any((row[k] is not None)!=(row['bp_attempts']>0) for k in hint_fields): raise ValueError('selected hint nullability mismatch')
        if (row['hint_disagreements_final'] is not None)!=(row['bp_attempts']>0 and not row['decoding_failure']): raise ValueError('hint disagreement nullability mismatch')
        if row['exit_reason']=='zero_syndrome' and any(row[k] for k in ('input_syndrome_weight','cycles_started','search_generated_nodes','bp_attempts','osd_calls')): raise ValueError('zero-syndrome counter mismatch')
        if row['osd_calls']!=int(row['osd_entered']) or row['effective_osd_order']!=(0 if row['osd_entered'] else None): raise ValueError('OSD counter mismatch')
        if (row['fallback_reason'] is not None)!=row['osd_entered']: raise ValueError('OSD fallback reason mismatch')
        if (row['exit_stage']=='failed')!=row['decoding_failure']: raise ValueError('terminal validity mismatch')
        if row['exit_stage']!='failed' and row['osd_entered']!=(row['exit_stage']=='osd'): raise ValueError('terminal OSD reach mismatch')
        if profiling=='none':
            if rs or ps or any(row[n] is not None for n in DURATION_FIELDS+['timing_accounting_ok']): raise ValueError('unmeasured telemetry must be null')
            continue
        if len(rs)!=row['cycles_started'] or [r['cycle_index'] for r in rs]!=list(range(len(rs))): raise ValueError('cycle count/order mismatch')
        if [p['phase_index'] for p in ps]!=list(range(len(ps))): raise ValueError('phase order mismatch')
        for r in rs:
            if r['result'] not in ('continue','search_exit','bp_exit','fallback','failed'): raise ValueError('unknown cycle result')
            if r['expanded']>r['expansion_budget'] or r['iterations']>r['iteration_budget']: raise ValueError('cycle work exceeds budget')
            if r['warm'] and not r['bp_entered']: raise ValueError('warm cycle without BP')
            hint_fields=('hint_node_id','hint_ones','hint_zeros','hint_depth','hint_g','hint_h','hint_f','hint_residual_weight','hint_digest','residual_before')
            if any((r[k] is not None)!=r['bp_entered'] for k in hint_fields): raise ValueError('cycle hint nullability mismatch')
            if not r['bp_entered'] and r['residual_after'] is not None: raise ValueError('unentered BP residual')
            if r['bp_entered'] and r['result']!='failed' and r['residual_after'] is None: raise ValueError('missing completed BP residual')
            if r['bp_entered'] and (len(r['hint_digest'])!=16 or any(c not in '0123456789abcdef' for c in r['hint_digest'])): raise ValueError('invalid hint digest')
            for clock in ('cpu','wall'):
                if r[f'start_{clock}_ns']<0 or r[f'end_{clock}_ns']<r[f'start_{clock}_ns']: raise ValueError('invalid cycle duration')
        for event_field,summary_field in [('expanded','search_expanded_nodes'),('iterations','bp_iterations'),('bp_entered','bp_attempts'),('warm','bp_warm_transitions')]:
            if sum(r[event_field] for r in rs)!=row[summary_field]: raise ValueError('cycle summary counter mismatch')
        last=0
        for p in ps:
            if p['phase'] not in ('search','bp_transition','bp_iterations','osd'): raise ValueError('unknown phase')
            if p['result'] not in ('valid','slice_complete','nonconverged','prefix_cpu_cap','invalid','exception'): raise ValueError('unknown phase result')
            if p['phase']!='osd' and p['native_wall_end_ns']>row['native_prefix_wall_ns']: raise ValueError('phase extends beyond prefix')
            if p['phase']=='osd' and p['native_wall_start_ns']<row['native_prefix_wall_ns']: raise ValueError('OSD overlaps prefix')
            if p['cycle_index'] is None:
                if p['phase']!='osd': raise ValueError('missing cycle foreign key')
            elif p['cycle_index']>=len(rs) or p['phase']=='osd': raise ValueError('invalid cycle foreign key')
            if p['cpu_ns']<0 or p['wall_ns']<0 or p['native_wall_start_ns']<last or p['native_wall_end_ns']-p['native_wall_start_ns']!=p['wall_ns']: raise ValueError('phase interval mismatch')
            last=p['native_wall_end_ns']
        if not row['decoding_failure'] and row['exit_reason']!='zero_syndrome':
            valid=[p for p in ps if p['candidate_syndrome_valid'] is True]
            expected={'search_goal_generated':'search','bp_transition_valid':'bp_transition','bp_iteration_valid':'bp_iterations','osd_valid':'osd'}[row['exit_reason']]
            if len(valid)!=1 or valid[0] is not ps[-1] or valid[0]['phase']!=expected or valid[0]['result']!='valid': raise ValueError('invalid terminal valid phase')
        for phase,count in [('search','search_slices'),('bp_transition','bp_attempts'),('osd','osd_calls')]:
            if sum(p['phase']==phase for p in ps)!=row[count]: raise ValueError('phase call count mismatch')
        for phase,count in [('search','search_expanded_nodes'),('bp_iterations','bp_iterations')]:
            if sum(p['work'] for p in ps if p['phase']==phase)!=row[count]: raise ValueError('phase work mismatch')
        for clock in ('cpu','wall'):
            for phase in ('search','bp_transition','bp_iterations','osd'):
                if sum(p[f'{clock}_ns'] for p in ps if p['phase']==phase)!=row[f'{phase}_{clock}_ns']: raise ValueError('phase duration sum mismatch')
            prefix=row[f'native_prefix_{clock}_ns']
            if prefix-sum(row[f'{p}_{clock}_ns'] for p in ('search','bp_transition','bp_iterations'))!=row[f'prefix_other_{clock}_ns']: raise ValueError('prefix accounting mismatch')
            if row[f'{clock}_ns']-prefix-row[f'osd_{clock}_ns']!=row[f'service_other_{clock}_ns']: raise ValueError('service accounting mismatch')
        if row['timing_accounting_ok']!=all(row[n]>=0 for n in DURATION_FIELDS): raise ValueError('accounting flag mismatch')
