"""Verified paired-run loading, block uncertainty, timing distributions and reports."""
from .io import RunData,discover_runs,load_run,read_manifest,select_records
from .statistics import aggregate_failures,aggregate_timings,empirical_distribution,timing_statistics,wilson_interval
from .report import create_report
from .config import AnalysisConfig, load_analysis_config
from .runtime import analysis_runtime

__all__=['RunData','discover_runs','load_run','read_manifest','select_records','aggregate_failures',
         'aggregate_timings','empirical_distribution','timing_statistics','wilson_interval','create_report']

from .hybrid import stage_statistics,paired_rows,summarize_pair,paired_statistics
__all__ += ['stage_statistics','paired_rows','summarize_pair','paired_statistics']
__all__ += ['AnalysisConfig', 'load_analysis_config', 'analysis_runtime']
