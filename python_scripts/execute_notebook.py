"""Execute the analysis notebook using this interpreter and explicit saved run(s)."""
from __future__ import annotations
import argparse
from pathlib import Path
import tempfile
import json
import os
import sys


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config',help='Analysis YAML')
    parser.add_argument('--run',action='append',required=True,help='Saved run path; repeatable')
    parser.add_argument('--output',required=True,help='New executed .ipynb output path')
    parser.add_argument('--notebook',default=str(Path(__file__).resolve().parents[1]/'notebook/benchmark_analysis.ipynb'))
    args=parser.parse_args()
    from qec_bp_benchmark.config import load_config
    from qec_bp_benchmark.runner import configure_execution
    configure_execution(load_config(args.config))
    import nbformat
    from nbclient import NotebookClient
    from jupyter_client.kernelspec import KernelSpecManager
    from jupyter_client import KernelManager
    output=Path(args.output).resolve(); output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists(): raise FileExistsError(output)
    notebook=nbformat.read(args.notebook,as_version=4)
    notebook.cells.insert(0,nbformat.v4.new_code_cell(
        'CONFIG_PATH = '+repr(str(Path(args.config).resolve()))+'\nRUN_PATHS = '+repr([str(Path(p).resolve()) for p in args.run])))
    # An ephemeral kernelspec explicitly points to the active environment; never
    # depend on the user's global python3 Jupyter registration.
    with tempfile.TemporaryDirectory(prefix='qec-notebook-kernel-') as temporary:
        directory=Path(temporary)/'qec-acceptance'; directory.mkdir()
        (directory/'kernel.json').write_text(json.dumps({'argv':[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}'],
            'display_name':'QEC active environment','language':'python'}))
        manager=KernelSpecManager(kernel_dirs=[temporary],ensure_native_kernel=False)
        kernel=KernelManager(kernel_name='qec-acceptance',kernel_spec_manager=manager,
                             transport='ipc',ip=str(directory/'kernel'))
        client=NotebookClient(notebook,km=kernel,timeout=600,kernel_name='qec-acceptance',
                              resources={'metadata':{'path':str(Path(args.notebook).resolve().parents[1])}})
        client.execute(cleanup_kc=True)
    with output.open('x') as file: nbformat.write(notebook,file)
    print(output,flush=True)


if __name__=='__main__': main()
