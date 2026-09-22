"""Minimal plotting API for the current simulation result layout."""
from .benchmark_plots import (
    REVTEX_COLUMN_SIZE,
    REVTEX_DOUBLE_COLUMN_WIDTH,
    decoder_event_rate_table,
    plot_decode_time_histogram,
    plot_logical_error_rate,
    plot_mean_decode_time,
)
from .config import AnalysisConfig, load_analysis_config
from .statistics import timing_statistics, wilson_interval

__all__ = [
    "REVTEX_COLUMN_SIZE",
    "REVTEX_DOUBLE_COLUMN_WIDTH",
    "decoder_event_rate_table",
    "plot_decode_time_histogram",
    "plot_logical_error_rate",
    "plot_mean_decode_time",
    "AnalysisConfig",
    "load_analysis_config",
    "timing_statistics",
    "wilson_interval",
]
