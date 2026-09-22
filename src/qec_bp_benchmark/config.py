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
    family: Literal["surface", "bb72"]
    distances: tuple[Positive, ...] = (5, 7, 9)
    rounds: Positive | None = None

    @model_validator(mode="after")
    def check(self) -> Self:
        if not self.distances or len(set(self.distances)) != len(self.distances):
            raise ValueError("distances must be nonempty and unique")
        if self.family == "bb72" and self.distances != (6,):
            raise ValueError("bb72 requires distances: [6]")
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


class Screened(StrictModel):
    profile: Literal["screened_reference"] = "screened_reference"
    name: str = "screened_reference"
    enabled: bool = True
    T0: Positive = 30
    Tpost: Positive = 30
    history_window: Positive = 8
    M: Positive = 16
    q: Positive = 2
    K: Positive = 8
    Lmax: Annotated[float, Field(gt=0, le=30)] = 25.0
    bp_method: Literal["sum_product"] = "sum_product"
    schedule: Literal["flooding"] = "flooding"
    arithmetic: Literal["binary64"] = "binary64"
    damping: Literal[False] = False
    warm_start: Literal[False] = False
    fallback: Literal["none"] = "none"

    @model_validator(mode="after")
    def check(self) -> Self:
        if self.q > self.M:
            raise ValueError("q must not exceed M; q <= n is also checked against the prepared problem")
        return self


class Bposd(StrictModel):
    profile: Literal["bposd_ms30_cs10"] = "bposd_ms30_cs10"
    name: str = "bposd_ms30_cs10"
    enabled: bool = True
    max_iter: Positive = 30
    bp_method: Literal["minimum_sum"] = "minimum_sum"
    schedule: Literal["parallel"] = "parallel"
    ms_scaling_factor: Literal[1.0] = 1.0
    osd_method: Literal["OSD_CS"] = "OSD_CS"
    osd_order: Nonnegative = 10
    omp_thread_count: Literal[1] = 1


class Bposd0(Bposd):
    """Actual upstream BP followed by CS0; not the hybrid's OSD-only bridge."""

    profile: Literal["bposd_ms30_cs0"] = "bposd_ms30_cs0"
    name: str = "bposd_ms30_cs0"
    osd_order: Annotated[int, Field(strict=True, ge=0, le=0)] = 0


# Checked native boundary sizes; cycle lists also bound configuration allocation.
NativeCount = Annotated[int, Field(strict=True, ge=0, le=2**31 - 1)]
WorkCount = Annotated[int, Field(strict=True, ge=0, le=2**64 - 1)]
CycleBudget = WorkCount | tuple[WorkCount, ...]
HYBRID_PROFILES = (
    "hybrid_search_soft_ms_osd0_v1",
    "search_osd0_v1",
    "hybrid_search_soft_ms_osd0_cold_v1",
)
SEARCH_BP_PROFILE = "search_bp"


class HybridSearch(StrictModel):
    """Global shot limits and expansion budgets (counts, except CPU nanoseconds).

    Scalars are broadcast by Hybrid to max_cycles entries. The node cap includes
    the root; it triggers fallback before constructing a child beyond capacity.
    The optional process-CPU cap covers only the prefix, not OSD or full service.
    """

    max_depth: NativeCount = 2
    max_cycles: Annotated[int, Field(strict=True, ge=0, le=65536)] = 3
    expansions_per_cycle: CycleBudget = 8
    max_generated_nodes: Annotated[int, Field(strict=True, ge=1, le=2**64 - 1)] = 4096
    detector_order: Literal["canonical_index"] = "canonical_index"
    branch_order: Literal["physical_weight_then_index"] = "physical_weight_then_index"
    heuristic: Literal["residual_fractional_cover"] = "residual_fractional_cover"
    goal_test: Literal["on_generation"] = "on_generation"
    guidance_selection: Literal["best_unused_generated_pattern"] = "best_unused_generated_pattern"
    prefix_cpu_budget_ns: Annotated[int, Field(strict=True, gt=0, le=2**63 - 1)] | None = None


class HybridBP(StrictModel):
    """Finite replacement fields and within-shot parallel min-sum continuation.

    LLR parameters are dimensionless finite binary64 values. Posterior beliefs
    are never channel priors. Disabled BP requires zero resolved iteration work.
    """

    enabled: Annotated[bool, Field(strict=True)] = True
    method: Literal["minimum_sum"] = "minimum_sum"
    schedule: Literal["parallel"] = "parallel"
    iterations_per_cycle: NativeCount | tuple[NativeCount, ...] = 6
    scaling_factor: Annotated[float, Field(strict=True, gt=0, le=1)] = 1.0
    llr_clip: Annotated[float, Field(strict=True, gt=0)] = 25.0
    hard_decision_zero: Literal["one"] = "one"
    warm_start: Annotated[bool, Field(strict=True)] = True
    hint_policy: Literal["signed_channel_magnitude_plus_margin"] = "signed_channel_magnitude_plus_margin"
    hint_margin_llr: Annotated[float, Field(strict=True, gt=0)] = 8.0
    replace_previous_hint: Literal[True] = True


