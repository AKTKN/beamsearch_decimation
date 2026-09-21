"""Lazy immutable physical batch layout, independent of scheduling and decoders."""
from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Iterator
from ..config import Config

SEED_RECIPE='sha256-instance/SeedSequence/stream-tag/batch/v1'


def batch_seed(master: int, instance_id: str, batch_id: int, stream: str='physical') -> int:
    """Derive exact uint64 seed; numerical import occurs only after runner bootstrap."""
    import numpy as np
    digest=hashlib.sha256((instance_id+'\0'+stream).encode()).digest()
    words=np.frombuffer(digest,dtype='<u4').tolist()
    return int(np.random.SeedSequence([master,*words,batch_id]).generate_state(1,dtype=np.uint64)[0])


@dataclass(frozen=True)
class BatchTask:
    """Picklable metadata only; offset/count are shot indices, seed is uint64."""
    instance_id: str
    artifact: str
    sampling_id: str
    batch_id: int
    offset: int
    count: int
    seed: int
    replay_samples: str | None = None
    replay_sha256: str | None = None


def task_stream(instances: tuple[tuple[str,str],...], config: Config, sampling_id: str) -> Iterator[BatchTask]:
    """Yield tasks without retaining shots or materializing the batch list."""
    for instance_id,artifact in instances:
        for batch_id,offset in enumerate(range(0,config.sampling.shots_per_point,config.sampling.batch_size)):
            yield BatchTask(instance_id,str(Path(artifact)),sampling_id,batch_id,offset,
                min(config.sampling.batch_size,config.sampling.shots_per_point-offset),
                batch_seed(config.sampling.master_seed,instance_id,batch_id))
