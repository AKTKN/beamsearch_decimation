"""Decode committed saved physical samples with the YAML decoder configuration."""
import argparse
from qec_bp_benchmark.runner.pipeline import run_benchmark


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_run',help='Complete or incomplete run with committed batches')
    parser.add_argument('config',help='Decoder/execution/output YAML; source physical dataset is authoritative')
    parser.add_argument('-v','--verbose',action='store_true',help='Print preparation and committed-batch progress to stderr')
    args=parser.parse_args()
    print(run_benchmark(args.config,replay_source=args.source_run,verbose=args.verbose),flush=True)


if __name__=='__main__': main()
