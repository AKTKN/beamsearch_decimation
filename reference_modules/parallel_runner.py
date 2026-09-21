"""Bounded CPU process scheduling, independent of storage and plotting."""
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
from collections.abc import Callable, Iterable, Iterator
from multiprocessing import get_context
import pandas as pd
from .config import BatchTask
from .sampling import sample_batch


def completed_batches(tasks: Iterable[BatchTask], num_workers: int,
                      worker: Callable = sample_batch) -> Iterator[tuple[BatchTask, pd.DataFrame]]:
    """Yield completed batches with at most 2*num_workers futures in flight.

    Args:
        tasks: Lazy deterministic task stream.
        num_workers: Positive process count; one executes serially.
        worker: Picklable batch function, injectable for tests.
    Yields:
        Task and its returned moderate-size table, in completion order.
    Raises:
        ValueError: Nonpositive worker count.
        Exception: Worker failures propagate and pending tasks are cancelled.
    Notes:
        Spawn isolates decoder state. Each process caches at most two code pairs.
    """
    if num_workers < 1:
        raise ValueError("num_workers must be positive")
    if num_workers == 1:
        for task in tasks:
            yield task, worker(task)
        return
    iterator = iter(tasks)
    pool = ProcessPoolExecutor(max_workers=num_workers, mp_context=get_context("spawn"))
    pending = {}
    try:
        def submit_next():
            task = next(iterator, None)
            if task is not None:
                pending[pool.submit(worker, task)] = task
        for _ in range(2*num_workers):
            submit_next()
        while pending:
            finished, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in finished:
                task = pending.pop(future)
                result = future.result()
                submit_next()
                yield task, result
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
