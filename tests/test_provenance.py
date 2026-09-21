import hashlib
import json
from pathlib import Path
import zipfile
from qec_bp_benchmark.provenance import ROOT,repository_state


def test_git_worktree_and_dirty_bytes():
    worktree=ROOT/'external_lib/pristine_ldpc_source'
    result=repository_state(worktree)
    assert result['git_metadata_kind']=='file'
    assert result['commit']=='d3429964cd4ffe1abfc041c6ec8b8425cb174f40'
    state=repository_state(ROOT/'external_lib/ldpc')
    assert state['dirty'] and state['branch']=='screened-decimation-bp'
    assert repository_state(ROOT/'simulation_data')['commit'] is None


def test_fork_patch_restores_ignored_binding_in_pristine_worktree(tmp_path):
    """A --check alone cannot detect a patch that silently omitted an ignored file."""
    import subprocess
    fork=ROOT/'external_lib/ldpc'; worktree=tmp_path/'pristine'
    subprocess.run(['git','-C',str(fork),'worktree','add','--detach',str(worktree),
                    'd3429964cd4ffe1abfc041c6ec8b8425cb174f40'],check=True,capture_output=True)
    try:
        subprocess.run(['git','-C',str(worktree),'apply',str(ROOT/'external_lib/patches/ldpc.patch')],check=True)
        from ldpc.hybrid_bp import SOURCE_FILES
        for relative in (*SOURCE_FILES, 'src_cpp/reference_bp.hpp','src_python/ldpc/reference_bp/bindings.cpp',
                         'src_python/ldpc/reference_bp/__init__.py','setup_reference.py'):
            assert (worktree/relative).read_bytes()==(fork/relative).read_bytes()
    finally:
        subprocess.run(['git','-C',str(fork),'worktree','remove','--force',str(worktree)],check=True)
