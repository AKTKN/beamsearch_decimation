"""Strict YAML configuration; no numerical/native imports during bootstrap."""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Annotated, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

Positive = Annotated[int, Field(strict=True, gt=0)]
Nonnegative = Annotated[int, Field(strict=True, ge=0)]
Probability = Annotated[float, Field(ge=0, le=0.5, allow_inf_nan=False)]
PositiveNativeCount = Annotated[int, Field(strict=True, ge=1, le=2**31-1)]


class StrictModel(BaseModel):
    """Immutable validated settings, rejecting unknown keys and nonfinite numbers."""
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True, allow_inf_nan=False)


class Code(StrictModel):
    family: Literal["surface", "bb72", "bb144"]
    distances: tuple[Positive, ...] = (5, 7, 9)
    rounds: Positive | None = None

    @model_validator(mode="after")
    def check(self) -> Self:
        if not self.distances or len(set(self.distances)) != len(self.distances):
            raise ValueError("distances must be nonempty and unique")
        if self.family == "bb72" and self.distances != (6,):
            raise ValueError("bb72 requires distances: [6]")
        if self.family == "bb144" and self.distances != (12,):
            raise ValueError("bb144 requires distances: [12]")
        if self.family == "surface" and any(d < 3 or d % 2 == 0 for d in self.distances):
            raise ValueError("surface distances must be odd and at least 3")
        return self


class Experiment(StrictModel):
    name: str = "implementation_smoke"
    purpose: str = "Implementation validation only; no performance claim"
    codes: tuple[Code, ...] = (Code(family="surface"), Code(family="bb72", distances=(6,)))
    memory_basis: Literal["Z"] = "Z"
    sector: Literal["Z_checks"] = "Z_checks"
    round_rule: Literal["distance"] = "distance"

    @model_validator(mode="after")
    def check(self) -> Self:
        points = [(c.family, d, c.rounds or d) for c in self.codes for d in c.distances]
        if not points or len(set(points)) != len(points):
            raise ValueError("code instances must be nonempty and unique")
        return self


class Grid(StrictModel):
    kind: Literal["linear", "log"]
    start: Probability
    stop: Probability
    count: Positive

    @model_validator(mode="after")
    def check(self) -> Self:
        if self.start >= self.stop or self.count < 2 or (self.kind == "log" and self.start <= 0):
            raise ValueError("grid requires start < stop, count >= 2, and positive log endpoints")
        return self

    def expand(self) -> tuple[float, ...]:
        """Return endpoint-inclusive binary64 probabilities, without mutation."""
        values = []
        for i in range(self.count):
            t = i / (self.count - 1)
            values.append(self.start + t * (self.stop - self.start) if self.kind == "linear"
                          else math.exp(math.log(self.start) + t * math.log(self.stop / self.start)))
        values[0], values[-1] = self.start, self.stop
        return tuple(values)


class Multipliers(StrictModel):
    one_qubit: Annotated[float, Field(ge=0)] = 1.0
    two_qubit: Annotated[float, Field(ge=0)] = 1.0
    idle: Annotated[float, Field(ge=0)] = 1.0
    reset: Annotated[float, Field(ge=0)] = 1.0
    measurement: Annotated[float, Field(ge=0)] = 1.0


class Noise(StrictModel):
    profile: Literal["circuit_depolarizing"] = "circuit_depolarizing"
    rates: tuple[Probability, ...] | None = None
    sweep: Grid | None = None
    multipliers: Multipliers = Multipliers()

    @model_validator(mode="after")
    def check(self) -> Self:
        if (self.rates is None) == (self.sweep is None):
            raise ValueError("specify exactly one of noise.rates or noise.sweep")
        rates = self.expanded_rates
        if not rates or len(set(rates)) != len(rates):
            raise ValueError("physical-rate grid must be nonempty and contain no duplicates")
        if any(p * mu > 1 for p in rates for mu in self.multipliers.model_dump().values()):
            raise ValueError("all multiplied physical probabilities must be <= 1")
        return self

    @property
    def expanded_rates(self) -> tuple[float, ...]:
        return self.rates if self.rates is not None else self.sweep.expand()


