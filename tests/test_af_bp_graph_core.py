"""Build and execute the standalone C++ graph-core assertions."""
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_af_bp_graph_core_native(tmp_path: Path) -> None:
    binary = tmp_path / "af_bp_graph_core_test"
    subprocess.run([
        "g++", "-std=c++17", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
        "-fno-fast-math", "-I", str(ROOT / "src"),
        str(ROOT / "tests/native/af_bp_graph_core_test.cpp"), "-o", str(binary),
    ], check=True)
    subprocess.run([str(binary)], check=True, timeout=60)
