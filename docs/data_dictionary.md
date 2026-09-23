# Active result fields

See [minimal simulation output](simulation_output.md) for the six-field
`search_bp_results/2` contract. The five-field SEARCH-BP-2.0 contract is preserved
under [legacy/search_bp_v2](legacy/search_bp_v2/README.md). The old 14-dataset dictionary is preserved in
[legacy/search_bp_v1](legacy/search_bp_v1/data_dictionary.md).

LPM-DP-BP-1.0 writes `lpm_dp_results/1`: nonnull `shot_id`, `decoder_name`,
`logical_error`, `latency_ns` and exact `osd_called`. It contains no
`correction_by_search` or other decoder telemetry. See
[lpm_dp_stage4.md](lpm_dp_stage4.md).
