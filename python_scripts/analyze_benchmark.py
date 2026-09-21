"""Analyze explicit saved runs; never sample or decode from this entry point."""
import argparse
from pathlib import Path
import sys


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config',nargs='?',default=str(Path(__file__).resolve().parents[1]/'config/analysis.yaml.example'),
                        help='Analysis-only YAML (existing benchmark YAML also supported)')
    parser.add_argument('--run',action='append',help='Explicit run path, repeatable; otherwise discover analysis.input')
    parser.add_argument('--allow-incomplete',action='store_true',help='Opt in to committed subsets, labeled incomplete')
    parser.add_argument('--family',action='append',choices=['surface','bb72'])
    parser.add_argument('--distance',type=int,action='append')
    parser.add_argument('--decoder-id',action='append')
    parser.add_argument('--timing-mode',action='append',choices=['throughput','isolated_latency'])
    parser.add_argument('-v','--verbose',action='store_true',help='Analysis progress on stderr')
    args=parser.parse_args()
    import matplotlib
    matplotlib.use('Agg')
    from analysis import create_report,discover_runs,load_analysis_config
    config=load_analysis_config(args.config)
    paths=args.run or discover_runs(config.analysis.input,include_incomplete=args.allow_incomplete)
    print(create_report(paths,config.analysis.output,settings=config.analysis,allow_incomplete=args.allow_incomplete,
        families=args.family,distances=args.distance,decoder_ids=args.decoder_id,timing_modes=args.timing_mode,
        progress=(lambda message: print(message,file=sys.stderr,flush=True)) if args.verbose else None),flush=True)


if __name__=='__main__': main()
