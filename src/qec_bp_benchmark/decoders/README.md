# Active decoder service

`DecoderAdapter(problem, config).decode(syndrome)` owns one prepared upstream
baseline and takes a binary selected-detector syndrome of shape `(m,)`. The
service sees no sampled logical truth. It copies the input, calls the pinned
upstream decoder, checks the correction against original H, predicts all A
observables and computes physical cost. Returned correction `(n,)` and
prediction `(k,)` arrays are caller-owned, or null on failure. The adapter is
worker-owned and not reentrant.

The active profiles are `beam8`, `bposd`, and `relay_bp`. Beam8 retains its upstream width-8
search decisions. The upstream local Beam patch only counts completed BP
iterations across all initial and masked paths and exposes
`total_iterations`; its old `iter` remains the last path count. BP-OSD uses
upstream parallel minimum-sum with maximum 30 iterations by default, scale 1,
OSD_CS and a configurable nonnegative `osd_order` (default 10). Its BP `.iter`
is exact for a nonzero syndrome; the zero-syndrome shortcut counts zero.
Relay uses pinned Apache-2.0 `relay_bp.RelayDecoderF64`, the same canonical H
and binary64 mechanism probabilities as the other baselines, and its single-shot
`decode_detailed` result. `DecodeResult.iterations` counts the initial BP leg
and all executed relay legs, including unsuccessful ones. The adapter uses
`DecodeResult.success` as the upstream declaration, then checks original H
itself. Seeded draws follow upstream per-instance RNG state in worker shot order.

`DecodeResult.total_iterations` and `counters['total_iterations']` expose exact
counts for all three comparison decoders; `declared_failure` is truth-free. The
worker times the full service, including validation and prediction. AF-BP and
qDither are not registered in this adapter yet. Historical decoder-service source
is preserved at `../legacy/decimation/decoder_service.py`; its native project
sources are excluded from active CMake and its profiles from active config.
