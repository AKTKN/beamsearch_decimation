"""Run bounded four-decoder serial/spawn and BB144 acceptance smoke checks."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pyarrow.parquet as pq
import yaml

from qec_bp_benchmark.runner.pipeline import run_benchmark
from qec_bp_benchmark.storage.minimal import SCHEMA

ROOT = Path(__file__).resolve().parents[1]


def rows(run: Path) -> list[dict]:
    paths = list((run / "data").glob("*_results.parquet"))
    if len(paths) != 1 or not pq.read_schema(paths[0]).equals(SCHEMA, check_metadata=True):
        raise AssertionError("expected one exact active-schema Parquet file")
    return pq.read_table(paths[0]).to_pylist()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    base = yaml.safe_load((ROOT / "config/bb144_tiny.yaml.example").read_text())
    base["experiment"] = {
        "name": "af_bp_final_smoke",
        "purpose": "Two-shot four-decoder final integration check only",
        "codes": [{"family": "surface", "distances": [3]}],
    }
    base["noise"]["rates"] = [.003]
    base["circuit"]["cache"] = str(ROOT / "simulation_data")
    base["sampling"] = {"shots_per_point": 2, "batch_size": 1, "warmup_count": 0}
    base["decoders"][0].update({"graph_rounds": 1, "n_fact": 1,
                                 "initial_iteration_budget": 1,
                                 "transformed_iteration_budget": 1})
    base["decoders"][1].update({"num_sets": 0, "seed": 7})
    serial = parallel = None
    for workers, name in ((1, "serial"), (2, "workers2")):
        config = dict(base)
        config["execution"] = {"workers": workers}
        config["output"] = {"root": str(output / name)}
        path = output / f"{name}.yaml"
        path.write_text(yaml.safe_dump(config))
        run = run_benchmark(path)
        if workers == 1:
            serial = run
        else:
            parallel = run
    assert serial is not None and parallel is not None
    left, right = rows(serial), rows(parallel)
    comparable = lambda values: sorted((item["shot_id"], item["decoder_name"],
                                        item["logical_error"], item["total_iterations"])
                                       for item in values)
    if comparable(left) != comparable(right):
        raise AssertionError("serial/spawn non-latency results differ")
    if len(left) != 8 or {item["decoder_name"] for item in left} != {
            "af_bp", "relay_bp", "beam8", "bposd"}:
        raise AssertionError("four-decoder pairing is incomplete")
    bb = yaml.safe_load((ROOT / "config/bb144_tiny.yaml.example").read_text())
    bb["circuit"]["cache"] = str(ROOT / "simulation_data")
    bb["output"]["root"] = str(output / "bb144")
    bb_path = output / "bb144.yaml"
    bb_path.write_text(yaml.safe_dump(bb))
    bb_run = run_benchmark(bb_path)
    bb_rows = rows(bb_run)
    if len(bb_rows) != 4 or {item["decoder_name"] for item in bb_rows} != {
            "af_bp", "relay_bp", "beam8", "bposd"}:
        raise AssertionError("BB144 four-decoder run is incomplete")
    result = {"serial_run": str(serial), "workers2_run": str(parallel),
              "bb144_run": str(bb_run), "paired_rows_each": len(left),
              "bb144_rows": len(bb_rows), "non_latency_equal": True,
              "bb144_iterations": {item["decoder_name"]: item["total_iterations"]
                                   for item in bb_rows}}
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