class Circuit(StrictModel):
    surface_provider: Literal["stim"] = "stim"
    bb_provider: Literal["qldpc"] = "qldpc"
    surface_schedule: Literal["rotated_memory_z"] = "rotated_memory_z"
    bb_schedule: Literal["edge_coloring"] = "edge_coloring"
    edge_coloring_strategy: Literal["smallest_last"] = "smallest_last"
    boundary: Literal["noisy_prepare_extract_readout"] = "noisy_prepare_extract_readout"
    cache: Path = Path("../simulation_data")


class Dem(StrictModel):
    decompose_errors: Literal[False] = False
    approximate_disjoint_errors: bool = False
    allow_gauge_detectors: Literal[False] = False
    sector_mapping: Literal["measurement_provenance"] = "measurement_provenance"
    merge: Literal["none"] = "none"
    normalization: Literal["remove_zero_reject_above_half"] = "remove_zero_reject_above_half"


class Bposd(StrictModel):
    profile: Literal["bposd"] = "bposd"
    name: str = "bposd"
    enabled: bool = True
    max_iter: Positive = 30
    bp_method: Literal["minimum_sum"] = "minimum_sum"
    schedule: Literal["parallel"] = "parallel"
    ms_scaling_factor: Literal[1.0] = 1.0
    osd_method: Literal["OSD_CS"] = "OSD_CS"
    osd_order: Nonnegative = 10
    omp_thread_count: Literal[1] = 1

class Beam(StrictModel):
    profile: Literal["beam8"] = "beam8"
    name: str = "beam8"
    enabled: bool = True
    max_rounds: Positive = 10
    beam_width: Literal[8] = 8
    num_results: Literal[1] = 1
    initial_iters: Positive = 30
    iters_per_round: Positive = 20


class RelayBP(StrictModel):
    """Pinned upstream F64 Relay settings; gamma draws come from its seeded RNG."""
    profile: Literal["relay_bp"] = "relay_bp"
    kind: Literal["relay_bp"] = "relay_bp"
    name: str = "relay_bp"
    enabled: bool = True
    alpha: float | None = None
    alpha_iteration_scaling_factor: Annotated[float, Field(gt=0)] = 1.0
    gamma0: float | None = 0.1
    pre_iter: Positive = 80
    num_sets: Nonnegative = 300
    set_max_iter: Positive = 60
    gamma_dist_interval: tuple[float, float] = (-0.24, 0.66)
    stop_nconv: Positive = 1
    seed: Annotated[int, Field(strict=True, ge=0, le=2**64-1)] = 0

    @model_validator(mode="after")
    def check(self) -> Self:
        if self.gamma_dist_interval[0] >= self.gamma_dist_interval[1]:
            raise ValueError("gamma_dist_interval requires low < high")
        return self


