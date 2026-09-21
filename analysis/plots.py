"""Standalone Matplotlib figures, with explicit zero-failure and small-tail labels."""
from __future__ import annotations
from collections import defaultdict
from pathlib import Path
from typing import Iterable,Sequence
import numpy as np
from qec_bp_benchmark.identity import content_hash
from .statistics import empirical_distribution,timing_statistics,timing_path


def decoder_label(row: dict) -> str:
    """Describe kernel/profile and active budgets; never label all methods simply BP."""
    d=row.get('decoder_parameters',{}); profile=row['decoder_profile']
    if profile=='screened_reference':
        params=', '.join(f'{k}={d.get(k,"?")}' for k in ('T0','Tpost','history_window','M','q','K','Lmax'))
        text='screened sum-product; '+params
    elif profile=='bposd_ms30_cs10': text=f'min-sum BP({d.get("max_iter","?")}) + OSD_CS({d.get("osd_order","?")}), scale=1'
    else: text='beam min-sum; '+', '.join(f'{k}={d.get(k,"?")}' for k in ('beam_width','max_rounds','initial_iters','iters_per_round','num_results'))
    return f'{row["decoder_name"]} [{row["decoder_id"][:8]}]\n{text}'


def _save(figure, output: Path, stem: str) -> list[Path]:
    output.mkdir(parents=True,exist_ok=True)
    paths=[]
    for suffix in ('png','pdf'):
        path=output/f'{stem}.{suffix}'
        if path.exists(): raise FileExistsError(path)
        figure.savefig(path,dpi=150,bbox_inches='tight')
        paths.append(path)
    return paths


def plot_failure_rates(summaries: Sequence[dict], output: str | Path) -> list[Path]:
    """Plot all block/component rates against p, separating code/noise/run/execution.

    A zero estimate stays zero in tables; on log plots only its labeled two-sided
    Wilson upper endpoint appears, with a downward triangle. No artificial rate.
    """
    import matplotlib.pyplot as plt
    groups=defaultdict(list)
    for row in summaries:
        key=(row['run_id'],row['comparison_id'],row['execution_id'],row['timing_mode'],row['workers'],row['profiling'])
        groups[key].append(row)
    paths=[]
    panels=[('block_failure','Z-memory block failure / all shots'),('decoding_failure','Decoding failure / all shots'),
            ('valid_mismatch_contribution','Valid logical mismatch / all shots'),
            ('conditional_valid_mismatch','Logical mismatch / valid outputs')]
    for key,rows in sorted(groups.items()):
        fig,axes=plt.subplots(2,2,figsize=(13,8),layout='constrained')
        by_decoder=defaultdict(list)
        for row in rows: by_decoder[row['decoder_id']].append(row)
        for ax,(metric,title) in zip(axes.flat,panels):
            for index,(_,points) in enumerate(sorted(by_decoder.items())):
                points=sorted(points,key=lambda r:r['physical_p']); color=f'C{index%10}'
                positive=[r for r in points if r[metric]['rate'] is not None and r[metric]['count']>0]
                zeros=[r for r in points if r[metric]['zero_observed']]
                label=decoder_label(points[0])
                if positive:
                    p=[r['physical_p'] for r in positive]; rates=[r[metric]['rate'] for r in positive]
                    errors=np.array([[r[metric]['rate']-r[metric]['low'] for r in positive],
                                     [r[metric]['high']-r[metric]['rate'] for r in positive]])
                    ax.errorbar(p,rates,yerr=errors,fmt='o',color=color,capsize=3,label=label)
                for index_zero,row in enumerate(zeros):
                    value=row[metric]
                    ax.plot(row['physical_p'],value['high'],'v',mfc='none',color=color,
                            label=label if not positive and index_zero==0 else None)
                    ax.annotate(f'0/{value["denominator"]} upper', (row['physical_p'],value['high']),
                                xytext=(3,5+10*index),textcoords='offset points',fontsize=7,color=color)
                if not positive and not zeros:
                    ax.plot([],[],color=color,label=label+'; no valid outputs')
                    ax.text(.02,.04+.06*index,f'{points[0]["decoder_name"]}: no valid outputs',
                            transform=ax.transAxes,color=color,fontsize=8)
            if all(r['physical_p']>0 for r in rows): ax.set_xscale('log')
            ax.set_yscale('log'); ax.set_ylim(top=1.1)
            ax.set_title(title); ax.set_xlabel('Physical error probability p'); ax.set_ylabel('Probability per block')
            ax.grid(True,which='both',alpha=.2)
        first=rows[0]; confidence=rows[0]['block_failure']['confidence']
        fig.suptitle(f'{first["family"]} d={first["distance"]}, R={first["rounds"]}, k_Z={first["k_Z"]}; '
                     f'{first["timing_mode"]}, workers={first["workers"]}, {first["run_status"]}\n'
                     f'{confidence:.0%} two-sided Wilson intervals; triangles show zero-event upper endpoints. Software smoke is not a performance result.')
        handles,labels=axes[0,0].get_legend_handles_labels()
        fig.legend(handles,labels,loc='outside lower center',fontsize=7,ncols=1)
        paths.extend(_save(fig,Path(output),'failure_'+content_hash(key)[:16])); plt.close(fig)
    return paths


