#include "search_bp.hpp"
#include <cassert>
#include <iostream>

using namespace qec::search_bp;

int main() {
    Settings search_settings;
    search_settings.max_cycles=1;search_settings.expansions_per_cycle=1;
    search_settings.bp_enabled=false;search_settings.beam_width=0;search_settings.max_iteration=0;
    auto model=std::make_shared<Model>(Rows{{0,1,2},{0,2},{1,2}},3,Reals{.1,.2,.3},Rows{});
    SearchSession search(model,search_settings);search.reset({1,0,0});
    auto slice=search.advance(1,{},[](const Bits&,uint64_t){return false;});
    assert(slice.expansions==1&&slice.generated==3&&search.counts.generated==4);

    // Generated children have no independent cap: one allowed expansion may
    // construct every canonical child of the selected Tanner-graph check.
    Rows wide_rows(1);Reals wide_probabilities(96,.1);
    for(int i=0;i<96;++i)wide_rows[0].push_back(i);
    auto wide_model=std::make_shared<Model>(wide_rows,96,wide_probabilities,Rows{});
    SearchSession wide_search(wide_model,search_settings);wide_search.reset({1});
    auto wide_slice=wide_search.advance(1,{},[](const Bits&,uint64_t){return false;});
    assert(wide_slice.expansions==1&&wide_slice.generated==96&&wide_search.counts.generated==97);

    // Fixing x0=1 removes every incident edge and XORs those checks into the
    // residual syndrome. Fixed edges remain zero across iterations.
    HardFixedMinSumSession hard(model->graph,1.0);
    hard.reset({1,0,0},Key{{0,1}},7);
    auto initial=hard.snapshot();
    assert(initial.fixed[0]==1&&initial.residual==Bits({0,1,0}));
    for(size_t j=model->graph->cp[0];j<model->graph->cp[1];++j) {
        const size_t edge=model->graph->ce[j];assert(initial.q[edge]==0&&initial.z[edge]==0);
    }
    hard.advance(2);auto advanced=hard.snapshot();
    assert(advanced.decision[0]==1);
    for(size_t j=model->graph->cp[0];j<model->graph->cp[1];++j) {
        const size_t edge=model->graph->ce[j];assert(advanced.q[edge]==0&&advanced.z[edge]==0);
    }

    // The active-node decisions match the upstream parallel min-sum kernel on
    // the explicitly reduced matrix and residual syndrome.
    ldpc::bp::BpSparse reduced(3,2,5);
    reduced.insert_entry(0,0);reduced.insert_entry(0,1);reduced.insert_entry(1,1);
    reduced.insert_entry(2,0);reduced.insert_entry(2,1);
    ldpc::bp::BpDecoder upstream(reduced,{.2,.3},2,ldpc::bp::MINIMUM_SUM,
        ldpc::bp::PARALLEL,1.0,1,{},0,false,ldpc::bp::SYNDROME);
    Bits residual={0,1,0};auto expected=upstream.decode(residual);
    assert(advanced.decision[1]==expected[0]&&advanced.decision[2]==expected[1]);

    // A descendant can inherit active messages but must preserve every ancestor
    // fixation. This is the hard-graph counterpart of beam state inheritance.
    hard.inherit(advanced,Key{{0,1},{1,0}},7);
    auto descendant=hard.snapshot();assert(descendant.fixed[0]==1&&descendant.fixed[1]==0);
    bool rejected=false;
    try{hard.inherit(advanced,Key{{0,0},{1,0}},7);}catch(const std::invalid_argument&){rejected=true;}
    assert(rejected);

    Settings controller;
    controller.max_cycles=1;controller.expansions_per_cycle=1;
    controller.beam_width=2;controller.max_iteration=3;
    Decoder decoder({{2,3},{0,1},{}},4,{.1,.1,.1,.1},{},controller);
    auto result=decoder.decode({1,1,0});auto telemetry=decoder.export_telemetry();
    assert(result.valid&&telemetry.updates.size()<=2);
    for(const auto& update:telemetry.updates)assert(update.quota==3&&update.violations==0);
    assert(telemetry.bp.retained_final<=2);
    std::cout<<"search_bp hard fixation, residual syndrome and beam scheduling passed\n";
}
