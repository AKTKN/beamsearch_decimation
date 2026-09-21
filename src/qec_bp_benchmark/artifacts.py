"""Content-addressed immutable circuit/DEM/matrix preparation artifacts."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import numpy as np
from .config import Config
from .circuits import make_template, apply_noise, select_z_detectors, operation_inventory
from .dem import convert_dem
from .identity import content_hash, scientific_identity


def _json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def verify_artifact(path: str | Path) -> dict:
    """Verify all committed file hashes; return manifest or raise ValueError/OSError."""
    path = Path(path)
    manifest = json.loads((path / "manifest.json").read_text())
    if manifest.get("schema_version") != 1 or manifest.get("status") != "complete":
        raise ValueError("artifact is incomplete or uses an unsupported schema")
    for name, expected in manifest["files"].items():
        if hashlib.sha256((path / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"artifact checksum mismatch: {name}")
    return manifest


def prepare_instance(config: Config, family: str, distance: int, p: float,
                     rounds: int | None = None) -> Path:
    """Build and atomically preserve one physical scientific instance from YAML.

    Args:
        config: Validated configuration with absolute circuit cache path.
        family, distance, rounds: Provider settings; rounds=None means R=d.
        p: One explicitly resolved physical sweep probability.
    Returns:
        Directory of exact circuit, selected view, DEM, matrices and maps.
        Existing content is reused only after checksum verification.
    Raises:
        ValueError/OSError: Invalid circuit/DEM, corrupted artifact or write failure.
        No decoder is called and no physical benchmark is sampled here.
    """
    import stim
    import qldpc
    repository = Path(__file__).resolve().parents[2]
    dependencies = json.loads((repository / "external_lib/manifest.lock.json").read_text())["dependencies"]
    provider_sources = {name: dependencies[name]["commit"] for name in ("Stim", "qLDPC")}
    template = make_template(family, distance, rounds)
    eligible = tuple(sorted((*template.data_qubits, *template.check_sectors)))
    noisy = apply_noise(template.circuit, p, config.noise.multipliers, eligible)
    view = select_z_detectors(noisy, template)
    options = config.dem.model_dump()
    dem = view.circuit.detector_error_model(decompose_errors=config.dem.decompose_errors,
                                           approximate_disjoint_errors=config.dem.approximate_disjoint_errors,
                                           allow_gauge_detectors=config.dem.allow_gauge_detectors)
    problem = convert_dem(dem, extraction_options=options)
    hashes = {**problem.hashes, "circuit": hashlib.sha256(str(noisy).encode()).hexdigest(),
              "selected_circuit": hashlib.sha256(str(view.circuit).encode()).hexdigest(),
              "detector_mapping": content_hash(view.detectors), "observable_mapping": content_hash(view.observables)}
    instance = {**template.metadata, "p": p, "provider_sources": provider_sources}
    instance_id = scientific_identity(instance, hashes, config)
    root = config.circuit.cache
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"{family}_d{distance}_r{template.metadata['rounds']}_{instance_id}"
    if target.exists():
        verify_artifact(target)
        return target
    temporary = Path(tempfile.mkdtemp(prefix=".preparing-", dir=root))
    try:
        (temporary / "circuit.stim").write_text(str(noisy))
        (temporary / "noiseless.stim").write_text(str(template.circuit))
        (temporary / "selected.stim").write_text(str(view.circuit))
        (temporary / "detector_model.dem").write_text(str(dem))
        _json(temporary / "instance.json", {**instance, "scientific_instance_id": instance_id,
              "hashes": hashes, "idle_eligible_qubits": eligible,
              "noise": {"profile": config.noise.profile, "multipliers": config.noise.multipliers.model_dump()},
              "extraction": options, "stim_version": stim.__version__, "qldpc_version": qldpc.__version__,
              "timing_convention": "qLDPC conflict-split TICK moments; flatten before injection; no extra measurement/reset waiting noise"})
        _json(temporary / "detector_mapping.json", {"full_to_selected": view.full_to_selected,
              "selected_to_full": view.selected_to_full, "detectors": view.detectors})
        _json(temporary / "observable_mapping.json", view.observables)
        _json(temporary / "normalization.json", {"instruction_to_column": problem.instruction_to_column,
              "original_error_to_column": problem.original_error_to_column,
              "column_to_instruction": problem.column_to_instruction, "syndrome_offset": "zero", "observable_offset": "zero"})
        _json(temporary / "inventory.json", operation_inventory(noisy))
        matrices = temporary / "matrices"
        matrices.mkdir()
        for key, matrix in (("H", problem.H), ("A", problem.A)):
            np.save(matrices / f"{key}_shape.npy", np.asarray(matrix.shape, dtype="<i8"), allow_pickle=False)
            np.save(matrices / f"{key}_indptr.npy", matrix.indptr.astype("<i8"), allow_pickle=False)
            np.save(matrices / f"{key}_indices.npy", matrix.indices.astype("<i8"), allow_pickle=False)
            # Every canonical nonzero is one, so no separate data buffer is needed.
        np.save(matrices / "p.npy", problem.probabilities, allow_pickle=False)
        for key, matrix in template.algebra.items():
            np.save(matrices / f"{key}.npy", matrix, allow_pickle=False)
        file_hashes = {str(path.relative_to(temporary)): hashlib.sha256(path.read_bytes()).hexdigest()
                       for path in sorted(temporary.rglob("*")) if path.is_file()}
        _json(temporary / "manifest.json", {"schema_version": 1, "status": "complete",
              "scientific_instance_id": instance_id, "files": file_hashes, "hashes": hashes})
        try:
            temporary.rename(target)
        except OSError:
            if not target.exists():
                raise
            existing = verify_artifact(target)
            if existing["files"] != file_hashes:
                raise ValueError("concurrent artifact creation produced inconsistent bytes")
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return target


def load_problem(path: str | Path):
    """Load owned canonical arrays from a verified artifact directory.

    Args:
        path: Prepared artifact directory, with all immutable files intact.
    Returns:
        DetectorProblem with read-only CSC/float buffers and original mappings.
    Raises:
        ValueError/OSError: Corruption, incompatible content or missing files.
    """
    from scipy.sparse import csc_matrix
    from .dem import DetectorProblem, sparse_hash
    path = Path(path)
    manifest = verify_artifact(path)
    metadata = json.loads((path / "instance.json").read_text())
    normalization = json.loads((path / "normalization.json").read_text())
    matrices = []
    for name in ("H", "A"):
        shape = tuple(np.load(path / f"matrices/{name}_shape.npy", allow_pickle=False))
        indices = np.load(path / f"matrices/{name}_indices.npy", allow_pickle=False)
        indptr = np.load(path / f"matrices/{name}_indptr.npy", allow_pickle=False)
        matrix = csc_matrix((np.ones(len(indices),dtype=np.uint8),indices,indptr),shape=shape)
        if sparse_hash(matrix) != manifest["hashes"][name]:
            raise ValueError(f"canonical {name} identity mismatch")
        for buffer in (matrix.data,matrix.indices,matrix.indptr):
            buffer.flags.writeable = False
        matrices.append(matrix)
    p = np.load(path / "matrices/p.npy",allow_pickle=False)
    if hashlib.sha256(p.tobytes()).hexdigest() != manifest["hashes"]["p"]:
        raise ValueError("canonical probability identity mismatch")
    p.flags.writeable = False
    return DetectorProblem(matrices[0],matrices[1],p,
        tuple(normalization["instruction_to_column"]),tuple(normalization["original_error_to_column"]),
        tuple(normalization["column_to_instruction"]),
        {key:manifest["hashes"][key] for key in ("H","A","p","dem","mappings","extraction_options")},metadata["extraction"])
