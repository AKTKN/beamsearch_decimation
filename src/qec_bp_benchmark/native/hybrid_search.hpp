#ifndef QEC_HYBRID_SEARCH_HPP
#define QEC_HYBRID_SEARCH_HPP
#include "hybrid_model.hpp"
#include <functional>
#include <queue>
namespace qec::hybrid {
struct SearchCounts {
    uint64_t expanded=0,generated=0,rejected=0,depth_limited=0,frontier_peak=0,guidance_peak=0,max_depth=0;
};
struct Node {
    uint64_t id=0,parent=UINT64_MAX;
    int selected=-1,depth=0;
    size_t zeros_begin=0,zeros_count=0;
    Key key; // cached exact canonical tie key; never used as a residual-only visited key
    Packed residual;
    double g=0,h=0,f=0;
    uint64_t rho=0;
};
struct SearchStep { bool goal=false,node_cap=false,cpu_cap=false; Bits correction; };

// Non-reentrant persistent session. Node IDs reference a compact arena; parent
// deltas reconstruct assignments into reusable byte flags. No beam truncation.
class SearchSession {
    std::shared_ptr<const Model> model_;
    Settings settings_;
    bool reference_;
    std::vector<Node> nodes_;
    std::vector<int> zeros_;
    std::vector<uint64_t> frontier_,guidance_;
    std::vector<int8_t> assignment_;
    std::vector<int> active_;
    Reals tree_;
    size_t leaves_=1;
    bool earlier(uint64_t a,uint64_t b) const {
        const auto& x=nodes_[a]; const auto& y=nodes_[b];
        if(x.f!=y.f) return x.f<y.f;
        if(x.rho!=y.rho) return x.rho<y.rho;
        return x.key<y.key;
    }
    void push(std::vector<uint64_t>& queue,uint64_t id) {
        queue.push_back(id);
        if(!reference_) std::push_heap(queue.begin(),queue.end(),[this](auto a,auto b){return earlier(b,a);});
    }
    uint64_t pop(std::vector<uint64_t>& queue) {
        if(reference_) {
            auto it=std::min_element(queue.begin(),queue.end(),[this](auto a,auto b){return earlier(a,b);});
            auto result=*it; queue.erase(it); return result;
        }
        std::pop_heap(queue.begin(),queue.end(),[this](auto a,auto b){return earlier(b,a);});
        auto result=queue.back(); queue.pop_back(); return result;
    }
    void materialize(uint64_t id) {
        std::fill(assignment_.begin(),assignment_.end(),-1);
        for(;id!=UINT64_MAX;id=nodes_[id].parent) {
            const auto& node=nodes_[id];
            if(node.selected>=0) assignment_[node.selected]=1;
            for(size_t k=node.zeros_begin;k<node.zeros_begin+node.zeros_count;++k) assignment_[zeros_[k]]=0;
        }
    }
    bool score(Node& node) {
        const auto& graph=*model_->graph;
        std::fill(tree_.begin(),tree_.end(),0);
        if(!reference_) {
            std::fill(active_.begin(),active_.end(),0);
            for(int a=0;a<graph.m;++a) if(bit(node.residual,a))
                for(size_t e=graph.rp[a];e<graph.rp[a+1];++e) ++active_[graph.col[e]];
        }
        for(int a=0;a<graph.m;++a) if(bit(node.residual,a)) {
            double best=std::numeric_limits<double>::infinity();
            for(size_t e=graph.rp[a];e<graph.rp[a+1];++e) {
                int i=graph.col[e]; if(assignment_[i]!=-1) continue;
                int k=active_[i];
                if(reference_) {k=0; for(size_t q=graph.cp[i];q<graph.cp[i+1];++q) k+=bit(node.residual,graph.row[graph.ce[q]]);}
                best=std::min(best,graph.weights[i]/k);
            }
            if(!std::isfinite(best)) return false;
            tree_[leaves_+a]=best;
        }
        for(size_t j=leaves_;j-->1;) tree_[j]=finite(tree_[2*j]+tree_[2*j+1]);
        node.h=tree_[1]; node.g=0;
        for(auto [i,b]:node.key) if(b) node.g=finite(node.g+graph.weights[i]);
        node.f=finite(node.g+node.h); return true;
    }
public:
    SearchCounts counts;
    SearchSession(std::shared_ptr<const Model> model,Settings settings,bool reference=false):
        model_(std::move(model)),settings_(std::move(settings)),reference_(reference) {
        settings_.validate();
        assignment_.resize(model_->graph->n); active_.resize(model_->graph->n);
        while(leaves_<size_t(model_->graph->m)) {if(leaves_>SIZE_MAX/2) throw std::length_error("heuristic tree overflow"); leaves_*=2;}
        if(leaves_>tree_.max_size()/2) throw std::length_error("heuristic tree allocation overflow");
        tree_.resize(2*leaves_);
        nodes_.reserve(size_t(std::min<uint64_t>(settings_.max_generated_nodes,4096)));
    }
    void clear() {nodes_.clear(); zeros_.clear(); frontier_.clear(); guidance_.clear(); counts={};}
    void reset(const Bits& s) {
        clear(); binary(s,model_->graph->m);
        Node root; root.residual.assign((size_t(model_->graph->m)+63)/64,0);
        for(int a=0;a<model_->graph->m;++a) if(s[a]) flip(root.residual,a);
        root.rho=weight(root.residual); std::fill(assignment_.begin(),assignment_.end(),-1);
        bool consistent=score(root); nodes_.push_back(std::move(root)); counts.generated=1;
        if(nodes_[0].rho && settings_.max_depth==0) ++counts.depth_limited;
        if(consistent && nodes_[0].rho && settings_.max_depth>0) push(frontier_,0);
        counts.frontier_peak=frontier_.size();
    }
    size_t frontier_size() const {return frontier_.size();}
    size_t guidance_size() const {return guidance_.size();}
    const Node& node(uint64_t id) const {return nodes_.at(id);}
    const std::vector<Node>& nodes() const {return nodes_;} // test-only snapshot access
    uint64_t take_hint() {if(guidance_.empty()) throw std::logic_error("empty guidance pool"); return pop(guidance_);}
    // Test oracle entry: evaluate arbitrary partial assignments against original H.
    Node evaluate(const Bits& s,const Key& key) {
        binary(s,model_->graph->m); Node node; node.key=key;
        node.residual.assign((size_t(model_->graph->m)+63)/64,0);
        for(int a=0;a<model_->graph->m;++a) if(s[a]) flip(node.residual,a);
        std::fill(assignment_.begin(),assignment_.end(),-1); int previous=-1;
        for(auto [i,b]:key) {
            if(i<=previous||i>=model_->graph->n||b>1) throw std::invalid_argument("invalid canonical pattern");
            previous=i; assignment_[i]=b;
            if(b) {++node.depth; for(size_t j=model_->graph->cp[i];j<model_->graph->cp[i+1];++j) flip(node.residual,model_->graph->row[model_->graph->ce[j]]);}
        }
        node.rho=weight(node.residual); if(!score(node)) node.h=node.f=std::numeric_limits<double>::infinity();
        return node;
    }
    SearchStep advance(uint64_t budget,const std::function<bool()>& cap={}) {
        SearchStep result;
        const auto& graph=*model_->graph;
        for(uint64_t step=0;step<budget && !frontier_.empty();++step) {
            if(cap && cap()) {result.cpu_cap=true; return result;}
            uint64_t parent=pop(frontier_); ++counts.expanded; materialize(parent);
            // Copy hot parent metadata before growing the node arena.
            Packed residual=nodes_[parent].residual; Key parent_key=nodes_[parent].key;
            int depth=nodes_[parent].depth+1,a=0; while(a<graph.m && !bit(residual,a)) ++a;
            std::vector<int> free;
            for(int i:model_->ordered[a]) if(assignment_[i]==-1) free.push_back(i);
            for(size_t k=0;k<free.size();++k) {
                if(cap && cap()) {result.cpu_cap=true; return result;}
                if(counts.generated>=settings_.max_generated_nodes) {result.node_cap=true; return result;}
                int selected=free[k]; Node child;
                child.id=nodes_.size(); child.parent=parent; child.selected=selected; child.depth=depth;
                child.zeros_begin=zeros_.size(); child.zeros_count=k;
                zeros_.insert(zeros_.end(),free.begin(),free.begin()+k);
                child.residual=residual;
                for(size_t e=graph.cp[selected];e<graph.cp[selected+1];++e) flip(child.residual,graph.row[graph.ce[e]]);
                child.rho=weight(child.residual); child.key=parent_key;
                for(size_t j=0;j<k;++j) child.key.emplace_back(free[j],0);
                child.key.emplace_back(selected,1); std::sort(child.key.begin(),child.key.end());
                ++counts.generated; counts.max_depth=std::max(counts.max_depth,uint64_t(depth));
                // Goal test precedes heuristic evaluation and heap insertion, at D too.
                if(!child.rho) {
                    result.goal=true; result.correction.assign(graph.n,0);
                    for(auto [i,b]:child.key) result.correction[i]=b;
                    nodes_.push_back(std::move(child)); return result;
                }
                if(depth==settings_.max_depth) ++counts.depth_limited;
                for(size_t j=0;j<k;++j) assignment_[free[j]]=0;
                assignment_[selected]=1;
                bool consistent=score(child);
                assignment_[selected]=-1; for(size_t j=0;j<k;++j) assignment_[free[j]]=-1;
                auto id=child.id; nodes_.push_back(std::move(child));
                if(!consistent) {++counts.rejected; continue;}
                push(guidance_,id);
                if(depth<settings_.max_depth) push(frontier_,id);
                counts.frontier_peak=std::max<uint64_t>(counts.frontier_peak,frontier_.size());
                counts.guidance_peak=std::max<uint64_t>(counts.guidance_peak,guidance_.size());
            }
        }
        return result;
    }
};
}
#endif
