"""Strict saved-data analysis settings, independent of simulation configuration."""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


Positive = Annotated[int, Field(strict=True, gt=0)]
Nonnegative = Annotated[int, Field(strict=True, ge=0)]


class Analysis(BaseModel):
    """Settings owned exclusively by saved-data analysis."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_default=True, allow_inf_nan=False
    )
    bootstrap_seed: Nonnegative = 20260921
    bootstrap_count: Positive = 2000
    bootstrap_unit: Literal["shot", "batch"] = "shot"
    accuracy_margin_absolute: Annotated[float, Field(ge=0, le=1)] | None = None
    confidence: Annotated[float, Field(gt=0, lt=1)] = 0.95
    quantiles: tuple[Annotated[float, Field(ge=0, le=1)], ...] = (
        .5, .9, .95, .99, .999
    )
    plots: tuple[
        Literal["failure_rate", "cpu_ecdf", "wall_ecdf", "cpu_survival", "wall_survival"],
        ...,
    ] = ("failure_rate", "cpu_ecdf", "wall_ecdf")
    stratify_timing: bool = False
    min_expected_tail_count: Positive = 10
    input: Path = Path("../assets/runs")
    output: Path = Path("../assets/analysis")

    @model_validator(mode="after")
    def check(self) -> Self:
        if len(set(self.plots)) != len(self.plots) or len(set(self.quantiles)) != len(self.quantiles):
            raise ValueError("analysis plots and requested quantiles must be unique")
        return self


class AnalysisConfig(BaseModel):
    """Immutable analysis-only YAML envelope; paths belong to the YAML directory."""

    model_config = ConfigDict(extra='forbid', frozen=True)
    analysis: Analysis = Analysis()


class _UniqueLoader(yaml.SafeLoader):
    """Analysis-owned safe YAML loader that rejects duplicate mapping keys."""


def _mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError(f"duplicate YAML key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def load_analysis_config(path: str | Path) -> AnalysisConfig:
    """Load an analysis-only YAML document.

    Returns owned immutable settings with absolute input/output paths. Simulation
    configuration is intentionally neither accepted nor imported here. Raises
    OSError, yaml.YAMLError, or ValueError for invalid files/settings.
    """
    path = Path(path).resolve()
    data = yaml.load(path.read_text(), Loader=_UniqueLoader)
    config = AnalysisConfig.model_validate(data)
    settings = config.analysis.model_dump()
    for field in ('input', 'output'):
        settings[field] = (path.parent / settings[field]).resolve()
    return AnalysisConfig(analysis=Analysis.model_validate(settings))
