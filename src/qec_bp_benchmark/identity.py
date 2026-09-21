"""Independent content identities, using round-trippable binary64 JSON values."""
import hashlib
import json
from datetime import datetime
from .config import Config, Decoder


def content_hash(value: object) -> str:
    """Hash JSON-compatible value with sorted keys; reject nonfinite numbers."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def scientific_identity(instance: dict, artifact_hashes: dict[str, str], config: Config) -> str:
    """Hash one resolved code/rate instance and artifacts, excluding execution/decoders/paths."""
    circuit = config.circuit.model_dump(mode="json", exclude={"cache"})
    return content_hash({"instance": instance, "artifacts": artifact_hashes,
                         "basis": config.experiment.memory_basis, "sector": config.experiment.sector,
                         "noise_profile": config.noise.profile,
                         "multipliers": config.noise.multipliers.model_dump(),
                         "circuit": circuit, "dem": config.dem.model_dump()})


def decoder_identity(decoder: Decoder, implementation: dict) -> str:
    """Hash complete algorithm settings and source/build identity, excluding display/enabled flags."""
    return content_hash({"parameters": decoder.model_dump(exclude={"name", "enabled"}),
                         "implementation": implementation})


def sampling_identity(config: Config, stim_version: str) -> str:
    """Hash immutable physical batch layout/seed; excludes decoders, workers, warmup and paths."""
    return content_hash({"master_seed": config.sampling.master_seed,
                         "shots": config.sampling.shots_per_point,
                         "batch_size": config.sampling.batch_size, "stim_version": stim_version,
                         "call": "one physical Circuit.compile_detector_sampler.sample per batch",
                         "seed_recipe": "sha256-instance/SeedSequence/stream-tag/batch/v1"})


def run_identity(config: Config, timestamp: datetime, nonce: str) -> str:
    """Hash timezone-aware run timestamp, unique nonce and complete execution configuration."""
    if timestamp.tzinfo is None:
        raise ValueError("run timestamp must be timezone-aware")
    return content_hash({"timestamp": timestamp.isoformat(), "nonce": nonce, "config": config.resolved()})
