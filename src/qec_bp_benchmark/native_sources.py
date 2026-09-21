"""Import-light hybrid project source inventory shared by CMake and runtime checks."""
from pathlib import Path
import hashlib

HYBRID_PROJECT_FILES = tuple('src/qec_bp_benchmark/native/' + name for name in (
    'hybrid_model.hpp', 'hybrid_search.hpp', 'hybrid_telemetry.hpp', 'hybrid.hpp',
    'hybrid_bindings.hpp', 'module.cpp',
)) + ('CMakeLists.txt', 'src/qec_bp_benchmark/native_sources.py')


def hybrid_project_digest(root: Path) -> str:
    """Hash relative names and bytes; missing native/build inputs raise OSError."""
    digest = hashlib.sha256()
    for name in HYBRID_PROJECT_FILES:
        digest.update(name.encode() + b'\0' + (root / name).read_bytes())
    return digest.hexdigest()


if __name__ == '__main__':
    print(hybrid_project_digest(Path(__file__).resolve().parents[2]))
