"""Identical subprocess workload for pristine and fork ordinary BP-OSD APIs."""
import itertools
import json
import numpy as np
import ldpc
from ldpc import BpOsdDecoder


def workload():
    rng=np.random.default_rng(213)
    matrices=[np.array([[1,1,0],[0,1,1]],dtype=np.uint8),
              np.array([[1,1,1,0,0],[0,1,1,1,0],[1,0,0,1,1]],dtype=np.uint8),
              (rng.random((8,15))<.3).astype(np.uint8)]
    records=[]
    for H in matrices:
        p=rng.uniform(.01,.2,H.shape[1])
        syndromes=[np.asarray(bits,dtype=np.uint8) for bits in itertools.product((0,1),repeat=H.shape[0])] if H.shape[0]<4 else [H@rng.integers(0,2,H.shape[1],dtype=np.uint8)%2 for _ in range(24)]
        for method in ('minimum_sum','product_sum'):
            options=dict(error_channel=p.tolist(),bp_method=method,schedule='parallel',max_iter=30,
                         ms_scaling_factor=1.0,osd_method='OSD_CS',osd_order=10,omp_thread_count=1)
            reused=BpOsdDecoder(H,**options)
            for s in syndromes+list(reversed(syndromes)):
                for decoder in (reused,BpOsdDecoder(H,**options)):
                    e=decoder.decode(s)
                    records.append({'e':e.tolist(),'syndrome':(H@e%2).tolist(),
                                    'converge':bool(decoder.converge),'iter':int(decoder.iter)})
    return {'import_path':ldpc.__file__,'version':ldpc.__version__,'records':records}


if __name__=='__main__':
    print(json.dumps(workload(),sort_keys=True))
