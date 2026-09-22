"""Validate and print a fully resolved benchmark configuration without running it."""
from __future__ import annotations

import argparse
import json

from qec_bp_benchmark.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", help="strict benchmark YAML to validate")
    args = parser.parse_args()
    config = load_config(args.config)
    print(json.dumps(config.model_dump(mode="json"), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
