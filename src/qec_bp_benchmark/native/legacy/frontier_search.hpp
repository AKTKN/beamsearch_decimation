#ifndef QEC_FRONTIER_SEARCH_HPP
#define QEC_FRONTIER_SEARCH_HPP
#include "frontier_model.hpp"
#include <functional>

namespace qec::frontier {
enum class ConstructionStatus { Root,Feasible,Goal,LocallyInfeasible,DepthLimited };
enum class SearchStatus { Queued,Expanded,PartiallyExpanded,Goal,LocallyInfeasible,DepthLimited,DetBeamDiscarded };

struct Node {
    uint64_t id=0,parent=UINT64_MAX;
    int selected=-1;
    size_t zeros_begin=0,zeros_count=0;
    uint64_t depth=0,rho=0;
    uint32_t generation_cycle=UINT32_MAX;
    Packed residual;
    double g=0,h=0,f=0;
    Key order_pattern;
    ConstructionStatus construction=ConstructionStatus::Root;
    SearchStatus search_status=SearchStatus::Queued;
    bool in_q=false,in_g=false,admitted=false;
};

struct SearchCounts {
    uint64_t roots=0,generated=0,expanded=0,queue_pops=0,stale_pops=0,terminal_pops=0;
    uint64_t locally_infeasible=0,depth_limited=0,det_beam_discards=0;
    uint64_t truncated_parents=0,ungenerated_siblings=0,frontier_peak=0,guidance_peak=0;
    uint64_t max_depth=0,direct_solutions=0,rho_min=0;
    bool node_cap_hit=false,expansion_cap_hit=false,generation_frozen=false;
};
struct SliceResult {bool stop=false,cpu_cap=false;uint64_t expansions=0,generated=0;};

// Shot-local persistent search. Q and G are independent lazy heaps over the
// same compact node arena; admission only changes G membership.
class SearchSession {
    std::shared_ptr<const Model> model_;
    Settings settings_;
    bool reference_=false;
    std::vector<Node> nodes_;
    std::vector<int> zeros_;
    std::vector<uint64_t> frontier_,guidance_;
    std::vector<int8_t> assignment_;
    std::vector<int> active_;
    Reals tree_;
    size_t leaves_=1,live_q_=0,live_g_=0;
    uint32_t generation_cycle_=0;

