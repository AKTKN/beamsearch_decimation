"""Execute a simulation and write the minimal named-Parquet result layout."""
import argparse
from qec_bp_benchmark.runner.pipeline import run_benchmark


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config',help='YAML configuration path')
    parser.add_argument('-v','--verbose',action='store_true',help='Print preparation and saved-batch progress to stderr')
    args=parser.parse_args()
    print(run_benchmark(args.config,verbose=args.verbose),flush=True)


if __name__=='__main__': main()