def plot_timings(records: Sequence[dict], output: str | Path, *, timer: str='cpu_ns', survival: bool=False,
                 stratify: bool=False, min_expected_tail_count: int=10) -> list[Path]:
    """Plot individual-shot CPU or wall distributions in ms, never time divided by R.

    Each figure has one run/scientific instance/execution mode. Every plotted curve
    reports N and p99/p99.9 expected tail counts; short tails are explicitly marked.
    """
    if timer not in ('cpu_ns','wall_ns'): raise ValueError('unknown timer')
    import matplotlib.pyplot as plt
    groups=defaultdict(list)
    for row in records:
        key=(row['run_id'],row['instance_id'],row['sampling_id'],row['execution_id'],row['timing_mode'],row['workers'],row['profiling'])
        groups[key].append(row)
    paths=[]
    for key,rows in sorted(groups.items()):
        curves=defaultdict(list)
        for row in rows:
            curves[(row['decoder_id'],'all')].append(row)
            if stratify: curves[(row['decoder_id'],timing_path(row))].append(row)
        fig,ax=plt.subplots(figsize=(12,6+.4*len(curves)),layout='constrained')
        for curve_key,curve in sorted(curves.items()):
            values=[row[timer] for row in curve]; x,y=empirical_distribution(values,survival=survival)
            stats=timing_statistics(values,min_expected_tail_count=min_expected_tail_count)
            n=stats['samples']; tails=[v for v in stats['quantiles'] if v['q'] in (.99,.999)]
            warning='INSUFFICIENT TAIL DATA' if any(v['insufficient_for_performance_claim'] for v in tails) else 'tail precision not guaranteed'
            stratum=curve_key[1]
            label=f'{decoder_label(curve[0])}; {stratum}; N={n}, E99={n*.01:.3g}, E99.9={n*.001:.3g}; {warning}'
            # Include the empirical left limit. A zero-time jump is represented at x=0.
            xx=np.concatenate(([0],x/1e6)); yy=np.concatenate(([1. if survival else 0.],y))
            ax.step(xx,yy,where='post',label=label)
        first=rows[0]
        ax.set_title(f'{first["family"]} d={first["distance"]}, R={first["rounds"]}, p={first["physical_p"]:g}; '
            f'{first["timing_mode"]}, workers={first["workers"]}, profiling={first["profiling"]}\n'
            f'Individual complete-block {"process CPU" if timer=="cpu_ns" else "wall"} time; {first["run_status"]}; failures included; '
            f'{"concurrent load" if first["concurrent_load"] else "one worker"}\n'
            'Descriptive smoke distribution; no performance or online round-latency claim.')
        ax.set_xlabel('Decode time per block (ms)'); ax.set_ylabel('P(T > t)' if survival else 'P(T ≤ t)')
        ax.set_ylim(-.02,1.02); ax.grid(alpha=.2)
        fig.legend(*ax.get_legend_handles_labels(),loc='outside lower center',fontsize=7)
        stem=f'{timer}_{"survival" if survival else "ecdf"}_{content_hash(key)[:16]}'
        paths.extend(_save(fig,Path(output),stem)); plt.close(fig)
    return paths
