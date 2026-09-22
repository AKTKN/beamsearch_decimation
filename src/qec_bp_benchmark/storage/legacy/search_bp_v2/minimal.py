"""Historical five-field SEARCH-BP-2.0 schema; never used for new writes."""

import pyarrow as pa

SCHEMA_VERSION = "search_bp_results/1"
SCHEMA = pa.schema([
    pa.field("shot_id", pa.string(), nullable=False),
    pa.field("decoder_name", pa.string(), nullable=False),
    pa.field("logical_error", pa.bool_(), nullable=False),
    pa.field("latency_ns", pa.int64(), nullable=False),
    pa.field("osd_called", pa.bool_(), nullable=True),
], metadata={b"qec_schema": SCHEMA_VERSION.encode()})
