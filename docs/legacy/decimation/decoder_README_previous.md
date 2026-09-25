# Decoder services

`DecoderAdapter(problem, validated_config).decode(syndrome)` owns a prepared native
backend and returns `DecodeResult`. The input has only selected detectors. Logical
truth never enters this interface. Output correction/prediction/cost are null on
failure. Unexpected exceptions propagate. Canonical H/A/p remain unchanged; upstream
constructors receive a writable H copy because their sparse conversion mutates it.

Screened configuration exposes T0, Tpost, history_window, M, q, K and Lmax. All other
reference choices are fixed by the schema. q must not exceed min(M,n); an exactly
empty normalized problem is handled algebraically before calling native decoders.
BP-OSD exposes max_iter and osd_order with fixed minimum_sum/parallel/scale=1/OSD_CS.
Beam exposes exactly max_rounds, beam_width, num_results=1, initial_iters and
iters_per_round. Unknown settings fail validation before construction. Upstream
conventions are recorded by Config.resolved(), with no transplantation of kernels.

Native reference code cold-starts every initial/candidate call. Baselines reset
through their published decode methods; their zero-syndrome fast paths can leave
old iteration fields, so BP-OSD records known zero iterations there and beam's
unavailable aggregate iterations remain null. BP-OSD's converge flag is BP-only;
valid OSD outputs are accepted. An exhausted beam never yields a prediction.

Timing must wrap this entire Python service, including conversion, native graph
work, cost and parity validation, and A prediction. Setup/source verification and
constructor copies are outside per-shot timing. Native flooding describes message
update dependencies, not CPU threading. Each backend uses one native CPU thread.


Hybrid migration Stage 1: `Bposd0` (`bposd_ms30_cs0`) fixes OSD_CS order zero and
shares the unchanged upstream BP-OSD adapter; its BP runs normally before fallback.
This is not the future direct OSD-only bridge. The previous CS10 profile/order
configuration is preserved. Dispatch and implementation identity enumerate all
supported profiles and reject unknown kinds. All three hybrid/ablation profiles now call the complete native service, including
empty models. `DecodeResult.hybrid_summary` owns scalar counters/times. Call
`export_telemetry()` after timing and before reuse for owned phase/cycle records.
Per-node `diagnostics=True` is rejected; profiling collects compact events. Session
lifetimes and error/reset behavior are in docs/hybrid_native.md. No truth is passed
to the service. Historical v2 telemetry is described in docs/hybrid_data.md.

`SearchBP` is the strict SEARCH-BP-2.0 configuration. Its adapter verifies native
source identities, maps every setting to SearchBP2Settings, and calls
SearchBP2Decoder with syndrome only. No v1 fallback is permitted.
`DecodeResult.osd_called` is false for screened/beam and algebraic empty-model
paths, exact from the hybrid invocation flag, and exact for upstream BP-OSD from
its nonzero-syndrome BP-fallback branch. A zero-syndrome early return never uses
a stale upstream convergence flag. Native baseline algorithms are unchanged.
The active runner saves only this flag, logical error and full service latency
with shot/decoder keys. Telemetry export remains a historical hybrid API.

The complete Stage-4 native `SearchBP2Decoder` is integrated in Stage 5.
SEARCH-BP profiling/diagnostics are rejected; no event dictionaries are constructed.
The adapter independently validates H and predicts A within the service timing
boundary, and preserves the exact native OSD flag. See docs/search_bp_stage5.md.
