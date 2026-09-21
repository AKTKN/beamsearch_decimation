"""Validate saved run integrity and optionally compare non-timing paired outputs."""
import argparse,json


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run')
    parser.add_argument('--compare')
    parser.add_argument('--allow-additional-decoders',action='store_true')
    parser.add_argument('--allow-incomplete',action='store_true')
    args=parser.parse_args()
    from analysis.io import load_run
    from analysis.validation import compare_runs
    left=load_run(args.run,allow_incomplete=args.allow_incomplete)
    result={'run_id':left.manifest['run_id'],'status':left.manifest['status'],
            'samples':left.samples.num_rows,'decodes':left.decodes.num_rows}
    if args.compare:
        result['comparison']=compare_runs(left,load_run(args.compare,allow_incomplete=args.allow_incomplete),
                                         allow_additional_decoders=args.allow_additional_decoders)
    print(json.dumps(result,indent=2,allow_nan=False))


if __name__=='__main__':main()
