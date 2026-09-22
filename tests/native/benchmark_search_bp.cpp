// Bounded decoder-only microbenchmark; no circuits, sampling or telemetry hooks.
// Build separately with -O3 -fno-fast-math -ffp-contract=off (optionally -pg).
#include "search_bp_decoder.hpp"
#include <chrono>
#include <iostream>
#include <random>

using namespace qec::search_bp2;
int main(int argc, char** argv) {
    const int repetitions = argc > 1 ? std::stoi(argv[1]) : 100;
    if (repetitions < 1 || repetitions > 10000) return 2;
    std::mt19937 rng(20260922);
    Rows h(64);
    for (auto& row : h) {
        while (row.size() < 8) {
            const int j = int(rng() % 128);
            if (std::find(row.begin(), row.end(), j) == row.end()) row.push_back(j);
        }
        std::sort(row.begin(), row.end());
    }
    // Deliberately inconsistent duplicate checks exercise full recursive cycles
    // and fallback; this is a synthetic stress case, not a physical noise model.
    h.back() = h.front();
    Reals p(128);
    for (size_t j = 0; j < p.size(); ++j) p[j] = .05 + .002 * (j % 64);
    DecoderSettings settings;
    settings.initial_iterations = settings.candidate_iterations = 4;
    settings.history_window = 2;
    std::vector<Bits> syndromes(16, Bits(h.size()));
    for (auto& s : syndromes) {
        for (auto& b : s) b = uint8_t(rng() % 2);
        s.back() = s.front() ^ 1;
    }
    for (const std::string policy : {"fixed_root", "refresh_descendant"}) {
        settings.local_variable_policy = policy;
        Decoder decoder(h, 128, p, {{0, 1}}, settings);
        uint64_t checksum = 1469598103934665603ULL;
        const auto hash = [&](const DecodeResult& result) {
            for (uint8_t b : result.correction) checksum = (checksum ^ b) * 1099511628211ULL;
            for (uint8_t b : result.prediction) checksum = (checksum ^ b) * 1099511628211ULL;
            checksum = (checksum ^ uint64_t(result.valid)) * 1099511628211ULL;
            checksum = (checksum ^ uint64_t(result.osd_called)) * 1099511628211ULL;
        };
        for (const auto& s : syndromes) hash(decoder.decode(s)); // untimed warmup
        const auto start = std::chrono::steady_clock::now();
        for (int i = 0; i < repetitions; ++i)
            for (const auto& s : syndromes) hash(decoder.decode(s));
        const auto end = std::chrono::steady_clock::now();
        std::cout << policy << ' ' << repetitions * syndromes.size() << ' '
                  << std::chrono::duration<double, std::nano>(end-start).count() /
                     (repetitions * syndromes.size()) << ' ' << checksum << '\n';
    }
}
