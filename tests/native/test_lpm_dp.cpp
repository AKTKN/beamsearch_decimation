#include "lpm_dp_candidates.hpp"
#include <cassert>
#include <iostream>
#include <map>
#include <random>

using namespace qec::lpm_dp;

namespace {

bool close(double a, double b, double tolerance = 2e-12) {
    return std::abs(a - b) <= tolerance * (1 + std::max(std::abs(a), std::abs(b)));
}

LocalVariable local(int id, uint8_t label, double field) {
    LocalVariable out;
    out.id = id; out.parity_label = label; out.field = field;
    out.unary_cost[0] = std::max(-field, 0.0) + std::log1p(std::exp(-std::abs(field)));
    out.unary_cost[1] = std::max(field, 0.0) + std::log1p(std::exp(-std::abs(field)));
    out.unary_probability[0] = std::exp(-out.unary_cost[0]);
    out.unary_probability[1] = std::exp(-out.unary_cost[1]);
    return out;
}

struct OracleEvaluation {
    double partition = 0;
    double coverage = 0;
    std::vector<ListEntry> ranked;
};

OracleEvaluation brute_force(const Region& region, const LocalFields& fields, uint8_t target,
                             int q, int keep) {
    assert(fields.variables.size() <= 8 && q >= 1 && q <= int(region.fixation_order.size()));
    std::map<int, size_t> offset;
    for (size_t i = 0; i < fields.variables.size(); ++i) offset[fields.variables[i].id] = i;
    std::map<uint64_t, double> marginal;
    OracleEvaluation out;
    const uint64_t total = uint64_t(1) << fields.variables.size();
    for (uint64_t assignment = 0; assignment < total; ++assignment) {
        uint8_t parity = 0; double cost = 0;
        for (size_t i = 0; i < fields.variables.size(); ++i) {
            const int bit = int((assignment >> i) & 1U);
            if (bit) parity ^= fields.variables[i].parity_label;
            cost += fields.variables[i].unary_cost[size_t(bit)];
        }
        if (parity != target) continue;
        const double mass = std::exp(-cost);
        out.partition += mass;
        uint64_t word = 0;
        for (int i = 0; i < q; ++i)
            word = (word << 1) | ((assignment >> offset.at(region.fixation_order[size_t(i)])) & 1U);
        marginal[word] += mass;
    }
    for (const auto& [word, mass] : marginal) out.ranked.push_back({-std::log(mass), word});
    std::sort(out.ranked.begin(), out.ranked.end(), [](const ListEntry& a, const ListEntry& b) {
        return a.cost != b.cost ? a.cost < b.cost : a.bits < b.bits;
    });
    if (out.ranked.size() > size_t(keep)) out.ranked.resize(size_t(keep));
    for (const auto& entry : out.ranked) out.coverage += std::exp(-entry.cost) / out.partition;
    return out;
}

void test_settings() {
    Settings defaults; defaults.validate();
    assert(defaults.history_window == 8 && defaults.history_clip == 25 && defaults.pool_size == 32);
    assert(defaults.local_check_limit == 2 && defaults.max_fixations == 4);
    assert(defaults.candidates_per_parent == 2 && defaults.retained_mass_target == .9 && defaults.proposal_clip == 30);
    for (int field = 0; field < 8; ++field) {
        Settings bad;
        if (field == 0) bad.history_window = 0;
        if (field == 1) bad.history_clip = 31;
        if (field == 2) bad.pool_size = 0;
        if (field == 3) bad.local_check_limit = 3;
        if (field == 4) bad.max_fixations = 65;
        if (field == 5) bad.candidates_per_parent = 1;
        if (field == 6) bad.retained_mass_target = 0;
        if (field == 7) bad.proposal_clip = 31;
        bool rejected = false;
        try { bad.validate(); } catch (const std::invalid_argument&) { rejected = true; }
        assert(rejected);
    }
}

void test_parent_and_region() {
    const ldpc::hybrid::Rows rows{{0,1,4},{1,2,4},{2,3}};
    Graph graph(rows, 6, Reals(6, .5));
    Settings settings; settings.history_window = 2; settings.history_clip = 1;
    settings.pool_size = 3; settings.max_fixations = 4;
    Bits syndrome{1,0,0}; std::vector<int8_t> fixed{0,-1,-1,-1,-1,-1};
    std::vector<Reals> history{{std::numeric_limits<double>::infinity(),-3,.2,.2,0,0},
                               {-std::numeric_limits<double>::infinity(),3,.2,.2,0,0}};
    Reals messages(graph.col.size(), 0);
    ParentView view{graph, syndrome, fixed, history, messages, 17};
    const auto summary = summarize_parent(view, settings);
    assert(summary.status == Status::Ok && summary.free == Bits({0,1,1,1,1,1}));
    assert(summary.mean_llr[1] == 0 && close(summary.mean_llr[2], .2));
    assert(summary.uncertain_pool == std::vector<int>({1,4,2}));
    assert(std::find(summary.uncertain_pool.begin(), summary.uncertain_pool.end(), 0) == summary.uncertain_pool.end());
    assert(std::find(summary.uncertain_pool.begin(), summary.uncertain_pool.end(), 5) == summary.uncertain_pool.end());
    const auto region = select_region(graph, summary, settings);
    assert(region.checks == std::vector<int>({0,1}));
    assert(region.variables == std::vector<int>({1,2,4}));
    assert(region.uncertain_local == std::vector<int>({1,4,2}));
    assert(region.fixation_order == region.uncertain_local); // Nested F_q are prefixes.

    settings.local_check_limit = 1;
    const auto single = select_region(graph, summary, settings);
    assert(single.checks == std::vector<int>({1}));

    settings.pool_size = 2; settings.local_check_limit = 2;
    const auto tied = select_region(graph, summarize_parent(view, settings), settings);
    assert(tied.checks == std::vector<int>({0,1}));
    assert(tied.fixation_order == std::vector<int>({1,4}));

    std::vector<int8_t> contradiction_fixed{0,0,0,0,0,-1};
    ParentView contradiction{graph, syndrome, contradiction_fixed, history, messages, 0};
    assert(summarize_parent(contradiction, settings).status == Status::ParentContradiction);
    Bits zero{0,0,0};
    ParentView solved{graph, zero, fixed, history, messages, 0};
    assert(summarize_parent(solved, settings).status == Status::ExistingSolution);
}

void test_cavity_fields() {
    const ldpc::hybrid::Rows rows{{0,1,4},{1,2,4},{2,3}};
    Graph graph(rows, 5, Reals(5, .5));
    Settings settings; settings.history_window = 1;
    Bits syndrome{1,0,0}; std::vector<int8_t> fixed(5, -1);
    std::vector<Reals> history(1, Reals(5, 0));
    Reals messages(graph.col.size(), 0);
    for (size_t edge = 0; edge < graph.col.size(); ++edge) {
        if (graph.row[edge] < 2) messages[edge] = -29; // Must be excluded.
        if (graph.row[edge] == 2 && graph.col[edge] == 2) messages[edge] = 100; // Clip to +30.
    }
    ParentView view{graph, syndrome, fixed, history, messages, 0};
    Region region{{0,1},{0,1,2,4},{0,1,2,4},{0,1,2,4}};
    const auto fields = build_local_fields(view, region, settings);
    assert(fields.variables.size() == 4);
    assert(detail::local_variable(fields, 1).field == 0);
    assert(detail::local_variable(fields, 2).field == 30);
    assert(close(detail::local_variable(fields, 2).unary_probability[0], 1.0 / (1.0 + std::exp(-30.))));
    assert(close(detail::local_variable(fields, 2).unary_probability[1], 1.0 / (1.0 + std::exp(30.))));
    assert(close(detail::local_variable(fields, 2).unary_cost[0], std::log1p(std::exp(-30.))));
    assert(close(detail::local_variable(fields, 2).unary_cost[1], 30 + std::log1p(std::exp(-30.))));
    assert(detail::local_variable(fields, 1).parity_label == 3);
}

void test_input_validation_and_end_to_end() {
    const ldpc::hybrid::Rows rows{{0,1}};
    Graph graph(rows, 2, Reals(2, .5));
    Settings settings; settings.history_window = 1; settings.local_check_limit = 1;
    settings.max_fixations = 2; settings.retained_mass_target = 1;
    Bits syndrome{1}; std::vector<int8_t> fixed(2, -1);
    std::vector<Reals> history(1, Reals(2, 0));
    Reals messages(graph.col.size(), 0);
    ParentView view{graph, syndrome, fixed, history, messages, 23};
    const auto result = generate_candidates(view, settings);
    assert(result.status == Status::Ok && result.parent_id == 23);
    assert(result.selected_checks == std::vector<int>({0}) && result.fixation_count == 2);
    assert(result.candidates.size() == 2 && close(result.retained_mass, 1));
    assert(result.candidates[0].pattern == Pattern({{0,0},{1,1}}));
    assert(result.candidates[1].pattern == Pattern({{0,1},{1,0}}));
    assert(result.candidates[0].parent_id == 23 && close(result.candidates[0].log_probability, -std::log(2.)));

    bool rejected = false;
    std::vector<Reals> short_history;
    try { (void)summarize_parent(ParentView{graph, syndrome, fixed, short_history, messages, 0}, settings); }
    catch (const std::invalid_argument&) { rejected = true; }
    assert(rejected);

    rejected = false;
    auto nonfinite_history = history;
    nonfinite_history[0][0] = std::numeric_limits<double>::infinity();
    try { (void)summarize_parent(ParentView{graph, syndrome, fixed, nonfinite_history, messages, 0}, settings); }
    catch (const std::invalid_argument&) { rejected = true; }
    assert(rejected);

    Region region{{0},{0,1},{0,1},{0,1}};
    LocalFields bad_fields{{local(0,0,0),local(1,1,0)}};
    rejected = false;
    try { (void)build_dp_tables(region, bad_fields, syndrome, settings); }
    catch (const std::invalid_argument&) { rejected = true; }
    assert(rejected);

    Region incomplete{{0},{0},{0},{0}};
    rejected = false;
    try { (void)build_local_fields(view, incomplete, settings); }
    catch (const std::invalid_argument&) { rejected = true; }
    assert(rejected);
}

void test_direct_dp_cases() {
    Settings settings; settings.candidates_per_parent = 2; settings.max_fixations = 4;

    Region one{{0},{0,1},{0},{0}};
    LocalFields one_fields{{local(0,1,0),local(1,1,0)}};
    auto one_dp = build_dp_tables(one, one_fields, Bits{1}, settings);
    auto one_eval = evaluate_fixation_count(one_dp, 1, settings, one.variables.size());
    assert(one_dp.states == 2 && one_eval.ranked.size() == 2 && one_eval.ranked[0].bits == 0 && one_eval.ranked[1].bits == 1);
    assert(one_eval.retained_mass == 1 && close(std::exp(-one_eval.negative_log_normalizer), .5));

    // Note's two-check example: shared boundary variable has joint label 3.
    Region example{{0,1},{0,1,2,3},{0,1,2},{0,1,2}};
    LocalFields example_fields{{local(0,1,0),local(1,3,0),local(2,2,0),local(3,3,std::log(9.0))}};
    auto example_dp = build_dp_tables(example, example_fields, Bits{1,0}, settings);
    auto q3 = evaluate_fixation_count(example_dp, 3, settings, example.variables.size());
    assert(q3.ranked.size() == 2 && q3.ranked[0].bits == 3 && q3.ranked[1].bits == 4);
    assert(close(std::exp(q3.negative_log_normalizer - q3.ranked[0].cost), .45));
    assert(close(q3.retained_mass, .9));
    Settings selection_settings = settings;
    selection_settings.retained_mass_target = .89;
    const auto example_selection = choose_fixation_count(7, example, example_dp, selection_settings);
    assert(example_selection.fixation_count == 3 && close(example_selection.retained_mass, .9));

    // Empty boundary: two independent parity equations leave exactly two of 8 patterns.
    Region empty{{0,1},{0,1,2},{0,1,2},{0,1,2}};
    LocalFields empty_fields{{local(0,1,0),local(1,3,0),local(2,2,0)}};
    auto empty_dp = build_dp_tables(empty, empty_fields, Bits{1,0}, settings);
    auto empty_eval = evaluate_fixation_count(empty_dp, 3, settings, empty.variables.size());
    assert(empty_eval.ranked.size() == 2 && close(empty_eval.retained_mass, 1));

    // Identical selected rows cannot realize different target parity bits.
    Region impossible{{0,1},{0,1},{0},{0}};
    LocalFields impossible_fields{{local(0,3,0),local(1,3,0)}};
    auto impossible_dp = build_dp_tables(impossible, impossible_fields, Bits{1,0}, settings);
    assert(!impossible_dp.feasible);
}

void test_selection_and_q64() {
    Settings settings; settings.candidates_per_parent = 2; settings.retained_mass_target = .9;
    Region uniform{{0},{0,1,2,3},{0,1,2,3},{0,1,2,3}};
    LocalFields fields{{local(0,1,0),local(1,1,0),local(2,1,0),local(3,1,0)}};
    auto tables = build_dp_tables(uniform, fields, Bits{0}, settings);
    assert(close(evaluate_fixation_count(tables, 4, settings, 4).retained_mass, .25));
    const auto selected = choose_fixation_count(9, uniform, tables, settings);
    assert(selected.fixation_count == 1 && selected.retained_mass == 1);

    settings.max_fixations = 64; settings.retained_mass_target = 1e-100;
    Region wide; wide.checks={0};
    LocalFields wide_fields;
    for (int j=0;j<64;++j) { wide.variables.push_back(j); wide.uncertain_local.push_back(j); wide.fixation_order.push_back(j); wide_fields.variables.push_back(local(j,1,0)); }
    auto wide_dp = build_dp_tables(wide, wide_fields, Bits{0}, settings);
    const auto result = choose_fixation_count(4,wide,wide_dp,settings);
    assert(result.fixation_count == 64 && result.candidates.size() == 2);
    assert(result.candidates[0].selected_order_bits == 0 && result.candidates[1].selected_order_bits == 3);
    assert((result.candidates[0].pattern.front() == std::pair<int,int>(0,0)));
    assert((result.candidates[0].pattern.back() == std::pair<int,int>(63,0)));
}

void test_random_oracle() {
    std::mt19937_64 rng(20260923);
    std::uniform_real_distribution<double> field_distribution(-3.0,3.0);
    std::uniform_real_distribution<double> target_distribution(.25,.99);
    size_t feasible_cases=0, infeasible_cases=0, compared_q=0;
    for (int trial=0; trial<600; ++trial) {
        const int r=1+int(rng()%2), states=1<<r, count=1+int(rng()%8);
        Settings settings; settings.max_fixations=1+int(rng()%count);
        settings.candidates_per_parent=2+int(rng()%3); settings.retained_mass_target=target_distribution(rng);
        Region region;
        for(int a=0;a<r;++a) region.checks.push_back(a);
        LocalFields fields;
        for(int j=0;j<count;++j) {
            region.variables.push_back(j); region.uncertain_local.push_back(j);
            fields.variables.push_back(local(j,uint8_t(1+rng()%(states-1)),field_distribution(rng)));
        }
        std::shuffle(region.uncertain_local.begin(),region.uncertain_local.end(),rng);
        region.fixation_order.assign(region.uncertain_local.begin(),region.uncertain_local.begin()+settings.max_fixations);
        Bits residual(size_t(r), 0); const uint8_t target=uint8_t(rng()%states);
        for(int bit=0;bit<r;++bit) residual[size_t(bit)]=(target>>bit)&1U;
        const auto tables=build_dp_tables(region,fields,residual,settings);
        if(!tables.feasible) {++infeasible_cases; continue;}
        ++feasible_cases;
        int expected_q=1;
        for(int q=1;q<=settings.max_fixations;++q) {
            const auto oracle=brute_force(region,fields,target,q,settings.candidates_per_parent);
            const auto actual=evaluate_fixation_count(tables,q,settings,region.variables.size());
            assert(close(std::exp(-actual.negative_log_normalizer),oracle.partition,4e-12));
            assert(actual.ranked.size()==oracle.ranked.size());
            for(size_t i=0;i<oracle.ranked.size();++i) {
                assert(actual.ranked[i].bits==oracle.ranked[i].bits);
                assert(close(actual.ranked[i].cost,oracle.ranked[i].cost,4e-12));
            }
            assert(close(actual.retained_mass,oracle.coverage,5e-12));
            if(oracle.coverage>=settings.retained_mass_target) expected_q=q;
            ++compared_q;
        }
        int selected_q=1;
        for(int q=settings.max_fixations;q>=1;--q) {
            const auto oracle=brute_force(region,fields,target,q,settings.candidates_per_parent);
            if(q==1 || oracle.coverage>=settings.retained_mass_target) {selected_q=q;break;}
        }
        assert(selected_q==expected_q);
        const auto actual_selection=choose_fixation_count(11,region,tables,settings);
        assert(actual_selection.fixation_count==selected_q);
        const auto selected_oracle=brute_force(region,fields,target,selected_q,settings.candidates_per_parent);
        assert(actual_selection.candidates.size()==selected_oracle.ranked.size());
        for(size_t i=0;i<selected_oracle.ranked.size();++i) {
            assert(actual_selection.candidates[i].selected_order_bits==selected_oracle.ranked[i].bits);
            assert(close(actual_selection.candidates[i].log_probability,
                         std::log(std::exp(-selected_oracle.ranked[i].cost)/selected_oracle.partition),5e-12));
        }
    }
    assert(feasible_cases>500 && infeasible_cases>0 && compared_q>1000);
    std::cout<<feasible_cases<<" feasible random local models, "<<infeasible_cases
             <<" infeasible models and "<<compared_q<<" fixation marginals checked\n";
}

} // namespace

int main() {
    std::cout << "ABI sizes: ListEntry=" << sizeof(ListEntry)
              << " LocalVariable=" << sizeof(LocalVariable) << " bytes\n";
    test_settings();
    test_parent_and_region();
    test_cavity_fields();
    test_input_validation_and_end_to_end();
    test_direct_dp_cases();
    test_selection_and_q64();
    test_random_oracle();
    std::cout<<"standalone LPM-DP candidate-generator checks passed\n";
}
