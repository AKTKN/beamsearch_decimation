"""Read and select verified paired datasets without loading a decoder or resampling."""
from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable,Iterator
import pyarrow as pa
import pyarrow.parquet as pq
from qec_bp_benchmark.identity import content_hash
from qec_bp_benchmark.storage import committed_batches,sha256
from qec_bp_benchmark.storage.schema import SAMPLES,DECODES


@dataclass(frozen=True)
class RunData:
    """Owned Arrow tables and detached JSON metadata from one verified run.

    Loading materializes the selected dataset in memory. No numerical decoder state
    is constructed. Incomplete data are opt-in and retain their status in outputs.
    """
    path: Path
    manifest: dict
    samples: pa.Table
    decodes: pa.Table
    instances: dict[str,dict]
    execution_id: str

    def records(self) -> list[dict]:
        """Return detached decode records with analysis grouping/label metadata."""
        profiles={d['id']:d['config'] for d in self.manifest['decoders']}
        output=[]
        for row in self.decodes.to_pylist():
            metadata=self.instances[row['instance_id']]
            comparison={k:v for k,v in metadata.items() if k not in ('p','hashes','scientific_instance_id')}
            output.append(dict(row,comparison_id=content_hash(comparison),execution_id=self.execution_id,
                run_status=self.manifest['status'],decoder_parameters=profiles[row['decoder_id']]))
        return output


def read_manifest(path: str | Path) -> dict:
    """Read version-1 run manifest, rejecting artifacts/unknown/inconsistent statuses."""
    path=Path(path)
    if path.is_dir(): path=path/'manifest.json'
    value=json.loads(path.read_text())
    required={'run_id','instances','config','completed_batches','expected_batches','status','schema_version'}
    if not required<=value.keys() or value['schema_version']!=1 or value['status'] not in ('complete','incomplete'):
        raise ValueError(f'unsupported run manifest: {path}')
    if value['status']=='complete' and value['completed_batches']!=value['expected_batches']:
        raise ValueError('complete run has inconsistent task counts')
    return value


def discover_runs(root: str | Path, *, include_incomplete: bool=False) -> tuple[Path,...]:
    """Discover immediate run children (or a single run); do not scan artifact trees.

    An incomplete run is skipped by default. A malformed candidate run raises rather
    than disappearing silently. Results are sorted by saved UTC time and run ID.
    """
    root=Path(root).resolve()
    candidates=[root] if (root/'manifest.json').is_file() else sorted(p.parent for p in root.glob('*/manifest.json'))
    found=[]
    for path in candidates:
        manifest=read_manifest(path)
        if manifest['status']=='complete' or include_incomplete:
            found.append((manifest.get('created_utc',''),manifest['run_id'],path))
    return tuple(item[2] for item in sorted(found))


def _inside(parent: Path, relative: str) -> Path:
    path=(parent/relative).resolve()
    if not path.is_relative_to(parent.resolve()): raise ValueError('manifest path escapes run directory')
    return path


