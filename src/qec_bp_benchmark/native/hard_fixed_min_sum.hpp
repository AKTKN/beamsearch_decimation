#ifndef QEC_HARD_FIXED_MIN_SUM_HPP
#define QEC_HARD_FIXED_MIN_SUM_HPP
#include "hybrid_model.hpp"
#include <functional>

namespace qec::search_bp {
using ldpc::hybrid::Bits;using ldpc::hybrid::Graph;using ldpc::hybrid::Reals;using qec::hybrid::Key;

struct HardSnapshot {
    Reals sums,llrs,q,z;
    Bits decision,syndrome,residual;
    std::vector<int8_t> fixed;
    uint64_t iterations=0,model_id=0,shot_id=0,numeric_id=0;
};

struct HardAdvance {bool valid=false,cap_hit=false;uint64_t iterations=0;};

// Stateful parallel min-sum on the graph induced by unfixed variables. Fixed
// columns never participate in check or variable updates; fixed ones are XORed
// into the residual syndrome. Buffers retain original edge IDs so an ancestor's
// active variable-to-check messages can seed a descendant deterministically.
class HardFixedMinSumSession {
    std::shared_ptr<const Graph> graph_;
    double alpha_;
    uint64_t shot_id_=0,numeric_id_=14695981039346656037ULL;
    bool ready_=false;
    HardSnapshot state_;

