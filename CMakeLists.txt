cmake_minimum_required(VERSION 3.18)
project(qec_bp_benchmark LANGUAGES NONE)

# Stage 1 packages only the pinned external baselines. Historical project-native
# decimation sources remain in the repository but are excluded from this build.
