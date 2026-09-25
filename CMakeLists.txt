cmake_minimum_required(VERSION 3.18)
project(qec_bp_benchmark LANGUAGES CXX)

# Only the standalone AF-BP service is built. Historical project-native
# decimation sources remain excluded from this target and active registration.
find_package(pybind11 CONFIG REQUIRED)
pybind11_add_module(_af_bp_service src/af_bp_core/bindings.cpp)
target_compile_features(_af_bp_service PRIVATE cxx_std_17)
target_compile_options(_af_bp_service PRIVATE -O3 -fno-fast-math -ffp-contract=off -Wall -Wextra)
target_include_directories(_af_bp_service PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/src/af_bp_core
    ${CMAKE_CURRENT_SOURCE_DIR}/external_lib/ldpc/src_cpp)

set(AF_BP_SERVICE_SOURCE_FILES
    src/af_bp_core/graph.hpp
    src/af_bp_core/decoder.hpp
    src/af_bp_core/bindings.cpp
    external_lib/ldpc/src_cpp/af_bp.hpp
    CMakeLists.txt)
set(AF_BP_SERVICE_DIGEST_INPUT "")
foreach(source IN LISTS AF_BP_SERVICE_SOURCE_FILES)
    file(SHA256 "${CMAKE_CURRENT_SOURCE_DIR}/${source}" source_sha)
    string(APPEND AF_BP_SERVICE_DIGEST_INPUT "${source_sha}")
endforeach()
string(SHA256 AF_BP_SERVICE_SOURCE_HASH "${AF_BP_SERVICE_DIGEST_INPUT}")
target_compile_definitions(_af_bp_service PRIVATE
    AF_BP_SERVICE_SOURCE_HASH="${AF_BP_SERVICE_SOURCE_HASH}")
install(TARGETS _af_bp_service LIBRARY DESTINATION qec_bp_benchmark)
