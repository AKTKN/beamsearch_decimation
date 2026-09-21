"""Strict saved-data analysis settings, independent of decoder construction."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from qec_bp_benchmark.config import Analysis, _UniqueLoader, load_config


class AnalysisConfig(BaseModel):
    """Immutable analysis-only YAML envelope; paths belong to the YAML directory."""

    model_config = ConfigDict(extra='forbid', frozen=True)
    analysis: Analysis = Analysis()


def load_analysis_config(path: str | Path) -> AnalysisConfig:
    """Load analysis-only YAML, or a fully validated existing benchmark YAML.

    Returns owned immutable settings with absolute input/output paths. Benchmark
    files retain full strict validation for compatibility, but their simulation
    and affinity settings are never applied to the analysis process. New analysis
    configurations need no noise, decoder, sampling, or native build settings.
    Raises OSError, yaml.YAMLError, or ValueError for invalid files/settings.
    """
    path = Path(path).resolve()
    data = yaml.load(path.read_text(), Loader=_UniqueLoader)
    if isinstance(data, dict) and any(k != 'analysis' for k in data):
        return AnalysisConfig(analysis=load_config(path).analysis)
    config = AnalysisConfig.model_validate(data)
    settings = config.analysis.model_dump()
    for field in ('input', 'output'):
        settings[field] = (path.parent / settings[field]).resolve()
    return AnalysisConfig(analysis=Analysis.model_validate(settings))
