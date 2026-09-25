"""Import-light active and historical project native source inventories."""
from pathlib import Path
import hashlib

AF_BP_SERVICE_FILES = (
    'src/af_bp_core/graph.hpp', 'src/af_bp_core/decoder.hpp',
    'src/af_bp_core/bindings.cpp', 'external_lib/ldpc/src_cpp/af_bp.hpp',
    'CMakeLists.txt',
)


def af_bp_service_digest(root: Path) -> str:
    """Match CMake's SHA256 of ordered source-file SHA256 hex strings."""
    hashes = ''.join(hashlib.sha256((root / path).read_bytes()).hexdigest()
                     for path in AF_BP_SERVICE_FILES)
    return hashlib.sha256(hashes.encode()).hexdigest()

HYBRID_PROJECT_FILES = tuple('src/qec_bp_benchmark/native/' + name for name in (
    'hybrid_model.hpp', 'hybrid_search.hpp', 'hybrid_telemetry.hpp', 'hybrid.hpp',
    'hybrid_bindings.hpp', 'module.cpp',
    'search_bp_model.hpp', 'search_bp_scores.hpp', 'search_bp_search.hpp',
    'search_bp_stage3.hpp', 'search_bp_bindings.hpp',
    'search_bp_admission.hpp', 'search_bp_decoder.hpp',
    'lpm_dp_model.hpp', 'lpm_dp_candidates.hpp', 'lpm_dp_decoder.hpp',
    'lpm_dp_bindings.hpp',
)) + ('CMakeLists.txt', 'src/qec_bp_benchmark/native_sources.py')


def hybrid_project_digest(root: Path) -> str:
    """Hash relative names and bytes; missing native/build inputs raise OSError."""
    digest = hashlib.sha256()
    for name in HYBRID_PROJECT_FILES:
        digest.update(name.encode() + b'\0' + (root / name).read_bytes())
    return digest.hexdigest()


if __name__ == '__main__':
    print(hybrid_project_digest(Path(__file__).resolve().parents[2]))
