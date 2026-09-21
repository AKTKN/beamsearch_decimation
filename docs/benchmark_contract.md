# Resolved benchmark contract

The normative inputs are the complete staged prompt contract (Sections A–J) and
bp_decimation_screening_specification.md, copied byte-for-byte in this directory.
This document records implementation choices and guides later stages.

The scientific experiment is offline logical Z memory. Defaults: rotated surface
codes d=5,7,9 with R=d, and BB [[72,12,6]] with six extraction rounds and all twelve
independent logical Z observables. An explicit round override is retained as a
separate experiment even if its value equals d. Published BB distance is six;
no claim of circuit distance follows from algebraic checks. BB uses qLDPC's
edge-coloring extraction strategy, not the original optimized seven-layer schedule.
Preparation and destructive readout are noisy, without extra ideal closing cycles.
Both physical extraction sectors remain present. Only verified Z-check detector
records enter the decoder. X components of X and Y faults can flip Z memory.

Noise is applied exactly once to noiseless templates using qLDPC NoiseModel: separate
YAML multipliers for one-qubit depolarization, two-qubit depolarization, idle
depolarization, wrong-state resets and flipped measurement outcomes. Idle noise is
explicitly enabled. Eligible qubits and moment boundaries are persisted. The same
exact physical circuit bytes are shared by all decoders. Only circuit sampling is
valid for benchmarks; DEM sampling is confined to labeled converter tests.

The canonical problem is H e=s, predicted observables A e, with mechanism priors
from an undecomposed DEM, not the physical sweep parameter. Retain hyperedges,
separator correlations, logical-only mechanisms and distinct instructions. Expand
repeat/offset semantics and XOR supports. Remove zero-probability instructions with
a reconstruction map; reject probabilities above one half. Gauge approximations and
column merging are unsupported. Disjoint-error approximation is off unless explicitly
requested in YAML and recorded. Zero-column noiseless problems are legal.

Screened reference: binary64 flooding sum-product, exact specification clipping,
iteration-zero check, L<0 ties, native posterior history and structural fixation.
Native BP lives in the explicit ldpc fork interface; screening/search lives in
project C++. No warm starts, damping, adaptive pools or fallback. BP-OSD starts with
minimum_sum, parallel schedule, 30 iterations, factor 1, OSD_CS order 10. Beam uses
the published native min-sum implementation with the five supported parameters.
These compare complete configured decoders, not screening alone.

Every physical batch is sampled once and supplied to all decoders. Truth is stored
separately. Seeds depend only on scientific instance, immutable sampling plan,
stream tag and batch index. Worker count, decoder order and output path cannot
change physical samples. Stim version, call shape and platform constrain replay;
raw records are retained. Warmup uses a separate stream and no measured rows.

For each shot let a indicate declared failure or invalid correction. Block failure
is a OR any mismatch of predicted and actual observables. Report total block failure,
decoding failure, valid-output mismatch contribution and conditional mismatch with
its valid-output denominator. Preserve per-observable results. Never divide BB block
failure by twelve, multiply one sector by two, or interpret block time/R as measured
online round latency. Programming exceptions fail the task, preserve traceback and
leave the experiment incomplete.

Timing encloses complete decode service: reset, adaptation, BP, screening, residual
work, correction reconstruction, syndrome validation and prediction. Exclude setup,
sampling, queues, I/O and plotting; record setup separately. Measure process CPU and
wall integer nanoseconds for every shot, failures included. Throughput uses spawn
workers (default four), one native/BLAS thread, bounded tasks and concurrent-load
labels. Isolated latency requires one worker and one native thread. Decoder order
is deterministic cyclic. No timer-overhead subtraction or hidden phase work.

Separate scientific, decoder, sampling-plan and run identities. Scientific identities
include circuit/DEM/matrix/mapping hashes and exact float values. Run storage uses
exclusive timestamped UTC directories, versioned long-form Arrow tables, one physical
sample row per shot, all observables, explicit nulls, and atomic paired batch shards
with checksums/counts. A run is complete only after all tasks/decoders are present.
Source revisions, patches/source bytes, build paths/flags, locks and environment are
retained. No resume support is claimed. These storage/runner requirements are implemented by Stage 5.

Analysis sums counts, uses Wilson intervals, retains shot dependence between BB
observables, and separates timing modes. Smoke checks establish software behavior,
not performance advantage or a production physical-rate choice.
