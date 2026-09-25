#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
mode=${1:?usage: check_af_bp_native.sh debug|asan|ubsan}
output="$root/assets/build/af-bp-final-$mode"
mkdir -p "$output"

flags=(-std=c++17 -O0 -g -UNDEBUG -Wall -Wextra -Werror -fno-fast-math -ffp-contract=off)
case "$mode" in
    debug) ;;
    asan) flags+=(-fsanitize=address -fno-omit-frame-pointer) ;;
    ubsan) flags+=(-fsanitize=undefined -fno-omit-frame-pointer) ;;
    *) echo "unknown mode: $mode" >&2; exit 2 ;;
esac

g++ "${flags[@]}" -I "$root/src" \
    "$root/tests/native/af_bp_graph_core_test.cpp" \
    -o "$output/af_bp_graph_core_test"
g++ "${flags[@]}" -I "$root/src/af_bp_core" -I "$root/external_lib/ldpc/src_cpp" \
    "$root/tests/native/af_bp_decoder_test.cpp" \
    -o "$output/af_bp_decoder_test"

export ASAN_OPTIONS=detect_leaks=1:halt_on_error=1
export UBSAN_OPTIONS=halt_on_error=1
"$output/af_bp_graph_core_test"
"$output/af_bp_decoder_test"
