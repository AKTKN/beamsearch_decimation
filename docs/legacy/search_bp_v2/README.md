# SEARCH-BP-2.0 legacy contract

The historical active contract had an unconditional single OSD-0 fallback and a
five-field `search_bp_results/1` row without `correction_by_search`. Existing run
directories remain readable through the read-only legacy schema. They cannot
retroactively distinguish direct search corrections from BP corrections.

SEARCH-BP-2.1 supersedes it with `osd_fallback`, an exact per-shot
`correction_by_search` flag, `search_bp_config/4`, and `search_bp_results/2`.
