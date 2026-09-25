"""Compare patched Beam decisions with an independently built pristine pin."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def decisions(module_path: Path) -> list[dict]:
    sys.path.insert(0, str(module_path))
    import numpy as np
    import beam_search_decoder as beam_package
    from beam_search_decoder import BeamSearchDecoder
    if Path(beam_package.__file__).resolve().parent != (module_path / "beam_search_decoder").resolve():
        raise RuntimeError("Beam fixture imported a decoder from the wrong checkout")

    matrices = [
        [[1, 1, 0, 1, 0, 0, 0, 0], [0, 1, 1, 0, 1, 0, 0, 0],
         [1, 0, 1, 0, 0, 1, 0, 0], [0, 1, 1, 1, 0, 0, 1, 1]],
        [[1, 1, 0, 0, 1, 0], [0, 1, 1, 0, 0, 1], [1, 0, 1, 1, 0, 0]],
        [[1, 1, 0, 0, 0, 1, 0, 0, 0], [0, 1, 1, 0, 1, 0, 0, 0, 0],
         [0, 0, 1, 1, 0, 1, 1, 0, 0], [1, 0, 0, 1, 0, 0, 0, 1, 0],
         [0, 0, 0, 1, 1, 0, 0, 1, 1]],
    ]
    results = []
    for matrix_index, rows in enumerate(matrices):
        h = np.asarray(rows, dtype=np.uint8)
        for setting_index, (width, initial, per_round, rounds) in enumerate(
                ((2, 1, 1, 1), (8, 2, 2, 3))):
            probabilities = ([0.1] * h.shape[1] if setting_index == 0 else
                             [0.03 + (v % 5) * 0.04 for v in range(h.shape[1])])
            decoder = BeamSearchDecoder(
                h, error_channel=probabilities, beam_width=width,
                initial_iters=initial, iters_per_round=per_round,
                max_rounds=rounds, num_results=1)
            for value in range(1 << h.shape[0]):
                syndrome = np.asarray([(value >> shift) & 1
                                       for shift in range(h.shape[0] - 1, -1, -1)],
                                      dtype=np.uint8)
                correction = np.asarray(decoder.decode(syndrome), dtype=np.uint8)
                results.append({"matrix": matrix_index, "setting": setting_index,
                                "syndrome": value, "correction": correction.tolist(),
                                "converged": bool(decoder.converge)})
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", nargs="?")
    parser.add_argument("--emit", type=Path)
    args = parser.parse_args()
    if args.emit:
        print(json.dumps(decisions(args.emit), sort_keys=True))
        return
    if not args.output_dir:
        parser.error("output_dir required")
    output = Path(args.output_dir).resolve() / "beam_pristine_comparison"
    output.mkdir(parents=True, exist_ok=True)
    source = ROOT / "external_lib/BeamSearchDecoder"
    checkout = output / "pristine"
    if checkout.exists():
        parser.error(f"pristine checkout already exists: {checkout}")
    manifest = json.loads((ROOT / "external_lib/manifest.lock.json").read_text())
    pin = manifest["dependencies"]["BeamSearchDecoder"]["commit"]
    subprocess.run(["git", "clone", "--no-local", str(source), str(checkout)], check=True)
    subprocess.run(["git", "-C", str(checkout), "checkout", "--detach", pin], check=True)
    with (output / "pristine_build.log").open("w") as log:
        subprocess.run([sys.executable, "setup.py", "build_ext", "--inplace"],
                       cwd=checkout / "decoder", stdout=log, stderr=subprocess.STDOUT,
                       check=True)
    script = str(Path(__file__).resolve())
    def emit(module_path: Path) -> list[dict]:
        raw = subprocess.check_output([sys.executable, script, "--emit", str(module_path)],
                                      cwd=ROOT, text=True)
        return json.loads(raw)
    pristine = emit(checkout / "decoder")
    patched = emit(source / "decoder")
    if pristine != patched:
        for index, (before, after) in enumerate(zip(pristine, patched)):
            if before != after:
                raise AssertionError(f"Beam decision mismatch at fixture {index}: {before} != {after}")
        raise AssertionError("Beam decision fixture lengths differ")
    digest = hashlib.sha256(json.dumps(pristine, sort_keys=True).encode()).hexdigest()
    result = {"pin": pin, "fixture_count": len(pristine),
              "matrix_count": 3, "settings_per_matrix": 2,
              "decisions_sha256": digest, "equal": True}
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
