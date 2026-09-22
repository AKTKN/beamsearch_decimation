"""Bounded simulation scheduler with the minimal result-directory contract."""
from __future__ import annotations

from concurrent.futures import Executor, FIRST_COMPLETED, ProcessPoolExecutor, wait
from datetime import datetime
import json
import multiprocessing
from pathlib import Path
import sys
import threading
import time
from typing import Callable, Iterable, Iterator, MutableMapping, TypeVar

from ..config import SearchBPOutput, load_config, require_available_decoder
from ..identity import content_hash, decoder_identity, sampling_identity
from ..storage import atomic_json
from ..storage.results import ResultStore, ShotChunkBuffer, condition_prefix
from . import configure_execution
from .plan import task_stream
from .worker import initialize, process_batch

TaskType = TypeVar("TaskType")
ResultType = TypeVar("ResultType")


def bounded_results(executor: Executor, tasks: Iterable[TaskType], limit: int,
                    function: Callable[[TaskType], ResultType] = process_batch) -> Iterator[ResultType]:
    """Lazily keep at most ``limit`` submitted/unconsumed tasks."""
    if limit < 1:
        raise ValueError("pending bound must be positive")
    iterator = iter(tasks)
    pending = {}
    exhausted = False
    try:
        while pending or not exhausted:
            while not exhausted and len(pending) < limit:
                try:
                    task = next(iterator)
                except StopIteration:
                    exhausted = True
                    break
                pending[executor.submit(function, task)] = task
            if not pending:
                break
            ready, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in ready:
                del pending[future]
                yield future.result()
    finally:
        for future in pending:
            future.cancel()


def _resolved_run_directory(root: Path, resolved: dict, started: datetime) -> tuple[Path, str]:
    """Return the required minute timestamp plus eight-character config hash."""
    config_hash = content_hash(resolved)
    name = f"{started.strftime('%Y_%m_%d_%H_%M')}_{config_hash[:8]}"
    return root / name, config_hash


def _prepared_instances(config, report) -> list[dict]:
    """Prepare/reuse execution inputs without copying them into the result run."""
    from ..artifacts import prepare_instance

    instances = []
    for code in config.experiment.codes:
        for distance in code.distances:
            rounds = code.rounds or distance
            for rate in config.noise.expanded_rates:
                report(f"Preparing {code.family} d={distance}, R={rounds}, p={rate:g}")
                artifact = prepare_instance(config, code.family, distance, rate, code.rounds)
                metadata = json.loads((artifact / "instance.json").read_text())
                instances.append({
                    "id": metadata["scientific_instance_id"],
                    "artifact": artifact,
                    "metadata": metadata,
                    "prefix": condition_prefix(code.family, distance, rounds, rate,
                                               config.experiment.memory_basis),
                })
    return instances


def _frontier_static_rows(config, run_id: str, sampling_id: str, instances: list[dict],
                          decoders: list[dict]) -> tuple[dict[str, dict], list[dict]]:
    """Build small typed rows stored beside each condition's simulation data."""
    import numpy
    from ..artifacts import load_problem

    conditions = {}
    for instance in instances:
        artifact_path = instance["artifact"]
        artifact = json.loads((artifact_path / "manifest.json").read_text())
        metadata = instance["metadata"]
        problem = load_problem(artifact_path)
        degrees = numpy.diff(problem.H.tocsc().indptr)
        conditions[instance["id"]] = {
            "run_id": run_id,
            "condition_id": instance["id"],
            "family": metadata["family"],
            "distance": metadata["distance"],
            "rounds": metadata["rounds"],
            "physical_rate": metadata["p"],
            "memory_basis": config.experiment.memory_basis,
            "sector": config.experiment.sector,
            "num_data_qubits": metadata["n"],
            "num_detectors": problem.H.shape[0],
            "num_fault_variables": problem.H.shape[1],
            "num_observables": problem.A.shape[0],
            "circuit_sha256": artifact["hashes"]["circuit"],
            "dem_sha256": artifact["hashes"]["dem"],
            "model_sha256": content_hash(problem.hashes),
            "noise_config_sha256": content_hash(metadata["noise"]),
            "sampling_id": sampling_id,
            "model_metadata_path": str(artifact_path / "instance.json"),
            "column_degree_histogram": numpy.bincount(degrees).astype("uint32").tolist(),
        }
    profiles = []
    for detail in decoders:
        decoder = detail["config"]
        profiles.append({
            "run_id": run_id,
            "decoder_id": detail["id"],
            "name": decoder["name"],
            "kind": decoder.get("kind", decoder["profile"]),
            "profile": decoder["profile"],
            "algorithm_version": decoder.get("algorithm_version", decoder["profile"]),
            "resolved_config_sha256": content_hash(decoder),
            "resolved_config_path": "config_resolved.json",
            "native_build_sha256": detail["implementation"]["native_sha256"],
            "source_commit": "not-recorded",
            "dirty_patch_sha256": None,
            "native_threads": 1,
            "v2_telemetry_available": decoder["profile"] == "search_bp",
        })
    return conditions, profiles


