"""Atomic separate-dataset writer and inventory validator for search_bp runs."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import uuid

from qec_bp_benchmark.storage import atomic_json, sha256
from .search_bp_schema import PARTITIONS, PRIMARY_KEYS, SCHEMAS, SCHEMA_VERSION, table, unpack_bits

DATASETS = tuple(SCHEMAS)


def _partition_path(name: str, rows: list[dict], batch_id: int) -> Path:
    path = Path("tables") / name
    for column in PARTITIONS[name]:
        values = {row[column] for row in rows}
        if len(values) != 1:
            raise ValueError(f"one shard must have one {name}.{column} value")
        path /= f"{column}={next(iter(values))}"
    return path / f"part-{batch_id:08d}.parquet"


def _groups(name: str, rows: list[dict]) -> list[list[dict]]:
    partitions = PARTITIONS[name]
    if not rows or not partitions:
        return [rows] if rows else []
    grouped: dict[tuple, list[dict]] = {}
    for row in rows:
        grouped.setdefault(tuple(row[field] for field in partitions), []).append(row)
    return [grouped[key] for key in sorted(grouped)]


def commit_batch(run: Path, batch_id: int, rows: dict[str, list[dict]], *, compression: str,
                 compression_level: int, setup: dict, condition_id: str, offset: int, count: int,
                 decoder_ids: tuple[str, ...]) -> dict:
    """Validate, publish immutable shards, then atomically append one batch inventory."""
    import pyarrow.parquet as pq
    if set(rows) != set(DATASETS) - {"conditions", "decoder_profiles"}:
        raise ValueError("search_bp batch must declare every non-static dataset")
    temporary: list[tuple[Path, Path, int, str, tuple | None, tuple | None]] = []
    try:
        for name in DATASETS:
            if name in ("conditions", "decoder_profiles"):
                continue
            for group in _groups(name, rows[name]):
                data = table(name, group)
                relative = _partition_path(name, group, batch_id)
                target = run / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                temp = target.with_name("." + target.name + "." + uuid.uuid4().hex + ".tmp")
                kwargs = {"compression": None if compression == "none" else compression}
                if compression == "zstd": kwargs["compression_level"] = compression_level
                pq.write_table(data, temp, **kwargs)
                check = pq.ParquetFile(temp).read()
                if not check.schema.equals(SCHEMAS[name], check_metadata=True) or check.num_rows != len(group):
                    raise ValueError(f"invalid staged {name} shard")
                keys = [tuple(row[field] for field in PRIMARY_KEYS[name]) for row in group]
                temporary.append((temp, target, len(group), name, min(keys) if keys else None, max(keys) if keys else None))
        files = {}
        for temp, target, size, name, first, last in temporary:
            if target.exists():
                raise FileExistsError(target)
            os.replace(temp, target)
            files[str(target.relative_to(run))] = {"dataset": name, "rows": size, "sha256": sha256(target),
                "schema_id": SCHEMAS[name].metadata[b"qec_schema"].decode(),
                "first_key": first, "last_key": last}
        inventory_path = run / "inventory" / "committed_batches.json"
        inventory_path.parent.mkdir(parents=True, exist_ok=True)
        if inventory_path.exists():
            import json
            inventory = json.loads(inventory_path.read_text())
        else:
            inventory = {"schema_version": SCHEMA_VERSION, "batches": [],
                         "datasets": {name: {"rows": 0, "shards": 0} for name in DATASETS}}
        if any(item["condition_id"] == condition_id and item["batch_id"] == batch_id for item in inventory["batches"]):
            raise ValueError("duplicate committed batch")
        entry = {"condition_id": condition_id, "batch_id": batch_id, "offset": offset, "count": count,
                 "decoder_ids": list(decoder_ids), "files": files, "setup": setup, "status": "committed"}
        inventory["batches"].append(entry)
        inventory["batches"].sort(key=lambda item: (item["condition_id"], item["batch_id"]))
        for detail in files.values():
            item = inventory["datasets"][detail["dataset"]]
            item["rows"] += detail["rows"]; item["shards"] += 1
        atomic_json(inventory_path, inventory)
        return entry
    finally:
        for temp, *_ in temporary:
            temp.unlink(missing_ok=True)


def write_static(run: Path, rows: dict[str, list[dict]], *, compression: str,
                 compression_level: int) -> dict:
    """Write conditions and decoder profiles once with strict schemas."""
    import pyarrow.parquet as pq
    details = {}
    for name in ("conditions", "decoder_profiles"):
        data = table(name, rows[name]);target = run / "tables" / name / "part-00000000.parquet"
        target.parent.mkdir(parents=True, exist_ok=True)
        kwargs = {"compression": None if compression == "none" else compression}
        if compression == "zstd": kwargs["compression_level"] = compression_level
        pq.write_table(data, target, **kwargs)
        details[name] = {"rows": data.num_rows, "sha256": sha256(target)}
    inventory = {"schema_version": SCHEMA_VERSION, "batches": [],
                 "datasets": {name: {"rows": 0, "shards": 0} for name in DATASETS}}
    for name, detail in details.items():
        inventory["datasets"][name] = {"rows": detail["rows"], "shards": 1}
    path = run / "inventory" / "committed_batches.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(path, inventory, exclusive=True)
    return details


def verify(run: Path) -> dict:
    """Verify hashes, schemas, keys, foreign keys, packed vectors and counters.

    Only inventory-listed shards participate.  This makes an interrupted unpublished
    batch invisible while making every published missing/corrupt shard a hard error.
    """
    import json
    import pyarrow.parquet as pq
    inventory = json.loads((run / "inventory" / "committed_batches.json").read_text())
    if inventory.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported search_bp inventory")
    seen = {name: set() for name in DATASETS}
    rows = {name: [] for name in DATASETS}
    counts = {name: 0 for name in DATASETS}
    for entry in inventory["batches"]:
        if entry.get("status") != "committed":
            raise ValueError("uncommitted batch in inventory")
        for relative, expected in entry["files"].items():
            path = run / relative
            if sha256(path) != expected["sha256"]:
                raise ValueError(f"checksum mismatch: {relative}")
            name = expected["dataset"];data = pq.ParquetFile(path).read()
            if not data.schema.equals(SCHEMAS[name], check_metadata=True) or data.num_rows != expected["rows"]:
                raise ValueError(f"schema/count mismatch: {relative}")
            for row in data.to_pylist():
                key = tuple(row[field] for field in PRIMARY_KEYS[name])
                if key in seen[name]: raise ValueError(f"duplicate {name} key")
                seen[name].add(key)
                rows[name].append(row)
            counts[name] += data.num_rows
    for name in ("conditions", "decoder_profiles"):
        path = run / "tables" / name / "part-00000000.parquet";data = pq.ParquetFile(path).read()
        if not data.schema.equals(SCHEMAS[name], check_metadata=True): raise ValueError(f"static schema mismatch: {name}")
        counts[name] = data.num_rows
        rows[name] = data.to_pylist()
        seen[name] = {tuple(row[field] for field in PRIMARY_KEYS[name]) for row in rows[name]}
        if len(seen[name]) != len(rows[name]): raise ValueError(f"duplicate {name} key")
    if counts != {name: inventory["datasets"][name]["rows"] for name in DATASETS}:
        raise ValueError("inventory dataset counts disagree with committed shards")
    _validate_relations(rows, seen)
    return {"rows": counts, "batches": len(inventory["batches"])}


def _validate_relations(rows: dict[str, list[dict]], seen: dict[str, set[tuple]]) -> None:
    """Apply the machine-readable contract's cross-dataset invariants."""
    conditions = {(row["run_id"], row["condition_id"]): row for row in rows["conditions"]}
    profiles = {(row["run_id"], row["decoder_id"]): row for row in rows["decoder_profiles"]}
    shots = {(row["run_id"], row["condition_id"], row["shot_id"]): row for row in rows["shot_inputs"]}
    decodes = {(row["run_id"], row["condition_id"], row["shot_id"], row["decoder_id"]): row
               for row in rows["decode_results"]}
    for condition in rows["conditions"]:
        if sum(condition["column_degree_histogram"]) != condition["num_fault_variables"]:
            raise ValueError("column-degree histogram does not cover all fault variables")
    for key, shot in shots.items():
        condition = conditions.get(key[:2])
        if condition is None: raise ValueError("shot input without condition")
        if shot["sampling_id"] != condition["sampling_id"]:
            raise ValueError("shot and condition sampling identities disagree")
        unpack_bits(shot["syndrome_packed"], condition["num_detectors"])
        unpack_bits(shot["true_observables_packed"], condition["num_observables"])
        if shot["syndrome_weight"] != sum(unpack_bits(shot["syndrome_packed"], condition["num_detectors"])):
            raise ValueError("syndrome weight disagrees with packed syndrome")
    enabled = {(row["run_id"], row["decoder_id"]) for row in rows["decoder_profiles"]}
    expected = {(run, condition, shot, decoder) for run, condition, shot in shots
                for profile_run, decoder in enabled if profile_run == run}
    if set(decodes) != expected:
        raise ValueError("decode results do not form one complete shot/decoder pairing")
    for key, result in decodes.items():
        if key[:3] not in shots or (key[0], key[3]) not in profiles:
            raise ValueError("decode result has an invalid foreign key")
        condition = conditions[key[:2]]
        valid = result["syndrome_valid"]
        if (result["status"] == "valid") != valid:
            raise ValueError("decode status and syndrome validity disagree")
        if result["block_failure"] != ((not valid) or bool(result["logical_mismatch"])):
            raise ValueError("decode block-failure label is inconsistent")
        if valid:
            required = ("correction_packed", "predicted_observables_packed", "physical_cost", "logical_mismatch")
            if any(result[field] is None for field in required): raise ValueError("valid decode lacks result data")
            unpack_bits(result["correction_packed"], condition["num_fault_variables"])
            unpack_bits(result["predicted_observables_packed"], condition["num_observables"])
            unpack_bits(result["observable_mismatch_packed"], condition["num_observables"])
        elif result["logical_mismatch"] is not None or result["observable_mismatch_packed"] is not None:
            raise ValueError("invalid decode has a logical label")
    v2 = {key for key, result in decodes.items() if profiles[(key[0], key[3])]["v2_telemetry_available"]}
    for name in ("search_summary", "bp_summary"):
        if seen[name] != v2: raise ValueError(f"{name} must have exactly one row for every v2 decode")
    grouped = {key: {name: [] for name in DATASETS} for key in v2}
    for name in DATASETS:
        if name in ("conditions", "decoder_profiles", "shot_inputs", "decode_results"):
            continue
        for row in rows[name]:
            key = (row["run_id"], row["condition_id"], row["shot_id"], row["decoder_id"])
            if name == "phase_timings" and key in decodes:
                if key in grouped: grouped[key][name].append(row)
                continue
            if key not in grouped: raise ValueError(f"{name} row without v2 decode")
            grouped[key][name].append(row)
    for key, data in grouped.items():
        search = data["search_summary"][0]; bp = data["bp_summary"][0]
        cycles = sorted(data["cycles"], key=lambda row: row["cycle_index"])
        updates = {row["update_id"]: row for row in data["bp_updates"]}
        patterns = {row["node_id"]: row for row in data["patterns"]}
        events = {row["solution_event_id"]: row for row in data["solution_events"]}
        if [row["cycle_index"] for row in cycles] != list(range(len(cycles))):
            raise ValueError("cycle indices are not contiguous")
        if search["root_nodes"] + sum(row["generated_actual"] for row in cycles) != search["generated_nodes"]:
            raise ValueError("generated-node accounting mismatch")
        if sum(row["expansions_actual"] for row in cycles) != search["expanded_nodes"]:
            raise ValueError("expansion accounting mismatch")
        if len(cycles) != bp["cycles_started"] or len(patterns) != bp["admissions"] or len(updates) != bp["evaluated_visits"]:
            raise ValueError("BP row counts disagree with summary")
        if sum(row["admissions_actual"] for row in cycles) != bp["admissions"] or sum(row["visits_actual"] for row in cycles) != bp["evaluated_visits"]:
            raise ValueError("cycle admissions/visits disagree with BP summary")
        if sum(row["allocated_tokens"] for row in cycles) != bp["planned_iteration_tokens"]:
            raise ValueError("planned iteration accounting mismatch")
        actual = sum(row["actual_iterations"] for row in updates.values())
        if actual != bp["actual_iterations"] or actual != sum(row["bp_actual_iterations"] for row in cycles):
            raise ValueError("actual iteration accounting mismatch")
        condition = conditions[key[:2]]
        for pattern in patterns.values():
            zeros, ones = pattern["fixed_zero_indices"], pattern["fixed_one_indices"]
            if zeros != sorted(set(zeros)) or ones != sorted(set(ones)) or set(zeros) & set(ones):
                raise ValueError("pattern assignment is not canonical")
            if any(index >= condition["num_fault_variables"] for index in zeros+ones):
                raise ValueError("pattern assignment index is outside the model")
            if pattern["ones_depth"] != len(ones): raise ValueError("pattern depth mismatch")
        for update in updates.values():
            if update["node_id"] not in patterns: raise ValueError("BP update without admitted pattern")
            if update["actual_iterations"] > update["quota"]:
                raise ValueError("BP update exceeds its quota")
            donor = update["donor_update_id"]
            if update["donor_kind"] in ("cold_seed", "cold_reset"):
                if donor is not None or update["donor_node_id"] is not None or update["donor_lineage_iterations"] != 0:
                    raise ValueError("cold BP update has donor provenance")
            elif donor not in updates or updates[donor]["cycle_index"] >= update["cycle_index"] or not updates[donor]["state_usable"]:
                raise ValueError("BP donor is not a usable earlier-cycle update")
            elif update["donor_kind"] == "own" and update["donor_node_id"] != update["node_id"]:
                raise ValueError("own BP donor must have the same node")
            elif update["donor_kind"] == "ancestor" and update["donor_node_id"] == update["node_id"]:
                raise ValueError("ancestor BP donor must be strict")
        membership_by_cycle: dict[int, list[dict]] = {}
        for member in data["bp_beam_membership"]:
            membership_by_cycle.setdefault(member["cycle_index"], []).append(member)
            update = updates.get(member["latest_update_id"])
            if update is None or not update["state_usable"] or update["node_id"] != member["node_id"]:
                raise ValueError("beam membership has invalid update provenance")
        for cycle in cycles:
            members = sorted(membership_by_cycle.get(cycle["cycle_index"], []), key=lambda row: row["retention_rank"])
            if len(members) != cycle["beam_after"] or [row["retention_rank"] for row in members] != list(range(len(members))):
                raise ValueError("beam membership does not match cycle")
        for event in events.values():
            unpack_bits(event["correction_packed"], condition["num_fault_variables"])
            unpack_bits(event["predicted_observables_packed"], condition["num_observables"])
            unpack_bits(event["observable_mismatch_packed"], condition["num_observables"])
        result = decodes[key]
        winner = result["winner_solution_event_id"]
        if winner is not None:
            if (winner not in events or events[winner]["correction_packed"] != result["correction_packed"] or
                    events[winner]["predicted_observables_packed"] != result["predicted_observables_packed"] or
                    events[winner]["logical_mismatch"] != result["logical_mismatch"]):
                raise ValueError("winner event does not match final result")
        if data["search_nodes"] and len(data["search_nodes"]) != search["generated_nodes"]:
            raise ValueError("search-node trace does not cover every generated node")
        for call in data["osd_calls"]:
            if call["solution_event_id"] is not None and call["solution_event_id"] not in events:
                raise ValueError("OSD call references a missing solution event")
        if result["profiling"] == "phases":
            phase_cpu = sum(row["exclusive_cpu_ns"] for row in data["phase_timings"])
            phase_wall = sum(row["exclusive_wall_ns"] for row in data["phase_timings"])
            if phase_cpu != result["service_cpu_ns"] or phase_wall != result["service_wall_ns"]:
                raise ValueError("exclusive phases do not sum to service time")
    phase_groups: dict[tuple, list[dict]] = {}
    for row in rows["phase_timings"]:
        key=(row["run_id"],row["condition_id"],row["shot_id"],row["decoder_id"])
        phase_groups.setdefault(key,[]).append(row)
    for key,result in decodes.items():
        phase_rows=phase_groups.get(key,[])
        if result["profiling"] == "phases":
            if not phase_rows or sum(row["exclusive_cpu_ns"] for row in phase_rows) != result["service_cpu_ns"] or sum(row["exclusive_wall_ns"] for row in phase_rows) != result["service_wall_ns"]:
                raise ValueError("phase rows do not exactly account for decode service")
        elif phase_rows:
            raise ValueError("phase rows emitted while profiling is disabled")
