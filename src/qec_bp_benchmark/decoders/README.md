# Active decoder service

`DecoderAdapter(problem, config).decode(syndrome)` owns one prepared upstream
baseline and takes a binary selected-detector syndrome of shape `(m,)`. The
service sees no sampled logical truth. It copies the input, calls the pinned
upstream decoder, checks the correction against original H, predicts all A
observables and computes physical cost. Returned correction `(n,)` and
prediction `(k,)` arrays are caller-owned, or null on failure. The adapter is
worker-owned and not reentrant.

The active profiles are `beam8` and `bposd`. Beam8 retains its upstream width-8
search decisions. The upstream local Beam patch only counts completed BP
iterations across all initial and masked paths and exposes
`total_iterations`; its old `iter` remains the last path count. BP-OSD uses
upstream parallel minimum-sum with maximum 30 iterations by default, scale 1,
OSD_CS and a configurable nonnegative `osd_order` (default 10). Its BP `.iter`
is exact for a nonzero syndrome; the zero-syndrome shortcut counts zero.

`DecodeResult.counters['total_iterations']` is exact for both baselines. The
worker times the full service, including validation and prediction. AF-BP and
Relay-BP do not exist in this adapter yet. Historical decoder-service source
is preserved at `../legacy/decimation/decoder_service.py`; its native project
sources are excluded from active CMake and its profiles from active config.
