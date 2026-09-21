#include "hybrid_search.hpp"
#include <chrono>
#include <iostream>
#include <random>
using namespace qec::hybrid;
int main() {
    std::mt19937 random(128);Rows rows(80);Reals p(180,.1);
    for(int i=0;i<180;++i) for(int k=0;k<5;++k) rows[random()%80].push_back(i);
    for(auto& row:rows) {std::sort(row.begin(),row.end());row.erase(std::unique(row.begin(),row.end()),row.end());}
    auto model=std::make_shared<Model>(rows,180,p,Rows{});
    Settings cfg;cfg.max_depth=3;cfg.max_generated_nodes=4096;
    Bits s(80);for(auto& b:s) b=random()%2;
    for(bool reference:{true,false}) {
        SearchSession session(model,cfg,reference);uint64_t nodes=0;
        auto start=std::chrono::steady_clock::now();
        for(int run=0;run<100;++run) {session.reset(s);session.advance(24);nodes+=session.counts.generated;}
        auto elapsed=std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now()-start).count();
        std::cout<<(reference?"reference":"optimized")<<" microseconds="<<elapsed<<" generated="<<nodes<<" trials=100\n";
    }
}
