import json
import os
from pathlib import Path
import subprocess
import sys


def test_pristine_pinned_bposd_regression():
    root=Path(__file__).resolve().parents[1]
    script=root/'tests/bposd_regression_driver.py'
    pristine=root/'external_lib/pristine_ldpc'
    assert pristine.is_dir(), 'Build/install the pristine pinned wheel first'
    original=json.loads(subprocess.check_output([sys.executable,str(script)],text=True,
                      env={**os.environ,'PYTHONPATH':str(pristine)}))
    fork=json.loads(subprocess.check_output([sys.executable,str(script)],text=True,
                  env={**os.environ,'PYTHONPATH':str(root/'external_lib/ldpc/src_python')}))
    assert pristine in Path(original['import_path']).parents
    assert root/'external_lib/ldpc/src_python' in Path(fork['import_path']).parents
    assert original['version']==fork['version']=='2.4.1'
    assert original['records']==fork['records']
    assert len(fork['records'])==288