class AFBP(StrictModel):
    """Strict AF-BP-1.0 experiment settings, mapped once to the native service."""
    profile: Literal["af_bp"] = "af_bp"
    kind: Literal["af_bp"] = "af_bp"
    name: str = "af_bp"
    enabled: bool = True
    history_window: Positive = 8
    residual_radius: Nonnegative = 2
    distance_decay: Annotated[float, Field(ge=0, le=1)] = 0.5
    uncertainty_weight: Annotated[float, Field(ge=0)] = 1.0
    oscillation_weight: Annotated[float, Field(ge=0)] = 1.0
    U_selection: Literal["top_k", "threshold"] = "top_k"
    U_top_k: Nonnegative = 32
    U_threshold: Annotated[float, Field(ge=0)] = 0.5
    factorization_policy: Literal["adaptive_cycle", "shen_cycle_count"] = "adaptive_cycle"
    n_fact: Nonnegative = 1
    graph_rounds: Nonnegative = 4
    bp_variant: Literal["parallel", "serial", "qdither"] = "parallel"
    initial_parallel: bool = True
    initial_iteration_budget: Nonnegative = 50
    transformed_iteration_budget: Nonnegative = 50
    ms_scaling_factor: Annotated[float, Field(gt=0, le=1)] = 1.0
    serial_order: Literal["natural", "random_per_iteration"] = "random_per_iteration"
    atanh_epsilon: Annotated[float, Field(gt=0, lt=1)] = 1e-12
    qdither_phase1_iterations: Nonnegative = 30
    qdither_chains: Nonnegative = 0
    qdither_iterations_per_chain: Nonnegative = 20
    qdither_alpha: Annotated[float, Field(ge=0, le=1)] = 0.0
    qdither_beta: Annotated[float, Field(ge=0, le=1)] = 1.0
    qdither_rho: Annotated[float, Field(ge=0, le=1)] = 0.0
    qdither_handoff: Literal["paper", "graph_warm"] = "graph_warm"
    seed: Annotated[int, Field(strict=True, ge=0, le=2**64-1)] = 0
    seed_policy: Literal["fixed", "syndrome_derived"] = "syndrome_derived"

    @model_validator(mode="after")
    def check(self) -> Self:
        total_weight = self.uncertainty_weight + self.oscillation_weight
        if not math.isfinite(total_weight) or total_weight <= 0:
            raise ValueError("at least one failure weight must be positive")
        native_counts = (self.history_window, self.residual_radius, self.U_top_k,
                         self.n_fact, self.graph_rounds, self.initial_iteration_budget,
                         self.transformed_iteration_budget, self.qdither_phase1_iterations,
                         self.qdither_chains, self.qdither_iterations_per_chain)
        if any(value > 2**31 - 1 for value in native_counts):
            raise ValueError("AF-BP native integer settings must fit signed int32")
        if self.qdither_alpha > self.qdither_beta:
            raise ValueError("qdither_alpha must not exceed qdither_beta")
        if (self.bp_variant == "qdither" and self.graph_rounds > 0 and
                self.n_fact > 0 and self.qdither_handoff != "graph_warm"):
            raise ValueError("AF-BP qDither graph relay requires graph_warm handoff")
        return self


Decoder = Annotated[Bposd | Beam | RelayBP | AFBP, Field(discriminator="profile")]


class Sampling(StrictModel):
    shots_per_point: Positive = 32
    batch_size: Positive = 16
    master_seed: Nonnegative = 20260920
    warmup_seed: Nonnegative = 20260921
    warmup_count: Nonnegative = 4
    store_raw_samples: Literal[False] = False


class Execution(StrictModel):
    workers: Positive = 4
    start_method: Literal["spawn"] = "spawn"
    max_pending: Positive | None = None
    worker_cache_size: Positive = 2
    native_threads: Literal[1] = 1
    blas_threads: Literal[1] = 1
    affinity: tuple[Nonnegative, ...] | None = None

    @model_validator(mode="after")
    def resolve(self) -> Self:
        if self.max_pending is None:
            object.__setattr__(self, "max_pending", 2 * self.workers)
        if self.affinity is not None and (not self.affinity or len(set(self.affinity)) != len(self.affinity)):
            raise ValueError("affinity must be nonempty and unique")
        return self


class Timing(StrictModel):
    mode: Literal["throughput", "isolated_latency"] = "throughput"
    timers: tuple[Literal["process_time_ns", "perf_counter_ns"], ...] = ("process_time_ns", "perf_counter_ns")
    decoder_order: Literal["cyclic"] = "cyclic"
    profiling: Literal["none", "phases"] = "none"

    @model_validator(mode="after")
    def check(self) -> Self:
        if set(self.timers) != {"process_time_ns", "perf_counter_ns"} or len(self.timers) != 2:
            raise ValueError("both nanosecond timers are required exactly once")
        return self


