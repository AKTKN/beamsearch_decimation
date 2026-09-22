"""Typed search_bp schema and direct saved-data checks."""
import math
from pathlib import Path

import pytest

from qec_bp_benchmark.storage.search_bp_schema import CONTRACT,SCHEMAS,pack_bits,table,unpack_bits


def test_all_normative_datasets_have_explicit_arrow_schemas():
    assert set(SCHEMAS) == set(CONTRACT["datasets"])
    assert len(SCHEMAS) == 14
    assert all(schema.metadata[b"qec_schema"].startswith(b"search_bp_parquet/2/") for schema in SCHEMAS.values())


def test_bit_packing_and_padding_are_strict():
    bits=[1,0,1,1,0,0,0,1,1]
    payload=pack_bits(bits,9)
    assert unpack_bits(payload,9)==[bool(value) for value in bits]
    with pytest.raises(ValueError): unpack_bits(payload[:-1],9)
    with pytest.raises(ValueError): unpack_bits(payload[:-1]+bytes([0xFE]),9)


def test_exact_fields_enums_nonfinite_and_duplicate_keys_rejected():
    row={field.name: None for field in SCHEMAS['conditions']}
    row.update(run_id='r',condition_id='c',family='surface',distance=3,rounds=3,physical_rate=.1,
        memory_basis='Z',sector='Z_checks',num_data_qubits=9,num_detectors=1,num_fault_variables=1,
        num_observables=1,circuit_sha256='a',dem_sha256='b',model_sha256='c',noise_config_sha256='d',
        sampling_id='s',model_metadata_path='models/c/metadata.json',column_degree_histogram=[1])
    assert table('conditions',[row]).num_rows==1
    columns={name:[value] for name,value in row.items()}
    assert table('conditions',columns).to_pylist()==[row]
    with pytest.raises(ValueError): table('conditions',{**columns,'distance':[3,4]})
    with pytest.raises(ValueError): table('conditions',[row,row])
    with pytest.raises(ValueError): table('conditions',[{**row,'family':'future'}])
    with pytest.raises(ValueError): table('conditions',[{**row,'physical_rate':math.nan}])


def test_committed_smoke_run_is_inventory_readable_if_present():
    root=Path(__file__).resolve().parents[1]/'assets/runs'
    candidates=[]
    for path in root.glob('*/manifest.json'):
        import json
        manifest=json.loads(path.read_text())
        inventory=path.parent/'inventory/committed_batches.json'
        if manifest.get('schema_version')==3 and manifest.get('status')=='complete' and inventory.exists():
            committed=json.loads(inventory.read_text())
            # Early development smoke artifacts predated static-count publication.
            if committed['datasets']['conditions']['rows']:
                candidates.append(path.parent)
    if not candidates: pytest.skip('no saved v2 smoke run in this checkout')
    from qec_bp_benchmark.storage.search_bp import verify
    checked=verify(sorted(candidates)[-1])
    assert checked['rows']['shot_inputs']>0
    assert checked['rows']['decode_results']>=checked['rows']['shot_inputs']
