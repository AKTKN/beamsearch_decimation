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
    root=Path(__file__).resolve().parents[1]
    parser.add_argument('config',nargs='?',default=str(root/'config/analysis.yaml.example'),help='Analysis YAML')
    parser.add_argument('--run',action='append',required=True,help='Saved run path; repeatable')
    parser.add_argument('--output',required=True,help='New executed .ipynb output path')
    parser.add_argument('--notebook',default=str(root/'notebook/benchmark_analysis.ipynb.example'))
    parser.add_argument('--timeout',type=int,default=600,help='Seconds per cell; -1 disables the limit')
    args=parser.parse_args()
    if args.timeout != -1 and args.timeout <= 0: parser.error('--timeout must be positive or -1')
    from analysis import load_analysis_config
    load_analysis_config(args.config)
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
        client=NotebookClient(notebook,km=kernel,timeout=args.timeout,kernel_name='qec-acceptance',
                              resources={'metadata':{'path':str(root)}})
        client.execute(cleanup_kc=True)
    notebook.metadata['kernelspec']={'name':'search_decimation','display_name':'Python (search_decimation)','language':'python'}
    with output.open('x') as file: nbformat.write(notebook,file)
    print(output,flush=True)


if __name__=='__main__': main()