    static double bounded_add(double a,double b) {
        constexpr double top=std::numeric_limits<double>::max();
        if(b>0&&a>top-b)return top;
        if(b<0&&a<-top-b)return -top;
        return a+b;
    }
    bool active(size_t edge) const {return state_.fixed[size_t(graph_->col[edge])]<0;}
    void apply_pattern(const Key& pattern) {
        state_.fixed.assign(size_t(graph_->n),-1);state_.residual=state_.syndrome;
        int previous=-1;
        for(auto [i,b]:pattern) {
            if(i<=previous||i<0||i>=graph_->n||b>1) throw std::invalid_argument("hard pattern must be sorted, unique, in-range, and binary");
            previous=i;state_.fixed[size_t(i)]=int8_t(b);state_.decision[size_t(i)]=b;
            if(b)for(size_t j=graph_->cp[size_t(i)];j<graph_->cp[size_t(i)+1];++j)
                state_.residual[size_t(graph_->row[graph_->ce[j]])]^=1;
        }
    }
    void initialize_decision() {
        for(int i=0;i<graph_->n;++i) {
            if(state_.fixed[size_t(i)]>=0) {state_.decision[size_t(i)]=uint8_t(state_.fixed[size_t(i)]);
                state_.llrs[size_t(i)]=state_.fixed[size_t(i)]?-graph_->weights[size_t(i)]:graph_->weights[size_t(i)];
                state_.sums[size_t(i)]=state_.llrs[size_t(i)];continue;}
            state_.sums[size_t(i)]=graph_->weights[size_t(i)];state_.llrs[size_t(i)]=state_.sums[size_t(i)];
            state_.decision[size_t(i)]=state_.llrs[size_t(i)]<=0;
        }
    }
    bool local_contradiction() const {
        for(int a=0;a<graph_->m;++a) {
            bool any=false;for(size_t e=graph_->rp[size_t(a)];e<graph_->rp[size_t(a)+1];++e)any|=active(e);
            if(!any&&state_.residual[size_t(a)])return true;
        }
        return false;
    }
    void variables() {
        for(int i=0;i<graph_->n;++i) {
            if(state_.fixed[size_t(i)]>=0) {
                state_.decision[size_t(i)]=uint8_t(state_.fixed[size_t(i)]);
                state_.llrs[size_t(i)]=state_.fixed[size_t(i)]?-graph_->weights[size_t(i)]:graph_->weights[size_t(i)];
                state_.sums[size_t(i)]=state_.llrs[size_t(i)];continue;
            }
            double sum=graph_->weights[size_t(i)];
            for(size_t j=graph_->cp[size_t(i)];j<graph_->cp[size_t(i)+1];++j)sum=bounded_add(sum,state_.z[graph_->ce[j]]);
            state_.sums[size_t(i)]=state_.llrs[size_t(i)]=sum;state_.decision[size_t(i)]=sum<=0;
            for(size_t j=graph_->cp[size_t(i)];j<graph_->cp[size_t(i)+1];++j) {
                size_t e=graph_->ce[j];state_.q[e]=bounded_add(sum,-state_.z[e]);
            }
        }
    }
public:
    HardFixedMinSumSession(std::shared_ptr<const Graph> graph,double alpha=1):graph_(std::move(graph)),alpha_(alpha) {
        if(!graph_||!std::isfinite(alpha_)||alpha_<=0||alpha_>1)throw std::invalid_argument("min-sum scaling must be finite and in (0,1]");
        const size_t n=size_t(graph_->n),edges=graph_->col.size();
        state_.sums.resize(n);state_.llrs.resize(n);state_.decision.resize(n);state_.fixed.resize(n);
        state_.q.resize(edges);state_.z.resize(edges);state_.residual.resize(size_t(graph_->m));
        uint64_t bits=0;std::memcpy(&bits,&alpha_,sizeof bits);for(int k=0;k<8;++k){numeric_id_^=(bits>>(8*k))&255;numeric_id_*=1099511628211ULL;}
    }
    void reset(const Bits& syndrome,const Key& pattern,uint64_t shot_id) {
        ready_=false;ldpc::hybrid::binary(syndrome,size_t(graph_->m));state_.syndrome=syndrome;shot_id_=shot_id;
        state_.iterations=0;std::fill(state_.q.begin(),state_.q.end(),0);std::fill(state_.z.begin(),state_.z.end(),0);
        apply_pattern(pattern);
        for(size_t e=0;e<state_.q.size();++e)if(active(e))state_.q[e]=graph_->weights[size_t(graph_->col[e])];
        initialize_decision();ready_=true;
    }
    void restore(const HardSnapshot& source,uint64_t shot_id) {
        ready_=false;
        if(source.model_id!=graph_->model_id||source.numeric_id!=numeric_id_||source.shot_id!=shot_id)
            throw std::invalid_argument("snapshot model, numeric policy, or shot identity mismatch");
        ldpc::hybrid::binary(source.syndrome,size_t(graph_->m));ldpc::hybrid::binary(source.decision,size_t(graph_->n));
        if(source.fixed.size()!=size_t(graph_->n)||source.sums.size()!=size_t(graph_->n)||source.llrs.size()!=size_t(graph_->n)||
           source.residual.size()!=size_t(graph_->m)||source.q.size()!=graph_->col.size()||source.z.size()!=graph_->col.size())
            throw std::invalid_argument("snapshot buffer shape mismatch");
        ldpc::hybrid::binary(source.residual,size_t(graph_->m));
        if(std::any_of(source.fixed.begin(),source.fixed.end(),[](int8_t x){return x < -1||x > 1;})||
           std::any_of(source.sums.begin(),source.sums.end(),[](double x){return !std::isfinite(x);})||
           std::any_of(source.llrs.begin(),source.llrs.end(),[](double x){return !std::isfinite(x);})||
           std::any_of(source.q.begin(),source.q.end(),[](double x){return !std::isfinite(x);})||
           std::any_of(source.z.begin(),source.z.end(),[](double x){return !std::isfinite(x);}))
            throw std::invalid_argument("snapshot contains invalid hard BP state");
        state_=source;shot_id_=shot_id;ready_=true;
    }
    void inherit(const HardSnapshot& source,const Key& pattern,uint64_t shot_id) {
        try {
            restore(source,shot_id);auto old_fixed=state_.fixed;auto old_q=state_.q;
            apply_pattern(pattern);
            for(size_t i=0;i<old_fixed.size();++i)if(old_fixed[i]>=0&&state_.fixed[i]!=old_fixed[i])
                throw std::invalid_argument("descendant hard pattern must preserve ancestor fixations");
            std::fill(state_.z.begin(),state_.z.end(),0);
            for(size_t e=0;e<state_.q.size();++e)state_.q[e]=active(e)?old_q[e]:0;
            initialize_decision();ready_=true;
        } catch(...) {ready_=false;throw;}
    }
    bool valid() const {return ready_&&!local_contradiction()&&graph_->valid(state_.decision,state_.syndrome);}
    HardAdvance advance(uint64_t count,const std::function<bool()>& cap={}) {
        if(!ready_)throw std::logic_error("hard BP reset required before iterations");
        HardAdvance out;out.valid=valid();
        if(local_contradiction())return out;
        for(uint64_t t=0;t<count&&!out.valid;++t) {
            if(cap&&cap()){out.cap_hit=true;break;}
            for(int a=0;a<graph_->m;++a) {
                double first=std::numeric_limits<double>::max(),second=first;size_t minimum=SIZE_MAX;bool sign=bool(state_.residual[size_t(a)]);
                for(size_t e=graph_->rp[size_t(a)];e<graph_->rp[size_t(a)+1];++e)if(active(e)) {
                    const double value=std::abs(state_.q[e]);sign^=state_.q[e]<=0;
                    if(value<first){second=first;first=value;minimum=e;}else if(value<second)second=value;
                }
                for(size_t e=graph_->rp[size_t(a)];e<graph_->rp[size_t(a)+1];++e) {
                    if(!active(e)){state_.z[e]=0;continue;}
                    const double magnitude=alpha_*(e==minimum?second:first);
                    state_.z[e]=(sign^(state_.q[e]<=0))?-magnitude:magnitude;
                }
            }
            variables();++state_.iterations;++out.iterations;out.valid=valid();
        }
        return out;
    }
    HardSnapshot snapshot() const {if(!ready_)throw std::logic_error("no hard BP state");auto out=state_;out.model_id=graph_->model_id;out.shot_id=shot_id_;out.numeric_id=numeric_id_;return out;}
    size_t snapshot_bytes() const {return 2*size_t(graph_->n)*sizeof(double)+2*graph_->col.size()*sizeof(double)+
        2*size_t(graph_->n)*sizeof(uint8_t)+2*size_t(graph_->m)*sizeof(uint8_t)+4*sizeof(uint64_t);}
    const Reals& llrs() const {return state_.llrs;}
    const Bits& decision() const {return state_.decision;}
};
}
#endif
