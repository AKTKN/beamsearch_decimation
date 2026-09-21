# Immutable scientific artifacts

Use stage_1_3_validation_index.json to select the four final accepted smoke fixtures
for surface d=5,7,9 and BB72, all R=d and p=0.001. It records exact instance and
circuit/DEM/matrix/mapping hashes and distinguishes earlier development artifacts,
which remain unchanged. Repeated preparation reuses and verifies identical bytes.

Each instance preserves physical/noiseless/selected Stim circuits, undecomposed DEM,
CSC H/A arrays, priors, normalization and detector/observable maps, inventory,
source pins and a complete checksum manifest. load_problem verifies and reconstructs
canonical arrays. Mutable per-shot output tables belong under assets/, not here.