def load_run(path: str | Path, *, allow_incomplete: bool=False) -> RunData:
    """Validate manifests, artifacts, provenance, schemas, pairing and counts.

    Returns owned samples/decodes Arrow tables; legitimate nulls remain Arrow nulls.
    Raises ValueError/OSError for corruption, duplicate IDs or missing committed data.
    Uncommitted orphan shards are ignored only for opt-in incomplete runs.
    """
    path=Path(path).resolve(); manifest=read_manifest(path)
    if manifest['status']!='complete' and not allow_incomplete:
        raise ValueError('incomplete run requires allow_incomplete=True')
    if 'provenance' not in manifest or 'decoders' not in manifest:
        raise ValueError('run failed before creating analysis-ready provenance')
    provenance=manifest['provenance']
    for name,expected in [('source_provenance/sources.zip',provenance['archive_sha256']),('environment.json',provenance['environment_sha256'])]:
        if sha256(path/name)!=expected: raise ValueError(f'provenance checksum mismatch: {name}')
    hashes=json.loads((path/'source_provenance/source_hashes.json').read_text())
    if content_hash(hashes)!=provenance['source_hash']: raise ValueError('source hash index mismatch')
    resolved=json.loads((path/'config_resolved.json').read_text())
    if resolved!=manifest['config']: raise ValueError('resolved configuration differs from manifest')
    environment=json.loads((path/'environment.json').read_text())
    execution_id=content_hash({'execution':manifest['timing']['execution'],
        'mode':manifest['timing']['mode'],'profiling':manifest['timing']['profiling'],
        'platform':environment['platform'],'cpu_model':environment['cpu_model'],
        'dependencies':environment['dependencies']})
    decoder_ids=tuple(d['id'] for d in manifest['decoders'])
    if not decoder_ids or len(set(decoder_ids))!=len(decoder_ids): raise ValueError('duplicate/empty manifest decoder IDs')
    samples=[]; decodes=[]; instances={}; total_batches=0
    for entry in manifest['instances']:
        iid=entry['instance_id']; folder=_inside(path,entry['directory'])
        if iid in instances: raise ValueError('duplicate instance in manifest')
        if sha256(folder/'manifest.json')!=entry['artifact_manifest_sha256']: raise ValueError('artifact manifest checksum mismatch')
        artifact=json.loads((folder/'manifest.json').read_text())
        if artifact.get('status')!='complete' or artifact.get('schema_version')!=1 or artifact['scientific_instance_id']!=iid:
            raise ValueError('artifact identity/status mismatch')
        for name,expected in artifact['files'].items():
            if sha256(_inside(folder,name))!=expected: raise ValueError(f'artifact checksum mismatch: {name}')
        metadata=json.loads((folder/'instance.json').read_text()); instances[iid]=metadata
        count=shots=0; previous_end=0; expected_batch=0
        for batch in committed_batches(folder):
            count+=1; shots+=batch['count']; total_batches+=1
            if batch['count']<=0 or batch['offset']<previous_end: raise ValueError('invalid/overlapping batch intervals')
            if manifest['status']=='complete' and 'replay' not in manifest:
                if batch['offset']!=previous_end or batch['batch_id']!=expected_batch: raise ValueError('missing batch/shot interval')
            previous_end=batch['offset']+batch['count']; expected_batch+=1
            if set(batch['decoder_ids'])!=set(decoder_ids): raise ValueError('batch decoder set differs from run')
            st=pq.read_table(folder/f'samples/part-{batch["batch_id"]:08d}.parquet')
            dt=pq.read_table(folder/f'decodes/part-{batch["batch_id"]:08d}.parquet')
            if st.num_rows!=batch['count'] or dt.num_rows!=batch['count']*len(decoder_ids): raise ValueError('batch count mismatch')
            for row,expected_index in zip(st.to_pylist(),range(batch['offset'],previous_end)):
                expected={'run_id':manifest['run_id'],'instance_id':iid,'shot_index':expected_index,
                    'batch_id':batch['batch_id'],'batch_seed':batch['seed'],'sampling_id':batch['sampling_id'],
                    'config_hash':content_hash(resolved),'source_hash':provenance['source_hash'],
                    'family':metadata['family'],'distance':metadata['distance'],'n':metadata['n'],
                    'k_Z':metadata['k_Z'],'rounds':metadata['rounds'],'physical_p':metadata['p']}
                if any(row[k]!=v for k,v in expected.items()): raise ValueError('row differs from run/artifact identity')
            for row in dt.to_pylist():
                expected={'timing_mode':resolved['timing']['mode'],'profiling':resolved['timing']['profiling'],
                    'workers':resolved['execution']['workers'],'native_threads':resolved['execution']['native_threads'],
                    'blas_threads':resolved['execution']['blas_threads'],
                    'concurrent_load':manifest['timing']['concurrent_load'],
                    'oversubscribed':manifest['timing']['execution']['oversubscribed']}
                if any(row[k]!=v for k,v in expected.items()): raise ValueError('timing row differs from manifest')
            samples.append(st); decodes.append(dt)
        if manifest['status']=='complete' and (count!=entry['expected_batches'] or shots!=entry['expected_shots']):
            raise ValueError('complete run has missing instance batches/shots')
        if manifest['status']=='complete':
            for sub in ('samples','decodes'):
                if len(list((folder/sub).glob('part-*.parquet')))!=count: raise ValueError('complete run has uncommitted shards')
    if manifest['status']=='complete' and total_batches!=manifest['completed_batches']:
        raise ValueError('complete manifest has missing committed batches')
    return RunData(path,manifest,pa.concat_tables(samples) if samples else pa.Table.from_pylist([],schema=SAMPLES),
        pa.concat_tables(decodes) if decodes else pa.Table.from_pylist([],schema=DECODES),instances,execution_id)


def select_records(runs: Iterable[RunData], *, families: Iterable[str] | None=None,
                   distances: Iterable[int] | None=None, decoder_ids: Iterable[str] | None=None,
                   timing_modes: Iterable[str] | None=None) -> list[dict]:
    """Select explicit values, preserving separate run/scientific/execution identities."""
    filters={key:set(values) for key,values in [('family',families),('distance',distances),
        ('decoder_id',decoder_ids),('timing_mode',timing_modes)] if values is not None}
    selected=[]; seen=set()
    for run in runs:
        for row in run.records():
            if any(row[key] not in values for key,values in filters.items()): continue
            key=(row['run_id'],row['shot_id'],row['decoder_id'])
            if key in seen: raise ValueError('duplicate selected run/shot/decoder')
            seen.add(key); selected.append(row)
    return selected