class Output(StrictModel):
    root: Path = Path("../assets/runs")
    compression: Literal["zstd", "snappy", "none"] = "zstd"
    shard_policy: Literal["paired_atomic_batch"] = "paired_atomic_batch"
    retain_traces: Literal[False] = False
    retain_corrections: Literal[False] = False


class Config(StrictModel):
    config_schema_version: Literal["af_bp_config/2"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    experiment: Experiment = Experiment()
    noise: Noise
    circuit: Circuit = Circuit()
    dem: Dem = Dem()
    decoders: tuple[Decoder, ...] = (Bposd(), Beam())
    sampling: Sampling = Sampling()
    execution: Execution = Execution()
    timing: Timing = Timing()
    output: Output = Output()

    @model_validator(mode="after")
    def check(self) -> Self:
        if self.timing.mode == "isolated_latency" and self.execution.workers != 1:
            raise ValueError("isolated_latency requires exactly one worker")
        names = [d.name for d in self.decoders]
        if len(set(names)) != len(names) or not any(d.enabled for d in self.decoders):
            raise ValueError("decoder names must be unique, with at least one enabled")
        return self

    def resolved(self) -> dict:
        """Return detached JSON-safe settings with expanded rates; no mutation."""
        data = self.model_dump(mode="json")
        data["noise"]["expanded_rates"] = list(self.noise.expanded_rates)
        data["experiment"]["instances"] = [
            {"family": c.family, "distance": d, "rounds": c.rounds or d,
             "round_override": c.rounds is not None}
            for c in self.experiment.codes for d in c.distances]
        for decoder in data["decoders"]:
            if decoder["profile"] == "beam8":
                decoder["implementation_properties"] = {
                    "bp_method": "upstream_min_sum", "hard_decision": "L<=0",
                    "branch_degree_filter": "skip columns with degree <=2",
                    "message_clip": "no configurable finite clip",
                    "tie_breaking": "upstream strict comparisons and (score,storage_index) priority queue",
                    "native_threads": 1,
                }
            elif decoder["profile"] == "bposd":
                decoder["implementation_properties"] = {
                    "hard_decision": "upstream L<=0", "error_channel_type": "list",
                    "converge_flag": "BP stage only; validate correction after OSD",
                }
            elif decoder["profile"] == "relay_bp":
                decoder["implementation_properties"] = {
                    "backend": "upstream RelayDecoderF64.decode_detailed",
                    "stopping_criterion": "nconv", "logging": False,
                    "batch_parallelism": False,
                }
            else:
                decoder["implementation_properties"] = {
                    "algorithm_version": "AF-BP-1.0",
                    "backend": "qec_bp_benchmark.af_bp_service.AFBPDecoder",
                    "truth_input": False,
                }
        return data


def require_available_decoder(profile: str) -> None:
    """Reject decimation and unimplemented future decoders from active runs."""
    if profile not in ("beam8", "bposd", "relay_bp", "af_bp"):
        raise ValueError(f"unsupported active decoder profile: {profile}")


class _UniqueLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError(f"duplicate YAML key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def load_config(path: str | Path) -> Config:
    """Load safe YAML and resolve all paths relative to its file.

    Args:
        path: YAML file path, in filesystem units.
    Returns:
        Immutable validated configuration. Input files are never modified.
    Raises:
        OSError, yaml.YAMLError, ValueError: Missing files or invalid settings.
    """
    path = Path(path).resolve()
    config = Config.model_validate(yaml.load(path.read_text(), Loader=_UniqueLoader))
    data = config.model_dump()
    for group, fields in {"circuit": ("cache",), "output": ("root",)}.items():
        for field in fields:
            data[group][field] = (path.parent / data[group][field]).resolve()
    return Config.model_validate(data)
