"""Runner bootstrap stays free of NumPy/SciPy/native imports until thread setup."""
import os
from ..config import Config

THREAD_KEYS=('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','BLIS_NUM_THREADS',
             'VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS')


def configure_execution(config: Config) -> dict:
    """Set process thread environment and optional affinity before numerical imports.

    Returns effective CPU availability/oversubscription labels. Invalid CPU affinity
    raises ValueError. The pipeline also constrains already-loaded thread pools.
    """
    for key in THREAD_KEYS:
        os.environ[key]=str(config.execution.native_threads if key=='OMP_NUM_THREADS' else config.execution.blas_threads)
    os.environ['OMP_DYNAMIC']='FALSE'
    os.environ['MKL_DYNAMIC']='FALSE'
    available=sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else list(range(os.cpu_count() or 1))
    if config.execution.affinity is not None:
        if not hasattr(os,'sched_setaffinity') or not set(config.execution.affinity)<=set(available):
            raise ValueError('requested affinity is outside available CPUs or unsupported')
        os.sched_setaffinity(0,config.execution.affinity)
        available=sorted(os.sched_getaffinity(0))
    return {'affinity':available,'oversubscribed':config.execution.workers>len(available),
            'thread_environment':{k:os.environ[k] for k in THREAD_KEYS}}