def run_benchmark(config_path: str | Path, *, replay_source: str | Path | None = None,
                  verbose: bool = False,
                  _simulation_timings: MutableMapping[str, int] | None = None) -> Path:
    """Execute one finite config and save only Parquet data plus resolved config.

    Result directories use ``YYYY_MM_DD_HH_MM_<config-hash-8>``. A second run
    with the same resolved configuration in the same minute is rejected rather
    than silently overwriting the first. The obsolete manifest-based replay
    workflow is intentionally no longer part of this simplified execution path.
    """
    if replay_source is not None:
        raise ValueError("manifest-based replay is legacy and is not supported by the simplified runner")

    total_started = time.perf_counter_ns()
    phase_started = total_started
    config_path = Path(config_path).resolve()
    config = load_config(config_path)
    for decoder in config.decoders:
        if decoder.enabled:
            require_available_decoder(decoder.profile)
    if _simulation_timings is not None:
        _simulation_timings["configuration"] = time.perf_counter_ns() - phase_started

    setup_wall_start = time.perf_counter_ns()

    def report(message: str) -> None:
        if verbose:
            elapsed = (time.perf_counter_ns() - setup_wall_start) / 1e9
            print(f"[qec {elapsed:.1f}s] {message}", file=sys.stderr, flush=True)

    report(f"Loading backends; config={config_path}")
    phase_started = time.perf_counter_ns()
    execution = configure_execution(config)
    import numpy  # noqa: F401
    import scipy.linalg  # noqa: F401
    import pyarrow as pa
    import stim
    from threadpoolctl import threadpool_limits
    from ..decoders import implementation_identity

    if _simulation_timings is not None:
        _simulation_timings["backend_imports"] = time.perf_counter_ns() - phase_started

    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    resolved = config.resolved()
    started = datetime.now().astimezone()
    directory, config_hash = _resolved_run_directory(config.output.root, resolved, started)
    config.output.root.mkdir(parents=True, exist_ok=True)
    phase_started = time.perf_counter_ns()
    try:
        directory.mkdir(exist_ok=False)
    except FileExistsError as error:
        raise FileExistsError(
            f"result directory already exists for this config and minute: {directory}"
        ) from error
    atomic_json(directory / "config_resolved.json", resolved, exclusive=True)
    (directory / "data").mkdir(exist_ok=False)
    if _simulation_timings is not None:
        _simulation_timings["run_directory_setup"] = time.perf_counter_ns() - phase_started

    try:
        with threadpool_limits(limits=1):
            phase_started = time.perf_counter_ns()
            decoders = []
            for decoder in config.decoders:
                if decoder.enabled:
                    implementation = implementation_identity(decoder.profile)
                    decoders.append({
                        "id": decoder_identity(decoder, implementation),
                        "config": decoder.model_dump(),
                        "implementation": implementation,
                    })
            if len({decoder["id"] for decoder in decoders}) != len(decoders):
                raise ValueError("duplicate semantic decoder configurations")
            report("Enabled decoders: " + ", ".join(item["config"]["name"] for item in decoders))
            if _simulation_timings is not None:
                _simulation_timings["decoder_identity_setup"] = time.perf_counter_ns() - phase_started

            phase_started = time.perf_counter_ns()
            instances = _prepared_instances(config, report)
            if _simulation_timings is not None:
                _simulation_timings["instance_preparation"] = time.perf_counter_ns() - phase_started
            prefixes = {item["id"]: item["prefix"] for item in instances}
            sampling_id = sampling_identity(config, stim.__version__)
            run_id = content_hash({"started": started.isoformat(), "config_hash": config_hash})
            source_hash = content_hash([item["implementation"] for item in decoders])
            context = {"run_id": run_id, "config_hash": config_hash, "source_hash": source_hash,
                       "simulation_benchmark": _simulation_timings is not None}
            tasks = task_stream(tuple((item["id"], str(item["artifact"])) for item in instances),
                                config, sampling_id)
            expected = len(instances) * (
                (config.sampling.shots_per_point + config.sampling.batch_size - 1)
                // config.sampling.batch_size
            )
            total_shots = len(instances) * config.sampling.shots_per_point
            report(f"Plan: {len(instances)} instances, {total_shots} physical shots, "
                   f"{total_shots * len(decoders)} decode rows, {expected} batches; "
                   f"workers={config.execution.workers}, timing={config.timing.mode}; "
                   f"oversubscribed={execution['oversubscribed']}")

            frontier_output = isinstance(config.output, SearchBPOutput)
            compression = config.output.compression
            compression_level = (config.output.parquet.compression_level if frontier_output else None)
            completed_batches = 0
            completed_shots = 0
            seen = set()

            with ResultStore(directory, prefixes,
                             benchmark_timings=_simulation_timings) as store:
                phase_started = time.perf_counter_ns()
                if frontier_output:
                    from ..storage.search_bp_schema import SCHEMAS, table as frontier_table

                    conditions, profiles = _frontier_static_rows(
                        config, run_id, sampling_id, instances, decoders
                    )
                    for instance in instances:
                        condition_id = instance["id"]
                        for name, schema in SCHEMAS.items():
                            store.ensure(condition_id, name, schema, compression=compression,
                                         compression_level=compression_level)
                        store.append(condition_id, "conditions", [conditions[condition_id]],
                                     SCHEMAS["conditions"],
                                     lambda rows: frontier_table("conditions", rows),
                                     compression=compression, compression_level=compression_level)
                        store.append(condition_id, "decoder_profiles", profiles,
                                     SCHEMAS["decoder_profiles"],
                                     lambda rows: frontier_table("decoder_profiles", rows),
                                     compression=compression, compression_level=compression_level)
                else:
                    from ..storage.schema import DECODER_PHASES, DECODES_V2, HYBRID_ROUNDS, SAMPLES

                    schemas = {"samples": SAMPLES, "decodes": DECODES_V2}
                    if config.timing.profiling == "phases":
                        schemas.update(hybrid_rounds=HYBRID_ROUNDS, decoder_phases=DECODER_PHASES)
                    for condition_id in prefixes:
                        for name, schema in schemas.items():
                            store.ensure(condition_id, name, schema, compression=compression)
                if _simulation_timings is not None:
                    _simulation_timings["static_output_setup"] = (
                        _simulation_timings.get("static_output_setup", 0)
                        + time.perf_counter_ns() - phase_started
                    )

                def write_frontier_group(message: dict) -> None:
                    from ..storage.search_bp_schema import SCHEMAS, table as frontier_table
                    condition_id = message["condition_id"]
                    for name, columns in message["tables"].items():
                        store.append(condition_id, name, columns, SCHEMAS[name],
                                     lambda values, dataset=name: frontier_table(dataset, values),
                                     compression=compression,
                                     compression_level=compression_level)

                frontier_buffer = (ShotChunkBuffer(
                    config.output.parquet.shots_per_flush, write_frontier_group
                ) if frontier_output else None)

                def write_frontier_chunk(message: dict) -> None:
                    assert frontier_buffer is not None
                    frontier_buffer.append(message)

                def consume(result):
                    nonlocal completed_batches, completed_shots
                    consume_started = time.perf_counter_ns()
                    storage_before = sum(_simulation_timings.get(name, 0) for name in (
                        "parquet_writer_open", "arrow_table_conversion", "parquet_write",
                        "parquet_writer_close"
                    )) if _simulation_timings is not None else 0
                    task = result["task"]
                    key = (task.instance_id, task.batch_id)
                    if key in seen:
                        raise ValueError("duplicate task completion")
                    if frontier_output:
                        if result["frontier_tables"] is not None:
                            write_frontier_chunk({"condition_id": task.instance_id,
                                                  "tables": result["frontier_tables"]})
                    else:
                        from ..storage.schema import DECODER_PHASES, DECODES_V2, HYBRID_ROUNDS, SAMPLES, table

                        batch_rows = {"samples": result["samples"], "decodes": result["decodes"]}
                        batch_schemas = {"samples": SAMPLES, "decodes": DECODES_V2}
                        if config.timing.profiling == "phases":
                            batch_rows.update(hybrid_rounds=result["hybrid_rounds"],
                                              decoder_phases=result["decoder_phases"])
                            batch_schemas.update(hybrid_rounds=HYBRID_ROUNDS,
                                                 decoder_phases=DECODER_PHASES)
                        for name, rows in batch_rows.items():
                            schema = batch_schemas[name]
                            store.append(task.instance_id, name, rows, schema,
                                         lambda values, selected=schema: table(values, selected),
                                         compression=compression)
                    seen.add(key)
                    completed_batches += 1
                    completed_shots += task.count
                    if verbose:
                        sample = result["progress"]
                        report(f"Saved batch {completed_batches}/{expected} "
                               f"({100 * completed_batches / expected:.1f}%); "
                               f"shots={completed_shots}/{total_shots}; "
                               f"{sample['family']} d={sample['distance']}, "
                               f"p={sample['physical_p']:g}, batch_id={task.batch_id}")
                    if _simulation_timings is not None:
                        for name, duration in (result.get("simulation_timings") or {}).items():
                            key = "worker_" + name
                            _simulation_timings[key] = _simulation_timings.get(key, 0) + duration
                        storage_after = sum(_simulation_timings.get(name, 0) for name in (
                            "parquet_writer_open", "arrow_table_conversion", "parquet_write",
                            "parquet_writer_close"
                        ))
                        _simulation_timings["parent_batch_bookkeeping"] = (
                            _simulation_timings.get("parent_batch_bookkeeping", 0)
                            + max(0, time.perf_counter_ns() - consume_started
                                  - (storage_after - storage_before))
                        )

                report("Starting decoding; progress updates after each saved batch")
                worker_config = config.model_dump(mode="json")
                if config.config_schema_version is not None:
                    worker_config["config_schema_version"] = config.config_schema_version
                execution_started = time.perf_counter_ns()
                if config.execution.workers == 1:
                    initialize(worker_config, context)
                    for task in tasks:
                        consume(process_batch(
                            task, chunk_sink=write_frontier_chunk if frontier_output else None
                        ))
                else:
                    mp_context = multiprocessing.get_context("spawn")
                    stream_queue = mp_context.Queue(maxsize=max(2, 2 * config.execution.workers)) if frontier_output else None
                    stream_errors: list[BaseException] = []
                    consumer_thread = None
                    if stream_queue is not None:
                        def drain_stream() -> None:
                            while True:
                                message = stream_queue.get()
                                if message is None:
                                    return
                                if stream_errors:
                                    continue
                                try:
                                    write_frontier_chunk(message)
                                except BaseException as error:
                                    stream_errors.append(error)
                        consumer_thread = threading.Thread(target=drain_stream,
                                                           name="qec-parquet-writer")
                        consumer_thread.start()
                    try:
                        with ProcessPoolExecutor(
                            max_workers=config.execution.workers,
                            mp_context=mp_context,
                            initializer=initialize,
                            initargs=(worker_config, context, stream_queue),
                        ) as executor:
                            for result in bounded_results(executor, tasks, config.execution.max_pending):
                                consume(result)
                    finally:
                        if stream_queue is not None:
                            stream_queue.put(None)
                            assert consumer_thread is not None
                            consumer_thread.join()
                            stream_queue.close()
                            stream_queue.join_thread()
                    if stream_errors:
                        raise stream_errors[0]
                if frontier_buffer is not None:
                    frontier_buffer.flush_all()
                if len(seen) != expected:
                    raise ValueError("incomplete task count")
                if _simulation_timings is not None:
                    _simulation_timings["batch_execution_and_consumption"] = (
                        time.perf_counter_ns() - execution_started
                    )

            report(f"Complete: {completed_shots} physical shots, "
                   f"{completed_shots * len(decoders)} decode rows; {directory}")
    except BaseException as error:
        report(f"Failed: {type(error).__name__}: {error}; partial data retained at {directory}")
        if hasattr(error, "add_note"):
            error.add_note(f"Partial data retained at {directory}")
        raise
    if _simulation_timings is not None:
        _simulation_timings["end_to_end"] = time.perf_counter_ns() - total_started
    return directory
