import json
import os
from pathlib import Path
import subprocess
import sys
import numpy as np
import pytest
import stim
from qec_bp_benchmark.config import Multipliers, load_config, Config
from qec_bp_benchmark.circuits import make_template, apply_noise, select_z_detectors, operation_inventory
from qec_bp_benchmark.dem import convert_dem
from qec_bp_benchmark.artifacts import prepare_instance, verify_artifact


@pytest.mark.parametrize('family,distance', [('surface',5),('surface',7),('surface',9),('bb72',6)])
@pytest.mark.parametrize('p',[0,.001])
def test_default_physical_instances(family,distance,p):
    t=make_template(family,distance)
    eligible=tuple(sorted((*t.data_qubits,*t.check_sectors)))
    c=apply_noise(t.circuit,p,Multipliers(),eligible)
    view=select_z_detectors(c,t)
    assert {m['sector'] for m in view.detectors if m['selected_id']>=0} == {'Z'}
    assert {m['role'] for m in view.detectors} == {'initial','bulk','final'}
    k=12 if family=='bb72' else 1
    assert c.num_observables == view.circuit.num_observables == k
    assert c.num_measurements == distance*len(t.check_sectors)+len(t.data_qubits)
    assert c.num_measurements == view.circuit.num_measurements
    # Compare exact detector projections of one shared physical measurement record.
    measurements=c.compile_sampler(seed=123).sample(shots=16)
    d,o=c.compile_m2d_converter().convert(measurements=measurements,separate_observables=True)
    ds,os_=view.circuit.compile_m2d_converter().convert(measurements=measurements,separate_observables=True)
    assert np.array_equal(d[:,view.selected_to_full],ds)
    assert np.array_equal(o,os_)
    physical=lambda circuit:[str(op) for op in circuit.flattened() if op.name!='DETECTOR']
    assert physical(c)==physical(view.circuit)
    problem=convert_dem(view.circuit.detector_error_model(decompose_errors=False,approximate_disjoint_errors=False))
    assert problem.A.shape[0]==k
    if p==0:
        assert not d.any() and not o.any() and problem.H.shape[1]==0
    else:
        assert problem.H.shape[1]>0
        assert 'DEPOLARIZE2' in operation_inventory(c)['instructions']
    if family=='bb72':
        assert view.circuit.num_detectors==36*7
        assert c.num_measurements==504
        assert 'CX' in str(c) and 'CZ' in str(c)


def test_round_override():
    for family,d in [('surface',5),('bb72',6)]:
        t=make_template(family,d,2)
        view=select_z_detectors(t.circuit,t)
        assert t.metadata['round_override'] and t.metadata['rounds']==2
        assert max(x['round'] for x in view.detectors)==2


def test_noise_inventory_and_no_duplicates():
    t=stim.Circuit('R 0 2 3\nTICK\nH 0\nTICK\nCX 0 2\nTICK\nMR 0\nM 2 3')
    mu=Multipliers(one_qubit=1,two_qubit=2,idle=3,reset=4,measurement=5)
    c=apply_noise(t,.01,mu,(0,2,3))
    expected=stim.Circuit('R 0 2 3\nX_ERROR(.04) 0 2 3\nTICK\nH 0\nDEPOLARIZE1(.01) 0\nDEPOLARIZE1(.03) 2 3\nTICK\nCX 0 2\nDEPOLARIZE2(.02) 0 2\nDEPOLARIZE1(.03) 3\nTICK\nMR(.05) 0\nM(.05) 2 3\nX_ERROR(.04) 0')
    assert c==expected
    with pytest.raises(ValueError,match='already'):
        apply_noise(c,.01,mu,(0,2,3))
    with pytest.raises(ValueError,match='allocation'):
        apply_noise(t,.01,mu,(0,1,2,3))


def test_reset_basis_and_conflict_ticks():
    c=apply_noise(stim.Circuit('RX 0\nH 0\nMX 0'),.01,Multipliers(),(0,))
    assert c==stim.Circuit('RX 0\nZ_ERROR(.01) 0\nTICK\nH 0\nDEPOLARIZE1(.01) 0\nTICK\nMX(.01) 0')


def test_bad_detector_provenance():
    t=make_template('surface',3)
    c=t.circuit.copy()
    c.append('DETECTOR',[stim.target_rec(-1)])
    with pytest.raises(ValueError):
        select_z_detectors(c,t)


def test_artifact_rebuild(tmp_path):
    data=load_config(Path(__file__).resolve().parents[1]/'config/legacy/smoke.yaml.example').model_dump()
    data['circuit']['cache']=tmp_path
    cfg=Config.model_validate(data)
    path=prepare_instance(cfg,'bb72',6,.001)
    first=verify_artifact(path)
    assert path==prepare_instance(cfg,'bb72',6,.001)
    assert first==verify_artifact(path)
    assert json.loads((path/'instance.json').read_text())['k_Z']==12
    (path/'circuit.stim').write_text('corrupt')
    with pytest.raises(ValueError,match='checksum'):
        prepare_instance(cfg,'bb72',6,.001)


def test_cross_process_bb_schedule():
    code='from qec_bp_benchmark.circuits import make_template; import hashlib; print(hashlib.sha256(str(make_template("bb72",6).circuit).encode()).hexdigest())'
    hashes=[subprocess.check_output([sys.executable,'-c',code],text=True,env={**os.environ,'PYTHONHASHSEED':seed}).strip() for seed in ('1','321')]
    assert hashes[0]==hashes[1]


def test_artifact_load_canonical_problem(tmp_path):
    from qec_bp_benchmark.artifacts import load_problem
    cfg=Config.model_validate({'noise':{'rates':[.001]},'circuit':{'cache':tmp_path}})
    path=prepare_instance(cfg,'surface',3,.001)
    loaded=load_problem(path)
    dem=stim.DetectorErrorModel.from_file(path/'detector_model.dem')
    direct=convert_dem(dem,extraction_options=cfg.dem.model_dump())
    assert loaded.hashes==direct.hashes
    assert np.array_equal(loaded.H.toarray(),direct.H.toarray())
    assert np.array_equal(loaded.A.toarray(),direct.A.toarray())
    assert np.array_equal(loaded.probabilities,direct.probabilities)


def test_incomplete_artifact_refused(tmp_path):
    (tmp_path/'manifest.json').write_text(json.dumps({'schema_version':1,'status':'incomplete','files':{}}))
    with pytest.raises(ValueError,match='incomplete'):
        verify_artifact(tmp_path)