class HybridFallback(StrictModel):
    """Direct pinned native OSD on original H/s; no hidden BP or hard hints."""

    backend: Literal["ldpc_osd_only"] = "ldpc_osd_only"
    osd_method: Literal["OSD_CS"] = "OSD_CS"
    osd_order: Annotated[int, Field(strict=True, ge=0, le=0)] = 0
    llr_source: Literal["last_bp_else_clipped_channel"] = "last_bp_else_clipped_channel"
    ordering: Literal["pinned_ldpc_signed_llr"] = "pinned_ldpc_signed_llr"


class HybridNumerics(StrictModel):
    """Deterministic reductions; no contraction or fast-math in future kernels."""

    dtype: Literal["float64"] = "float64"
    heuristic_reduction: Literal["fixed_binary_tree"] = "fixed_binary_tree"
    fast_math: Literal[False] = False


class SearchBPSearch(StrictModel):
    """Step 3/4/6 budgets; names distinguish check count from matrix row count."""
    selected_checks: PositiveNativeCount = 2
    local_variables: PositiveNativeCount = 4
    local_variable_policy: Literal['fixed_root', 'refresh_descendant'] = 'refresh_descendant'
    max_fixations: PositiveNativeCount = 2
    max_cycles: PositiveNativeCount = 2
    beta: Annotated[float, Field(strict=True, ge=0)] = 1.0
    guidance_strength: Annotated[float, Field(strict=True, ge=0)] = 1.0

    @model_validator(mode="after")
    def check(self) -> Self:
        if self.max_fixations > self.local_variables:
            raise ValueError("max_fixations must not exceed local_variables")
        return self


class SearchBPBP(StrictModel):
    """Parallel minimum-sum budgets and clipped posterior history."""
    initial_iterations: PositiveNativeCount = 30
    candidate_iterations: PositiveNativeCount = 20
    history_window: PositiveNativeCount = 8
    average_llr_clip: Annotated[float, Field(strict=True, gt=0)] = 25.0
    scaling_factor: Annotated[float, Field(strict=True, gt=0, le=1)] = 1.0

    @model_validator(mode="after")
    def check(self) -> Self:
        if self.history_window > min(self.initial_iterations, self.candidate_iterations):
            raise ValueError("history_window exceeds a BP iteration budget")
        if self.average_llr_clip > sys.float_info.max / (2.0 * self.history_window):
            raise ValueError("average_llr_clip can overflow the history accumulator")
        return self


class SearchBPAdmission(StrictModel):
    k_run: PositiveNativeCount = 4
    k_keep: PositiveNativeCount = 2

    @model_validator(mode="after")
    def check(self) -> Self:
        if self.k_keep > self.k_run:
            raise ValueError("k_keep must not exceed k_run")
        return self


class SearchBP(StrictModel):
    """SEARCH-BP-2.1 native service with an optional direct OSD-0 fallback."""
    kind: Literal["search_bp"] = "search_bp"
    profile: Literal["search_bp"] = SEARCH_BP_PROFILE
    name: Literal["search_bp"] = "search_bp"
    enabled: Annotated[bool, Field(strict=True)] = True
    algorithm_version: Literal["SEARCH-BP-2.1"]
    osd_fallback: Annotated[bool, Field(strict=True)] = True
    search: SearchBPSearch = SearchBPSearch()
    bp: SearchBPBP = SearchBPBP()
    admission: SearchBPAdmission = SearchBPAdmission()
    native_threads: Annotated[int, Field(strict=True, ge=1, le=1)] = 1


def _cycle_budgets(value: int | tuple[int, ...], cycles: int, field: str) -> tuple[int, ...]:
    """Resolve bounded scalars/lists without mutation; reject length/uint64 overflow."""
    result = (value,) * cycles if isinstance(value, int) else value
    if len(result) != cycles:
        raise ValueError(f"{field} must have exactly max_cycles entries")
    if sum(result) > 2**64 - 1:
        raise ValueError(f"{field} total exceeds uint64")
    return result


