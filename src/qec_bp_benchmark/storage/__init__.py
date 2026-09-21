"""Parent-only atomic paired storage. Incomplete runs expose committed batches only."""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Iterator,Sequence
import uuid


def sha256(path: Path) -> str:
    with Path(path).open('rb') as file: return hashlib.file_digest(file,'sha256').hexdigest()


def _sync_dir(path: Path) -> None:
    fd=os.open(path,os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)


def atomic_json(path: Path, contents: dict, *, exclusive: bool=False) -> None:
    """Publish finite JSON atomically; exclusive mode never replaces existing bytes."""
    payload=(json.dumps(contents,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
    temporary=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('xb') as file: file.write(payload); file.flush(); os.fsync(file.fileno())
        if exclusive: os.link(temporary,path); temporary.unlink()
        else: os.replace(temporary,path)
        _sync_dir(path.parent)
    finally: temporary.unlink(missing_ok=True)


def failure_labels(status: str, syndrome_valid: bool, prediction: Sequence[bool] | None, truth: Sequence[bool]) -> dict:
    """Per-shot block/observable indicators; conditional mismatch excludes failures."""
    failure=status!='SUCCESS' or not syndrome_valid
    if not failure and (prediction is None or len(prediction)!=len(truth)):
        raise ValueError('successful decode must predict every observable')
    mismatch=None if failure else [bool(a!=b) for a,b in zip(prediction,truth)]
    valid_mismatch=False if failure else any(mismatch)
    return {'decoding_failure':failure,'valid_logical_mismatch':valid_mismatch,
            'block_failure':failure or valid_mismatch,'observable_mismatch':mismatch,
            'observable_total_failure':[True]*len(truth) if failure else mismatch}


def validate_pair(samples: list[dict], decodes: list[dict], decoder_ids: tuple[str,...]) -> None:
    """Check exact pairing, semantic nulls, timing units and block failure labels."""
    from .schema import COMMON
    if not decoder_ids or len(set(decoder_ids))!=len(decoder_ids): raise ValueError('empty or duplicate decoder set')
    by_shot={r['shot_id']:r for r in samples}
    if len(by_shot)!=len(samples) or not samples: raise ValueError('empty or duplicate samples')
    seen=set()
    for row in samples:
        if row['num_detectors']<0 or row['k_Z']<1: raise ValueError('invalid sample dimensions')
        if len(row['actual_observables'])!=row['k_Z']: raise ValueError('truth dimension mismatch')
        if len(row['detectors_packed'])!=(row['num_detectors']+7)//8: raise ValueError('packed detector size')
        if row['num_detectors']%8 and row['detectors_packed'][-1]>>(row['num_detectors']%8): raise ValueError('nonzero detector padding')
        if row['shot_id']!=f'{row["instance_id"]}:{row["sampling_id"]}:{row["shot_index"]}': raise ValueError('inconsistent shot identity')
    for row in decodes:
        key=(row['shot_id'],row['decoder_id'])
        if key in seen or row['shot_id'] not in by_shot or row['decoder_id'] not in decoder_ids: raise ValueError('duplicate/unpaired decode')
        seen.add(key); sample=by_shot[row['shot_id']]
        for field in COMMON:
            if sample[field.name]!=row[field.name]: raise ValueError('incompatible paired identities')
        if row['status'] not in ('SUCCESS','DECLARED_FAILURE','INVALID_OUTPUT'): raise ValueError('unknown normalized status')
        labels=failure_labels(row['status'],row['syndrome_valid'],row['prediction'],sample['actual_observables'])
        if any(row[k]!=v for k,v in labels.items()): raise ValueError('inconsistent failure labels')
        if labels['decoding_failure']:
            if row['prediction'] is not None or row['cost'] is not None or row['correction_packed'] is not None: raise ValueError('failure requires null outputs')
        elif row['cost'] is None or not math.isfinite(row['cost']) or row['cost']<0: raise ValueError('success requires finite physical cost')
        if row['cpu_ns']<0 or row['wall_ns']<0: raise ValueError('negative elapsed time')
    if len(seen)!=len(samples)*len(decoder_ids): raise ValueError('missing decoder result')


def commit_batch(instance: Path, batch_id: int, samples: list[dict], decodes: list[dict],
                 decoder_ids: tuple[str,...], compression: str, setup: dict) -> dict:
    """Write two shards then commit marker, never overwriting a shard (even an orphan)."""
    import pyarrow.parquet as pq
    from .schema import SAMPLES,DECODES,table
    validate_pair(samples,decodes,decoder_ids)
    for sub in ('samples','decodes','batch_manifests'): (instance/sub).mkdir(exist_ok=True)
    name=f'part-{batch_id:08d}'
    destinations=[instance/'samples'/f'{name}.parquet',instance/'decodes'/f'{name}.parquet']
    marker=instance/'batch_manifests'/f'{name}.json'
    if any(p.exists() for p in [*destinations,marker]): raise FileExistsError(f'batch {batch_id} already has output')
    tables=[table(samples,SAMPLES),table(decodes,DECODES)]
    files={}
    for target,data in zip(destinations,tables):
        temp=target.with_name('.'+target.name+'.'+uuid.uuid4().hex+'.tmp')
        try:
            pq.write_table(data,temp,compression=None if compression=='none' else compression)
            with temp.open('rb') as file: os.fsync(file.fileno())
            # link provides atomic publication with exclusive destination semantics.
            os.link(temp,target); temp.unlink(); _sync_dir(target.parent)
        finally: temp.unlink(missing_ok=True)
        files[str(target.relative_to(instance))]={'sha256':sha256(target),'rows':data.num_rows}
    manifest={'schema_version':1,'status':'committed','batch_id':batch_id,'files':files,
              'offset':samples[0]['shot_index'],'count':len(samples),'seed':samples[0]['batch_seed'],
              'sampling_id':samples[0]['sampling_id'],'decoder_ids':list(decoder_ids),'setup':setup}
    atomic_json(marker,manifest,exclusive=True)
    return manifest


def committed_batches(instance: Path, *, verify: bool=True) -> Iterator[dict]:
    """Yield only committed pairs; ignore orphan files and validate each checksum/count."""
    import pyarrow.parquet as pq
    from .schema import SAMPLES,DECODES
    for path in sorted((instance/'batch_manifests').glob('part-*.json')):
        batch=json.loads(path.read_text())
        if batch.get('status')!='committed' or batch.get('schema_version')!=1: raise ValueError('invalid batch manifest')
        expected={f'{sub}/part-{batch["batch_id"]:08d}.parquet' for sub in ('samples','decodes')}
        if set(batch['files'])!=expected: raise ValueError('invalid paired shard paths')
        if verify:
            values={}
            for name,detail in batch['files'].items():
                file=instance/name
                if sha256(file)!=detail['sha256']: raise ValueError(f'checksum mismatch: {file}')
                data=pq.read_table(file)
                schema=SAMPLES if name.startswith('samples/') else DECODES
                if not data.schema.equals(schema,check_metadata=True) or data.num_rows!=detail['rows']: raise ValueError('shard schema/count mismatch')
                values[name.split('/')[0]]=data.to_pylist()
            validate_pair(values['samples'],values['decodes'],tuple(batch['decoder_ids']))
        yield batch