    bool earlier(uint64_t a,uint64_t b) const {
        const auto& x=nodes_[a];const auto& y=nodes_[b];
        if(x.f!=y.f) return x.f<y.f;
        if(x.rho!=y.rho) return x.rho<y.rho;
        if(x.order_pattern!=y.order_pattern) return x.order_pattern<y.order_pattern;
        return x.id<y.id;
    }
    auto comparator() const {return [this](uint64_t a,uint64_t b){return earlier(b,a);};}
    void push(std::vector<uint64_t>& heap,uint64_t id) {
        heap.push_back(id);std::push_heap(heap.begin(),heap.end(),comparator());
    }
    uint64_t pop_raw(std::vector<uint64_t>& heap) {
        std::pop_heap(heap.begin(),heap.end(),comparator());auto id=heap.back();heap.pop_back();return id;
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
        std::fill(tree_.begin(),tree_.end(),0.0);
        if(!reference_) {
            std::fill(active_.begin(),active_.end(),0);
            for(int a=0;a<graph.m;++a) if(qec::hybrid::bit(node.residual,a))
                for(size_t e=graph.rp[a];e<graph.rp[a+1];++e) ++active_[graph.col[e]];
        }
        for(int a=0;a<graph.m;++a) if(qec::hybrid::bit(node.residual,a)) {
            double best=std::numeric_limits<double>::infinity();
            for(size_t e=graph.rp[a];e<graph.rp[a+1];++e) {
                int i=graph.col[e];if(assignment_[i]!=-1) continue;
                int k=active_[i];
                if(reference_) {k=0;for(size_t q=graph.cp[i];q<graph.cp[i+1];++q)
                    k+=qec::hybrid::bit(node.residual,graph.row[graph.ce[q]]);}
                best=std::min(best,graph.weights[i]/double(k));
            }
            if(!std::isfinite(best)) return false;
            tree_[leaves_+size_t(a)]=best;
        }
        for(size_t j=leaves_;j-->1;) tree_[j]=ldpc::hybrid::finite(tree_[2*j]+tree_[2*j+1]);
        node.h=tree_[1];node.g=0;
        for(auto [i,b]:node.order_pattern) if(b) node.g=ldpc::hybrid::finite(node.g+graph.weights[i]);
        node.f=ldpc::hybrid::finite(node.g+node.h);return true;
    }
    void queue_node(uint64_t id,bool terminal) {
        auto& node=nodes_[id];
        const bool depth_ok=settings_.max_depth<0||node.depth<uint64_t(settings_.max_depth);
        if((!terminal&&depth_ok)||(terminal&&settings_.goal_test==GoalTest::OnPop)) {
            node.in_q=true;++live_q_;push(frontier_,id);counts.frontier_peak=std::max<uint64_t>(counts.frontier_peak,live_q_);
        }
        const bool hint_ok=!terminal&&id!=0&&(settings_.hint_max_depth<0||node.depth<=uint64_t(settings_.hint_max_depth));
        if(hint_ok&&(node.construction==ConstructionStatus::Feasible||node.construction==ConstructionStatus::DepthLimited)) {
            node.in_g=true;++live_g_;push(guidance_,id);counts.guidance_peak=std::max<uint64_t>(counts.guidance_peak,live_g_);
        }
    }
    Bits correction(const Node& node) const {
        Bits out(size_t(model_->graph->n),0);for(auto [i,b]:node.order_pattern) out[size_t(i)]=b;return out;
    }
    void truncate(Node& parent,size_t remaining) {
        parent.search_status=SearchStatus::PartiallyExpanded;++counts.truncated_parents;
        counts.ungenerated_siblings+=remaining;
    }
public:
    SearchCounts counts;
    SearchSession(std::shared_ptr<const Model> model,Settings settings,bool reference=false):
        model_(std::move(model)),settings_(std::move(settings)),reference_(reference) {
        settings_.validate();assignment_.resize(size_t(model_->graph->n));active_.resize(size_t(model_->graph->n));
        while(leaves_<size_t(model_->graph->m)) {if(leaves_>SIZE_MAX/2) throw std::length_error("heuristic tree overflow");leaves_*=2;}
        tree_.resize(2*leaves_);nodes_.reserve(size_t(std::min<uint64_t>(settings_.max_generated_nodes,4096)));
    }
    void clear() {nodes_.clear();zeros_.clear();frontier_.clear();guidance_.clear();live_q_=live_g_=0;counts={};}
    void reset(const Bits& syndrome) {
        clear();ldpc::hybrid::binary(syndrome,size_t(model_->graph->m));
        Node root;root.residual.assign((size_t(model_->graph->m)+63)/64,0);
        for(int a=0;a<model_->graph->m;++a) if(syndrome[size_t(a)]) qec::hybrid::flip(root.residual,a);
        root.rho=qec::hybrid::weight(root.residual);counts.rho_min=root.rho;
        std::fill(assignment_.begin(),assignment_.end(),-1);bool feasible=score(root);
        counts.roots=counts.generated=1;nodes_.push_back(std::move(root));
        if(!feasible) {nodes_[0].construction=ConstructionStatus::LocallyInfeasible;nodes_[0].search_status=SearchStatus::LocallyInfeasible;++counts.locally_infeasible;return;}
        if(!nodes_[0].rho) {nodes_[0].construction=ConstructionStatus::Goal;nodes_[0].search_status=SearchStatus::Goal;return;}
        if(settings_.max_depth==0) {nodes_[0].construction=ConstructionStatus::DepthLimited;nodes_[0].search_status=SearchStatus::DepthLimited;++counts.depth_limited;return;}
        queue_node(0,false);
    }
    size_t frontier_size() const {return live_q_;}
    size_t guidance_size() const {return live_g_;}
    const Node& node(uint64_t id) const {return nodes_.at(size_t(id));}
    const std::vector<Node>& nodes() const {return nodes_;}
    void set_cycle(uint32_t cycle){generation_cycle_=cycle;}
    std::vector<uint32_t> added_zeros(uint64_t id) const {
        const auto& node=nodes_.at(size_t(id));std::vector<uint32_t> out;out.reserve(node.zeros_count);
        for(size_t k=node.zeros_begin;k<node.zeros_begin+node.zeros_count;++k) out.push_back(uint32_t(zeros_[k]));
        std::sort(out.begin(),out.end());return out;
    }
    bool is_ancestor(uint64_t ancestor,uint64_t descendant) const {
        for(uint64_t id=nodes_.at(size_t(descendant)).parent;id!=UINT64_MAX;id=nodes_[size_t(id)].parent)
            if(id==ancestor) return true;
        return false;
    }
    std::vector<uint64_t> proposals(uint64_t limit) const {
        auto heap=guidance_;std::vector<uint64_t> out;out.reserve(size_t(std::min<uint64_t>(limit,live_g_)));
        auto cmp=comparator();
        while(!heap.empty()&&out.size()<limit) {
            std::pop_heap(heap.begin(),heap.end(),cmp);auto id=heap.back();heap.pop_back();
            if(nodes_[size_t(id)].in_g&&!nodes_[size_t(id)].admitted) out.push_back(id);
        }
        return out;
    }
    void admit(uint64_t id) {
        auto& node=nodes_.at(size_t(id));
        if(!node.in_g||node.admitted) throw std::logic_error("guidance node cannot be admitted twice");
        node.in_g=false;node.admitted=true;--live_g_;
    }
    SliceResult advance(uint64_t allowance,const std::function<bool()>& cpu_cap,
                        const std::function<bool(const Bits&,uint64_t)>& submit) {
        SliceResult out;const auto& graph=*model_->graph;uint64_t used=0;
        while(!frontier_.empty()) {
            if(cpu_cap&&cpu_cap()) {out.cpu_cap=true;return out;}
            uint64_t parent_id=pop_raw(frontier_);auto& parent=nodes_[size_t(parent_id)];
            if(!parent.in_q) {++counts.queue_pops;++counts.stale_pops;continue;}
            if(!parent.rho&&settings_.goal_test==GoalTest::OnPop) {
                parent.in_q=false;--live_q_;++counts.queue_pops;++counts.terminal_pops;++counts.direct_solutions;
                parent.search_status=SearchStatus::Goal;
                if(submit(correction(parent),parent_id)) {out.stop=true;return out;}
                continue;
            }
            if(settings_.det_beam>=0&&parent.rho>counts.rho_min+uint64_t(settings_.det_beam)) {
                parent.in_q=false;--live_q_;++counts.queue_pops;++counts.det_beam_discards;
                parent.search_status=SearchStatus::DetBeamDiscarded;continue;
            }
            counts.rho_min=std::min(counts.rho_min,parent.rho);
            if(used>=allowance) {push(frontier_,parent_id);break;}
            if(counts.generation_frozen) {push(frontier_,parent_id);break;}
            if(counts.expanded>=settings_.max_expansions) {
                counts.expansion_cap_hit=counts.generation_frozen=true;push(frontier_,parent_id);break;
            }
            parent.in_q=false;--live_q_;++counts.queue_pops;++counts.expanded;++used;++out.expansions;
            parent.search_status=SearchStatus::Expanded;materialize(parent_id);
            Packed residual=parent.residual;Key pattern=parent.order_pattern;
            int a=0;while(a<graph.m&&!qec::hybrid::bit(residual,a)) ++a;
            std::vector<int> free;for(int i:model_->ordered[size_t(a)]) if(assignment_[size_t(i)]<0) free.push_back(i);
            for(size_t k=0;k<free.size();++k) {
                if(cpu_cap&&cpu_cap()) {truncate(nodes_[size_t(parent_id)],free.size()-k);out.cpu_cap=true;return out;}
                if(counts.generated>=settings_.max_generated_nodes) {
                    truncate(nodes_[size_t(parent_id)],free.size()-k);counts.node_cap_hit=counts.generation_frozen=true;return out;
                }
                const int selected=free[k];Node child;child.id=nodes_.size();child.parent=parent_id;child.selected=selected;
                child.generation_cycle=generation_cycle_;
                child.zeros_begin=zeros_.size();child.zeros_count=k;zeros_.insert(zeros_.end(),free.begin(),free.begin()+long(k));
                child.depth=parent.depth+1;child.residual=residual;
                for(size_t e=graph.cp[size_t(selected)];e<graph.cp[size_t(selected)+1];++e)
                    qec::hybrid::flip(child.residual,graph.row[graph.ce[e]]);
                child.rho=qec::hybrid::weight(child.residual);child.order_pattern=pattern;
                for(size_t j=0;j<k;++j) child.order_pattern.emplace_back(free[j],0);
                child.order_pattern.emplace_back(selected,1);std::sort(child.order_pattern.begin(),child.order_pattern.end());
                child.g=ldpc::hybrid::finite(parent.g+graph.weights[size_t(selected)]);child.h=0;child.f=child.g;
                ++counts.generated;++out.generated;counts.max_depth=std::max(counts.max_depth,child.depth);
                const uint64_t id=child.id;
                if(!child.rho) {
                    child.construction=ConstructionStatus::Goal;child.search_status=SearchStatus::Goal;nodes_.push_back(std::move(child));
                    if(settings_.goal_test==GoalTest::OnGeneration) {
                        ++counts.direct_solutions;
                        if(submit(correction(nodes_.back()),id)) {
                            if(k+1<free.size()) truncate(nodes_[size_t(parent_id)],free.size()-k-1);
                            out.stop=true;return out;
                        }
                    } else queue_node(id,true);
                    continue;
                }
                for(size_t j=0;j<k;++j) assignment_[size_t(free[j])]=0;
                assignment_[size_t(selected)]=1;
                bool feasible=score(child);assignment_[size_t(selected)]=-1;
                for(size_t j=0;j<k;++j) assignment_[size_t(free[j])]=-1;
                if(!feasible) {
                    child.construction=ConstructionStatus::LocallyInfeasible;child.search_status=SearchStatus::LocallyInfeasible;
                    ++counts.locally_infeasible;nodes_.push_back(std::move(child));continue;
                }
                const bool depth_limited=settings_.max_depth>=0&&child.depth>=uint64_t(settings_.max_depth);
                if(depth_limited) {child.construction=ConstructionStatus::DepthLimited;child.search_status=SearchStatus::DepthLimited;++counts.depth_limited;}
                else {child.construction=ConstructionStatus::Feasible;child.search_status=SearchStatus::Queued;}
                nodes_.push_back(std::move(child));queue_node(id,false);
                if(depth_limited) {auto& stored=nodes_.back();if(stored.in_q){stored.in_q=false;--live_q_;}}
            }
        }
        return out;
    }
};
}
#endif