class Hybrid(StrictModel):
    """HSBP-ALG-1.0 configuration for the native hybrid decoder.

    Budgets are normalized into immutable tuples during validation and JSON lists
    on serialization, so scalar and equivalent list inputs have the same identity.
    max_cycles=0 resolves scalar budgets to empty lists and means direct OSD0.
    Profile-specific defaults never override explicitly supplied conflicting flags.
    """

    kind: Literal["hybrid_search_soft_bp_osd0"] = "hybrid_search_soft_bp_osd0"
    profile: Literal["hybrid_search_soft_ms_osd0_v1", "search_osd0_v1",
                     "hybrid_search_soft_ms_osd0_cold_v1"] = "hybrid_search_soft_ms_osd0_v1"
    name: str = "hybrid_search_soft_ms_osd0_v1"
    enabled: Annotated[bool, Field(strict=True)] = True
    algorithm_version: Literal["HSBP-ALG-1.0"] = "HSBP-ALG-1.0"
    search: HybridSearch = HybridSearch()
    bp: HybridBP = HybridBP()
    fallback: HybridFallback = HybridFallback()
    numerics: HybridNumerics = HybridNumerics()
    native_threads: Annotated[int, Field(strict=True, ge=1, le=1)] = 1

    @model_validator(mode="before")
    @classmethod
    def profile_defaults(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        profile = data.get("profile", HYBRID_PROFILES[0])
        data.setdefault("name", profile)
        defaults = ({"enabled": False, "warm_start": False, "iterations_per_cycle": 0}
                    if profile == "search_osd0_v1" else
                    {"warm_start": False} if profile == "hybrid_search_soft_ms_osd0_cold_v1" else {})
        if isinstance(data.get("bp", {}), dict):
            data["bp"] = {**defaults, **data.get("bp", {})}
        return data

    @model_validator(mode="after")
    def resolve(self) -> Self:
        cycles = self.search.max_cycles
        expansions = _cycle_budgets(self.search.expansions_per_cycle, cycles, "expansions_per_cycle")
        iterations = _cycle_budgets(self.bp.iterations_per_cycle, cycles, "iterations_per_cycle")
        expected = {HYBRID_PROFILES[0]: (True, True), "search_osd0_v1": (False, False),
                    "hybrid_search_soft_ms_osd0_cold_v1": (True, False)}[self.profile]
        if (self.bp.enabled, self.bp.warm_start) != expected:
            raise ValueError("BP enabled/warm_start flags conflict with the explicit hybrid profile")
        if self.bp.enabled and any(t == 0 for t in iterations):
            raise ValueError("enabled BP requires positive iterations_per_cycle")
        if not self.bp.enabled and any(iterations):
            raise ValueError("disabled BP requires zero iterations_per_cycle")
        object.__setattr__(self, "search", self.search.model_copy(update={"expansions_per_cycle": expansions}))
        object.__setattr__(self, "bp", self.bp.model_copy(update={"iterations_per_cycle": iterations}))
        return self


def require_available_decoder(profile: str) -> None:
    """Reject unknown profiles without numerical imports or mutation (ValueError)."""
    if profile == SEARCH_BP_PROFILE:
        return
    if profile in HYBRID_PROFILES:
        return
    if profile not in ("screened_reference", "bposd_ms30_cs10", "bposd_ms30_cs0", "beam8", "beam32"):
        raise ValueError(f"unsupported decoder profile: {profile}")


class Beam(StrictModel):
    profile: Literal["beam8", "beam32"] = "beam8"
    name: str = "beam8"
    enabled: bool = True
    max_rounds: Positive = 10
    beam_width: Positive = 8
    num_results: Literal[1] = 1
    initial_iters: Positive = 30
    iters_per_round: Positive = 20

    @model_validator(mode="before")
    @classmethod
    def defaults(cls, value):
        if isinstance(value, dict) and value.get("profile") == "beam32":
            return {"name": "beam32", "beam_width": 32, "initial_iters": 40,
                    "iters_per_round": 30, "enabled": False, **value}
        return value


Decoder = Annotated[Screened | Bposd | Bposd0 | Beam | Hybrid | SearchBP, Field(discriminator="profile")]


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


class ParquetOutput(StrictModel):
    compression: Literal["zstd", "snappy", "none"] = "zstd"
    compression_level: Annotated[int, Field(strict=True, ge=1, le=22)] = 3
    shots_per_flush: Positive = 1024


class SearchBPOutput(StrictModel):
    """Six-column per-condition result contract; no telemetry or raw samples."""
    root: Path = Path("../assets/runs")
    layout: Literal["minimal_results"] = "minimal_results"
    data_schema_version: Literal["search_bp_results/2"] = "search_bp_results/2"
    parquet: ParquetOutput = ParquetOutput()

    @property
    def compression(self) -> str:
        return self.parquet.compression

    @property
    def retain_traces(self) -> bool:
        return False

    @property
    def retain_corrections(self) -> bool:
        return False


class Analysis(StrictModel):
    """Legacy analysis settings type, excluded from simulation ``Config``.

    Historical consumers import this symbol directly.  Current saved-data
    analysis owns and validates its settings in ``analysis.config``; this class
    is not a simulation field, is not path-resolved by ``load_config``, and never
    enters a resolved run configuration or its identity.
    """

    bootstrap_seed: Nonnegative = 20260921
    bootstrap_count: Positive = 2000
    bootstrap_unit: Literal["shot", "batch"] = "shot"
    accuracy_margin_absolute: Annotated[float, Field(ge=0, le=1)] | None = None
    confidence: Annotated[float, Field(gt=0, lt=1)] = 0.95
    quantiles: tuple[Annotated[float, Field(ge=0, le=1)], ...] = (.5, .9, .95, .99, .999)
    plots: tuple[Literal["failure_rate", "cpu_ecdf", "wall_ecdf", "cpu_survival", "wall_survival"], ...] = ("failure_rate", "cpu_ecdf", "wall_ecdf")
    stratify_timing: bool = False
    min_expected_tail_count: Positive = 10
    input: Path = Path("../assets/runs")
    output: Path = Path("../assets/analysis")

    @model_validator(mode="after")
    def check(self) -> Self:
        if len(set(self.plots)) != len(self.plots) or len(set(self.quantiles)) != len(self.quantiles):
            raise ValueError("analysis plots and requested quantiles must be unique")
        return self


class Config(StrictModel):
    config_schema_version: Literal["search_bp_config/4"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    experiment: Experiment = Experiment()
    noise: Noise
    circuit: Circuit = Circuit()
    dem: Dem = Dem()
    decoders: tuple[Decoder, ...] = (Screened(), Bposd(), Beam())
    sampling: Sampling = Sampling()
    execution: Execution = Execution()
    timing: Timing = Timing()
    output: Output | SearchBPOutput = Output()

    @model_validator(mode="after")
    def check(self) -> Self:
        if self.timing.mode == "isolated_latency" and self.execution.workers != 1:
            raise ValueError("isolated_latency requires exactly one worker")
        names = [d.name for d in self.decoders]
        if len(set(names)) != len(names) or not any(d.enabled for d in self.decoders):
            raise ValueError("decoder names must be unique, with at least one enabled")
        has_search_bp = any(isinstance(d, SearchBP) for d in self.decoders)
        if has_search_bp and not isinstance(self.output, SearchBPOutput):
            raise ValueError("search_bp requires minimal_results output")
        if has_search_bp and self.config_schema_version != "search_bp_config/4":
            raise ValueError("search_bp requires config_schema_version: search_bp_config/4")
        if has_search_bp and self.timing.profiling != "none":
            raise ValueError("search_bp does not emit phase profiling")
        return self

    def resolved(self) -> dict:
        """Return detached JSON-safe settings with expanded rates; no mutation."""
        data = self.model_dump(mode="json")
        if self.config_schema_version is not None:
            data["config_schema_version"] = self.config_schema_version
        data["noise"]["expanded_rates"] = list(self.noise.expanded_rates)
        data["experiment"]["instances"] = [
            {"family": c.family, "distance": d, "rounds": c.rounds or d,
             "round_override": c.rounds is not None}
            for c in self.experiment.codes for d in c.distances]
        for decoder in data["decoders"]:
            if decoder["profile"] in ("beam8", "beam32"):
                decoder["implementation_properties"] = {
                    "bp_method": "upstream_min_sum", "hard_decision": "L<=0",
                    "branch_degree_filter": "skip columns with degree <=2",
                    "message_clip": "no configurable finite clip",
                    "tie_breaking": "upstream strict comparisons and (score,storage_index) priority queue",
                    "native_threads": 1,
                }
            elif decoder["profile"] in ("bposd_ms30_cs10", "bposd_ms30_cs0"):
                decoder["implementation_properties"] = {
                    "hard_decision": "upstream L<=0", "error_channel_type": "list",
                    "converge_flag": "BP stage only; validate correction after OSD",
                }

        return data


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
    if config.config_schema_version is not None:
        data["config_schema_version"] = config.config_schema_version
    for group, fields in {"circuit": ("cache",), "output": ("root",)}.items():
        for field in fields:
            data[group][field] = (path.parent / data[group][field]).resolve()
    return Config.model_validate(data)
