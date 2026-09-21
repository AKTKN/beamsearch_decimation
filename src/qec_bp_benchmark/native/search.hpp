#pragma once
#include "reference_bp.hpp"
#include <chrono>
#include <functional>
#include <map>
#include <numeric>
#include <queue>
#include <tuple>

namespace qec {
using ldpc::reference::Bits;
using ldpc::reference::Beliefs;
using ldpc::reference::ReferenceBp;
using ldpc::reference::Status;
struct Settings { int T0=30, Tpost=30, window=8, M=16, q=2, K=8; double limit=25; };
struct Pattern {
    Bits id; // flattened increasing (index, bit) pairs
    double g=0, h=0, f=0, rho=0;
    bool rejected=false;
};
inline bool better(const Pattern& a, const Pattern& b) {
    return std::tie(a.f,a.rho,a.id) < std::tie(b.f,b.rho,b.id);
}
struct Screen { Bits pool; std::vector<Pattern> retained; uint64_t enumerated=0, rejected=0; };
struct SearchResult {
    std::string status="NONCONVERGENCE";
    Bits correction, selected_pattern;
    double cost=0;
    bool valid=false, initial_success=false;
    int initial_iterations=0;
    uint64_t post_iterations=0, completions=0, successes=0;
    Screen screening;
    std::vector<Beliefs> history;
    std::vector<Bits> completion_decisions;
    std::vector<std::string> completion_statuses;
    std::map<std::string,int64_t> phases;
};
class ScreenedDecoder {
    std::vector<Bits> rows_;
    ReferenceBp bp_;
    Settings cfg_;
    void check_syndrome(const Bits& s) const {
        if(s.size()!=rows_.size()) throw std::invalid_argument("syndrome shape mismatch");
        for(int b:s) if(b!=0 && b!=1) throw std::invalid_argument("syndrome must be binary");
    }
    void check_reliability(const Beliefs& r) const {
        if(r.size()!=static_cast<size_t>(bp_.num_variables())) throw std::invalid_argument("reliability shape mismatch");
        for(double v:r) if(!std::isfinite(v)||v<0) throw std::invalid_argument("invalid reliability");
    }
    Pattern score_unchecked(const Bits& s,const Beliefs& r,const Bits& id) const {
        Pattern p; p.id=id;
        Bits fixed(bp_.num_variables(),-1), residual=s, degree(rows_.size(),0), k(bp_.num_variables(),0);
        const auto& w=bp_.physical_weights();
        for(size_t t=0;t<id.size();t+=2) { fixed[id[t]]=id[t+1]; p.g+=id[t+1]*w[id[t]]; p.rho+=r[id[t]]; }
        for(size_t a=0;a<rows_.size();++a) {
            for(int i:rows_[a]) { if(fixed[i]<0) ++degree[a]; else residual[a]^=fixed[i]; }
            if(!degree[a] && residual[a]) { p.rejected=true; return p; }
            if(residual[a]) for(int i:rows_[a]) if(fixed[i]<0) ++k[i];
        }
        for(size_t a=0;a<rows_.size();++a) if(residual[a]) {
            double minimum=std::numeric_limits<double>::infinity();
            for(int i:rows_[a]) if(fixed[i]<0) minimum=std::min(minimum,w[i]/k[i]);
            p.h+=minimum;
        }
        p.f=p.g+p.h; return p;
    }
public:
    ScreenedDecoder(std::vector<Bits> rows,int n,const Beliefs& p,Settings cfg={})
        :rows_(std::move(rows)),bp_(rows_,n,p),cfg_(cfg) {
        if(cfg.T0<1||cfg.Tpost<1||cfg.window<1||cfg.M<1||cfg.K<1||cfg.q<1||
           cfg.q>std::min(cfg.M,n)||!std::isfinite(cfg.limit)||cfg.limit<=0||cfg.limit>30)
            throw std::invalid_argument("invalid screened settings; require 1<=q<=min(M,n)");
        // Reject count overflow before starting an exhaustive run. No adaptive budget.
        __uint128_t count=1;
        int m=std::min(cfg.M,n), q=std::min(cfg.q,m-cfg.q);
        for(int i=1;i<=q;++i) {
            count=count*(m-q+i)/i;
            if(count>std::numeric_limits<uint64_t>::max()) throw std::overflow_error("pattern count exceeds uint64");
        }
        for(int i=0;i<cfg.q;++i) {
            count*=2;
            if(count>std::numeric_limits<uint64_t>::max()) throw std::overflow_error("pattern count exceeds uint64");
        }
    }
    double cost(const Bits& e) const {
        if(e.size()!=static_cast<size_t>(bp_.num_variables())) throw std::invalid_argument("correction shape mismatch");
        double total=0;
        for(size_t i=0;i<e.size();++i) {
            if(e[i]!=0 && e[i]!=1) throw std::invalid_argument("correction must be binary");
            if(e[i]) total+=bp_.physical_weights()[i];
        }
        return total;
    }
    bool valid(const Bits& e,const Bits& s) const {
        for(size_t a=0;a<rows_.size();++a) { int b=0; for(int i:rows_[a]) b^=e[i]; if(b!=s[a]) return false; }
        return true;
    }
    Bits pool(const Beliefs& r,const Bits& flips) const {
        check_reliability(r);
        if(flips.size()!=r.size()) throw std::invalid_argument("flip shape mismatch");
        for(int f:flips) if(f<0) throw std::invalid_argument("negative flip count");
        Bits u(r.size()); std::iota(u.begin(),u.end(),0);
        std::sort(u.begin(),u.end(),[&](int i,int j) { return std::make_tuple(r[i],-flips[i],i)<std::make_tuple(r[j],-flips[j],j); });
        u.resize(std::min(cfg_.M,bp_.num_variables())); return u;
    }
    Pattern score(const Bits& s,const Beliefs& r,const Bits& id) const {
        check_syndrome(s); check_reliability(r);
        if(id.size()!=static_cast<size_t>(2*cfg_.q)) throw std::invalid_argument("pattern has wrong size");
        int previous=-1;
        for(size_t i=0;i<id.size();i+=2) {
            if(id[i]<=previous||id[i]>=bp_.num_variables()||(id[i+1]!=0&&id[i+1]!=1)) throw std::invalid_argument("noncanonical pattern");
            previous=id[i];
        }
        return score_unchecked(s,r,id);
    }
    Screen screen(const Bits& s,const Beliefs& r,const Bits& flips) const {
        check_syndrome(s);
        Screen out; out.pool=pool(r,flips);
        Bits u=out.pool; std::sort(u.begin(),u.end());
        std::priority_queue<Pattern,std::vector<Pattern>,decltype(&better)> heap(&better);
        Bits id;
        std::function<void(size_t)> assignments=[&](size_t t) {
            if(t<id.size()) { for(int b=0;b<=1;++b) { id[t+1]=b; assignments(t+2); } return; }
            ++out.enumerated;
            Pattern p=score_unchecked(s,r,id);
            if(p.rejected) { ++out.rejected; return; }
            if(heap.size()<static_cast<size_t>(cfg_.K)) heap.push(std::move(p));
            else if(better(p,heap.top())) { heap.pop(); heap.push(std::move(p)); }
        };
        std::function<void(int,int)> subsets=[&](int start,int remaining) {
            if(!remaining) { assignments(0); return; }
            for(int t=start;t<=static_cast<int>(u.size())-remaining;++t) {
                id.push_back(u[t]); id.push_back(0); subsets(t+1,remaining-1); id.resize(id.size()-2);
            }
        };
        subsets(0,cfg_.q);
        while(!heap.empty()) { out.retained.push_back(heap.top()); heap.pop(); }
        std::sort(out.retained.begin(),out.retained.end(),better); return out;
    }
    SearchResult decode(const Bits& s,bool diagnostics=false,bool profiling=false) const {
        using Clock=std::chrono::steady_clock;
        SearchResult out;
        auto start=profiling?Clock::now():Clock::time_point{};
        auto stamp=[&](const char* name) { if(profiling) { auto end=Clock::now(); out.phases[name]=std::chrono::duration_cast<std::chrono::nanoseconds>(end-start).count(); start=end; } };
        auto initial=bp_.decode(s,cfg_.T0,cfg_.limit,cfg_.window);
        out.initial_iterations=initial.iterations;
        if(diagnostics) out.history=initial.history;
        stamp("initial_bp_wall_ns");
        if(initial.status==Status::CONVERGED) {
            out.status="INITIAL_CONVERGED"; out.initial_success=true; out.valid=true;
            out.correction=initial.last_decision; out.cost=cost(out.correction); return out;
        }
        if(initial.status==Status::LOCAL_CONTRADICTION) { out.status="LOCAL_CONTRADICTION"; return out; }
        out.screening=screen(s,initial.reliability,initial.flips);
        stamp("screening_wall_ns");
        for(const auto& p:out.screening.retained) {
            Bits fixed(bp_.num_variables(),-1);
            for(size_t i=0;i<p.id.size();i+=2) fixed[p.id[i]]=p.id[i+1];
            auto result=bp_.decode(s,cfg_.Tpost,cfg_.limit,0,fixed);
            ++out.completions; out.post_iterations+=result.iterations;
            bool ok=result.status==Status::CONVERGED && valid(result.last_decision,s);
            if(diagnostics) {
                out.completion_decisions.push_back(result.last_decision);
                out.completion_statuses.push_back(ok?"CONVERGED":"NONCONVERGENCE");
            }
            if(!ok) continue;
            ++out.successes;
            double w=cost(result.last_decision);
            if(!out.valid || std::tie(w,result.last_decision)<std::tie(out.cost,out.correction)) {
                out.valid=true; out.cost=w; out.correction=result.last_decision; out.selected_pattern=p.id;
            }
        }
        stamp("completions_wall_ns");
        if(out.valid) out.status="POST_CONVERGED";
        return out;
    }
};
} // namespace qec
