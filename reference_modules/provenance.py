"""Source, environment and scientific-convention manifests."""
from pathlib import Path
from datetime import datetime
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import zipfile
from .config import PROJECT_ROOT, GRID_PROVENANCE, HISTORICAL_NOTE, FORCED_GAP_SOURCE


def source_hashes() -> dict[str, str]:
    """Return SHA256 hashes of every package source and project packaging file."""
    paths = sorted((PROJECT_ROOT / "src/color_code_softoutput").rglob("*.py"))
    paths += [PROJECT_ROOT / "pyproject.toml"]
    return {str(p.relative_to(PROJECT_ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def repository_state(path: Path) -> dict:
    """Return exact Git identity/status; explicitly represent non-Git workspaces.

    Args:
        path: Repository root to inspect.
    Returns:
        SHA, branch, porcelain status, dirty flag and diff hash where applicable.
    """
    if not (path / ".git").exists():
        return dict(sha=None, dirty=None, status="not a Git repository; source hashes recorded")
    def git(*args):
        return subprocess.check_output(["git", "-C", str(path), *args], text=True).strip()
    status = git("status", "--porcelain")
    return dict(sha=git("rev-parse", "HEAD"), branch=git("branch", "--show-current"),
                dirty=bool(status), status=status,
                diff_sha256=hashlib.sha256(git("diff", "HEAD").encode()).hexdigest())


def environment_metadata() -> dict:
    """Capture shared source/environment provenance for any experiment.

    Returns:
        JSON-compatible repository identities, package versions, import paths,
        interpreter, thread settings and package source hashes. The main root
        is explicitly identified as non-Git when applicable.
    """
    import pymatching
    import color_code_stim
    return dict(
        repositories={"main":repository_state(PROJECT_ROOT), **{
            name:repository_state(PROJECT_ROOT / "external_libs" / name)
            for name in ("PyMatching", "color-code-stim")}},
        python=sys.version, executable=sys.executable, conda_environment=Path(sys.prefix).name, conda_prefix=sys.prefix,
        shell_conda_environment=os.environ.get("CONDA_DEFAULT_ENV"),
        platform=platform.platform(), cpu=platform.processor(), cpu_count=os.cpu_count(),
        thread_environment={key:os.environ.get(key) for key in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS","MPLBACKEND")},
        dependencies={d.metadata["Name"]:d.version for d in importlib.metadata.distributions() if d.metadata["Name"]},
        imported_package_paths={"pymatching":pymatching.__file__, "color_code_stim":color_code_stim.__file__},
        source_hashes=source_hashes())


def create_metadata(config, timestamp: datetime) -> dict:
    """Capture complete reproducibility metadata before any sampling.

    Args:
        config: Validated fixed experiment configuration.
        timestamp: Timezone-aware creation time.
    Returns:
        JSON-compatible manifest including source limitations and seed recipe.
    """
    from color_code_stim.soft_output.results import GROWTH_CONVENTION
    import pymatching
    import color_code_stim
    return dict(
        timestamp=timestamp.isoformat(), timezone=str(timestamp.tzinfo), experiment_name="phase2a_test",
        phase="2B", resolved_config=config.resolved(), config_hash=config.config_hash,
        command_argv=sys.argv, master_seed=config.master_seed,
        seed_recipe="uint64 SeedSequence([master_seed, *little_endian_uint32(SHA256(config_id)), batch_id])",
        grid_provenance=GRID_PROVENANCE, near_threshold_ps=config.near_threshold_ps,
        subthreshold_ps=config.subthreshold_ps, distances=config.distances,
        shots_per_point=config.shots_per_point, batch_size=config.batch_size, num_workers=config.num_workers,
        noise_model="NoiseModel(bitflip=p); all other noise absent", rounds=1,
        circuit_type="tri", cnot_schedule="tri_optimal", decoder_mode="ordinary concatenated MWPM + paired comparative",
        selected_swim_rule="phi of ordinary hard decoder selected color; never min over colors",
        forced_gap_source=FORCED_GAP_SOURCE,
        metric_failure_labels={"selected_swim_distance":"ordinary_logical_error", "forced_gap":"comparative_logical_error"},
        pairing="same physical sample; comparative detector prefix plus ordinary observable parity; forced input overwrites extra bit",
        swim_growth_convention=GROWTH_CONVENTION, swim_bound_certified=False,
        limitations="No certified odd-cut dual, posterior calibration, or full-decoder gap theorem; selected-color score is empirical",
        historical_note=HISTORICAL_NOTE,
        **environment_metadata(), analysis_version="0.2.0", status="running",
        confidence_level=.99, resume="not implemented; atomic shards preserved on failure; use a new run directory",
    )


def write_json(path: Path, contents: dict) -> None:
    """Atomically replace a small UTF-8 JSON manifest with finite JSON values."""
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(contents, indent=2, sort_keys=True, allow_nan=False)+"\n")
    temporary.replace(path)


def archive_sources(path: Path, hashes: dict[str, str]) -> None:
    """Archive main sources matching the manifest, since this workspace has no Git.

    Args:
        path: New ZIP destination inside the run directory.
        hashes: Project-relative source paths and their recorded SHA256 values.
    Raises:
        ValueError: A source changed between metadata capture and archiving.
        FileExistsError: Archive already exists.
    """
    with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, expected in hashes.items():
            contents = (PROJECT_ROOT / name).read_bytes()
            if hashlib.sha256(contents).hexdigest() != expected:
                raise ValueError(f"Source changed while freezing run: {name}")
            archive.writestr(name, contents)
