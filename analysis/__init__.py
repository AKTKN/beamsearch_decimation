"""Verified paired-run loading, block uncertainty, timing distributions and reports."""
from .io import RunData,discover_runs,load_run,read_manifest,select_records
from .statistics import aggregate_failures,aggregate_timings,empirical_distribution,timing_statistics,wilson_interval
from .report import create_report

__all__=['RunData','discover_runs','load_run','read_manifest','select_records','aggregate_failures',
         'aggregate_timings','empirical_distribution','timing_statistics','wilson_interval','create_report']
