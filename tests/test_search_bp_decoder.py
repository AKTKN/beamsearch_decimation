"""Deterministic native search_bp hard-fixation and beam tests."""
import math

from qec_bp_benchmark.decoders import native_hybrid


def settings(*, cycles=2, expansions=1, width=2, max_iteration=4):
    native = native_hybrid()
    value = native.SearchBPSettings()
    value.max_cycles = cycles
    value.expansions_per_cycle = expansions
    value.beam_width = width
    value.max_iteration = max_iteration
    return value


def test_native_settings_have_no_generated_node_cap():
    assert not hasattr(native_hybrid().SearchBPSettings(), "max_generated_nodes")


def decoder(rows, syndrome, config, probabilities=None):
    probabilities = probabilities or [.1] * max((i for row in rows for i in row), default=-1).__add__(1)
    native = native_hybrid()
    instance = native.SearchBPDecoder(rows, len(probabilities), probabilities, [], config)
    result = instance.decode(syndrome)
    return result, instance.summary(result), instance.export_telemetry()


def test_beam_width_is_the_per_cycle_admission_width_and_visit_work_is_fixed():
    rows = [[3, 4], [0, 3, 4, 5], [1, 2, 4, 5], [0, 1, 2, 5]]
    config = settings(cycles=1, width=2, max_iteration=3)
    config.set_stop_mode("bounded_improve")
    result, summary, events = decoder(rows, [1, 0, 1, 0], config)
    updates = events["bp_updates"]
    assert 0 < len(updates) <= config.beam_width
    assert [row["quota"] for row in updates] == [3] * len(updates)
    assert all(row["actual_iterations"] <= 3 for row in updates)
    assert summary["bp_summary"]["admissions"] <= config.beam_width
    assert summary["bp_summary"]["retained_final"] <= config.beam_width
    assert summary["bp_summary"]["hard_fixations"] == len(updates)
    assert all(row["fixed_assignment_violations_after"] == 0 for row in updates)
    assert result.valid


def test_retained_hard_bp_state_continues_and_ancestor_state_can_seed_descendant():
    rows = [[0, 3, 6], [1, 6], [0, 1, 6], [3, 4], [3, 5]]
    syndrome = [0, 1, 0, 1, 1]
    config = settings(cycles=3, width=2, max_iteration=2)
    config.set_stop_mode("bounded_improve"); config.post_solution_cycles = 3
    _, _, events = decoder(rows, syndrome, config)
    updates = events["bp_updates"]
    assert any(row["donor_kind"] in ("own", "ancestor") for row in updates)
    assert all(row["fixed_assignment_violations_after"] == 0 for row in updates)

    cold = settings(cycles=3, width=2, max_iteration=2)
    cold.set_stop_mode("bounded_improve"); cold.post_solution_cycles = 3
    cold.set_inheritance("cold")
    _, _, cold_events = decoder(rows, syndrome, cold)
    assert not any(row["donor_kind"] == "ancestor" for row in cold_events["bp_updates"])


def test_zero_iteration_does_not_admit_and_zero_cycles_calls_direct_cs0():
    config = settings(cycles=1, max_iteration=0)
    _, summary, events = decoder([[2, 3], [0, 1], []], [1, 1, 0], config)
    assert not events["patterns"] and not events["bp_updates"]
    assert summary["bp_summary"]["admissions"] == summary["bp_summary"]["actual_iterations"] == 0

    direct = settings(cycles=0, expansions=0, width=2, max_iteration=4)
    result, summary, events = decoder([[0, 1], [1, 2]], [1, 1], direct, [.1] * 3)
    assert result.valid and summary["osd_entered"] and len(events["osd_calls"]) == 1
    assert summary["search_summary"]["root_nodes"] == 0


def test_repeatability_and_no_cross_shot_state():
    config = settings(cycles=2, width=2, max_iteration=4)
    config.set_stop_mode("bounded_improve"); config.post_solution_cycles = 2
    native = native_hybrid()
    instance = native.SearchBPDecoder([[2, 3], [0, 1], []], 4, [.1] * 4, [[0]], config)
    first = instance.decode([1, 1, 0]); first_summary = instance.summary(first)
    first_events = instance.export_telemetry()
    assert first.valid and math.isfinite(first.cost)
    assert instance.decode([0, 0, 0]).correction == [0, 0, 0, 0]
    repeated = instance.decode([1, 1, 0])
    assert repeated.correction == first.correction
    assert instance.summary(repeated) == first_summary
    assert instance.export_telemetry() == first_events


def test_native_column_export_matches_compatibility_rows():
    config = settings(cycles=2, width=2, max_iteration=3)
    native = native_hybrid()
    instance = native.SearchBPDecoder([[0, 1], [1, 2]], 3, [.1] * 3, [[0]], config)
    result = instance.decode([1, 1])
    assert result.valid
    rows = instance.export_telemetry()
    columns = instance.export_telemetry_columns()
    assert set(columns) == set(rows)
    for name, expected in rows.items():
        actual = columns[name]
        assert set(actual) == (set(expected[0]) if expected else set())
        rebuilt = [
            {field: values[index] for field, values in actual.items()}
            for index in range(len(expected))
        ]
        assert rebuilt == expected
