#ifndef QEC_HYBRID_MODEL_HPP
#define QEC_HYBRID_MODEL_HPP
#include "hybrid_graph.hpp"
#include <numeric>
namespace qec::hybrid {
using ldpc::hybrid::Bits; using ldpc::hybrid::Reals; using ldpc::hybrid::Rows;
using ldpc::hybrid::Graph; using ldpc::hybrid::binary; using ldpc::hybrid::finite;
using Key=std::vector<std::pair<int,uint8_t>>;
using Packed=std::vector<uint64_t>;
inline bool bit(const Packed& v,int i) {return (v[size_t(i)/64]>>(i%64))&1;}
inline void flip(Packed& v,int i) {v[size_t(i)/64]^=uint64_t(1)<<(i%64);}
inline uint64_t weight(const Packed& v) {uint64_t count=0; for(auto x:v) count+=__builtin_popcountll(x); return count;}
struct Model {
    std::shared_ptr<const Graph> graph;
    Rows observables,ordered;
    Bits channel_decision;
    Model(const Rows& rows,int n,const Reals& probabilities,const Rows& a):
        graph(std::make_shared<Graph>(rows,n,probabilities)),observables(a),ordered(rows) {
        for(double w:graph->weights) channel_decision.push_back(w<=0);
        for(const auto& r:a) {
            if(!std::is_sorted(r.begin(),r.end())||std::adjacent_find(r.begin(),r.end())!=r.end())
                throw std::invalid_argument("observable rows must be sorted unique indices");
            for(int i:r) if(i<0||i>=n) throw std::invalid_argument("observable column outside model");
        }
        for(auto& row:ordered) std::sort(row.begin(),row.end(),[&](int i,int j){
            return std::pair<double,int>{graph->weights[i],i}<std::pair<double,int>{graph->weights[j],j};});
    }
    Bits predict(const Bits& e) const {
        Bits out(observables.size(),0);
        for(size_t a=0;a<observables.size();++a) for(int i:observables[a]) out[a]^=e[i];
        return out;
    }
    double cost(const Bits& e) const {double cost=0; for(int i=0;i<graph->n;++i) if(e[i]) cost=finite(cost+graph->weights[i]); return cost;}
};
struct Settings {
    int max_depth=2;
    std::vector<uint64_t> expansions{8,8,8};
    std::vector<int> iterations{6,6,6};
    uint64_t max_generated_nodes=4096;
    int64_t prefix_cpu_budget_ns=0; // zero is the native representation of null
    double alpha=1,clip=25,margin=8;
    bool bp_enabled=true,warm=true;
    void validate() const {
        if(max_depth<0||expansions.size()>65536||iterations.size()!=expansions.size()||!max_generated_nodes||prefix_cpu_budget_ns<0)
            throw std::invalid_argument("invalid hybrid work/resource budgets");
        uint64_t total=0;
        for(size_t c=0;c<expansions.size();++c) {
            if(expansions[c]>UINT64_MAX-total) throw std::invalid_argument("expansion sum overflows uint64");
            total+=expansions[c];
            if(iterations[c]<0 || (bp_enabled ? iterations[c]==0 : iterations[c]!=0))
                throw std::invalid_argument("iteration budgets conflict with BP enablement");
        }
        if(!std::isfinite(alpha)||alpha<=0||alpha>1||!std::isfinite(clip)||clip<=0||!std::isfinite(margin)||margin<=0)
            throw std::invalid_argument("invalid finite min-sum parameters");
        if(!bp_enabled && warm) throw std::invalid_argument("disabled BP cannot request warm continuation");
    }
};
}
#endif
