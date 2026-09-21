"""Analyze explicit saved runs; never sample or decode from this entry point."""
import argparse
from qec_bp_benchmark.config import load_config
from qec_bp_benchmark.runner import configure_execution


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config',help='YAML analysis settings and default input/output paths')
    parser.add_argument('--run',action='append',help='Explicit run path, repeatable; otherwise discover analysis.input')
    parser.add_argument('--allow-incomplete',action='store_true',help='Opt in to committed subsets, labeled incomplete')
    parser.add_argument('--family',action='append',choices=['surface','bb72'])
    parser.add_argument('--distance',type=int,action='append')
    parser.add_argument('--decoder-id',action='append')
    parser.add_argument('--timing-mode',action='append',choices=['throughput','isolated_latency'])
    args=parser.parse_args(); config=load_config(args.config); configure_execution(config)
    import matplotlib
    matplotlib.use('Agg')
    from analysis import create_report,discover_runs
    paths=args.run or discover_runs(config.analysis.input,include_incomplete=args.allow_incomplete)
    print(create_report(paths,config.analysis.output,settings=config.analysis,allow_incomplete=args.allow_incomplete,
        families=args.family,distances=args.distance,decoder_ids=args.decoder_id,timing_modes=args.timing_mode),flush=True)


if __name__=='__main__': main()
