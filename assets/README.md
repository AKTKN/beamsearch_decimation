# assets

Mutable experiment outputs belong here in timestamped run/report directories.
Implementation smoke simulations do not constitute a production campaign.

The accepted Stage 5 smoke, isolated and replay outputs are listed in
../docs/test_results/stage_4_5_summary.json. Each contains committed paired Parquet,
original/resolved config, exact scientific artifacts and source/environment archives.
Earlier development runs remain preserved. These small datasets validate software;
they do not support a decoder-performance claim.

Final Stage 6–7 output paths are indexed in ../docs/test_results/stage_6_7_summary.json.
analysis/ contains checksummed count/timing JSON and standalone PNG/PDF reports;
notebook/ contains executed consumer notebooks. acceptance/ preserves an independent
source workspace, fresh search_decimation prefix, full source-build/test logs and
its own complete run/report/notebook outputs. Original run snapshots remain immutable.
