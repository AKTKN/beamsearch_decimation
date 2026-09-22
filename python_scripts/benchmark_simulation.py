"""Measure simulation-pipeline time with decoder calls kept opaque."""
import argparse
import json

from qec_bp_benchmark.benchmarking.simulation import (
    benchmark_simulation,
    format_report,
    write_report,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("config")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--shots", type=int)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--output", help="optional JSON report path")
    parser.add_argument("--json", action="store_true", help="print JSON instead of text")
    args = parser.parse_args()
    report = benchmark_simulation(
        args.config, repeats=args.repeats, shots=args.shots, batch_size=args.batch_size
    )
    if args.output:
        write_report(report, args.output)
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else format_report(report))


if __name__ == "__main__":
    main()
