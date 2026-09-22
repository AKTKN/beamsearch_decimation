## SEARCH-BP-1.0

The active kind and profile are both `search_bp`. Nested
search/BP/stopping/fallback/numerics objects reject unknown keys and nonfinite
values. `search.expansions_per_cycle` is one scalar used in every cycle. There is
no `max_generated_nodes`: expanded search work is bounded only by
`max_cycles * expansions_per_cycle`, while each expanded Tanner-graph node may
generate all of its finite canonical children.
`bp.beam_width` controls both new pattern admission and retained BP states, while
`bp.max_iteration` is the fixed request for each candidate visit. There are no
`max_expansions`, `max_generated_nodes`, `admissions_per_cycle`,
`max_total_iterations`, soft-hint, LLR clip, or hard-decision-zero settings.
`max_cycles: 0` selects direct CS0.

Typed output requires `search_bp_config/2`, layout `typed_datasets` and data schema
`search_bp_parquet/2`. Validate without executing using
`python python_scripts/validate_config.py CONFIG`.
