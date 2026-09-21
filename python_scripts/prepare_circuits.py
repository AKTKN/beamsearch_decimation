"""Prepare immutable physical circuit artifacts from a strict YAML configuration."""
import argparse
import json
from qec_bp_benchmark.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", help="Validated YAML path")
    args = parser.parse_args()
    config = load_config(args.config)
    # Numerical libraries are imported only after thread limits are configured.
    import os
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[key] = str(config.execution.native_threads if key == "OMP_NUM_THREADS" else config.execution.blas_threads)
    from qec_bp_benchmark.artifacts import prepare_instance
    from qec_bp_benchmark.identity import content_hash
    for code in config.experiment.codes:
        for distance in code.distances:
            for rate in config.noise.expanded_rates:
                print(prepare_instance(config, code.family, distance, rate, code.rounds), flush=True)
    resolved = config.resolved()
    path = config.circuit.cache / f"preparation_config_{content_hash(resolved)}.json"
    if not path.exists():
        with path.open("x") as file:
            json.dump(resolved, file, indent=2, allow_nan=False)
            file.write("\n")


if __name__ == "__main__":
    main()
