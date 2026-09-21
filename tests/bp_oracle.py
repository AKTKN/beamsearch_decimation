"""Test-only scalar residual-matrix flooding oracle; never production imported."""
from collections import deque
import math
import numpy as np


def scalar_bp(H, p, s, T=30, limit=25, window=8, fixed=None):
    H=np.asarray(H,dtype=np.uint8)
    s=np.asarray(s,dtype=np.uint8).copy()
    n=H.shape[1]
    fixed=np.full(n,-1) if fixed is None else np.asarray(fixed)
    free=np.flatnonzero(fixed<0)
    fixed_one=np.flatnonzero(fixed==1)
    # Explicit residual matrix, independently from native active adjacency masks.
    if len(fixed_one):
        s ^= np.asarray(H[:,fixed_one].sum(axis=1)%2,dtype=np.uint8)
    B=H[:,free]
    clip=lambda x:max(-limit,min(limit,x))
    prior=[clip(math.log1p(-float(p[i]))-math.log(float(p[i]))) for i in free]
    v={(a,i):prior[i] for a in range(len(s)) for i in range(len(free)) if B[a,i]}
    c={edge:0.0 for edge in v}
    L=prior.copy()
    def full():
        bits=np.maximum(fixed,0).astype(np.uint8)
        bits[free]=np.asarray(L)<0
        return bits.tolist()
    def snap():
        return (L.copy(),[v[e] for e in sorted(v)],[c[e] for e in sorted(c)],full())
    trace=[snap()]
    history=deque(maxlen=window)
    def finish(status,t):
        return dict(status=status,iterations=t,last_decision=full(),beliefs=L.copy(),
                    history=list(history),trace=trace,free_ids=free.tolist())
    if any(not B[a].any() and s[a] for a in range(len(s))):
        return finish('LOCAL_CONTRADICTION',0)
    if np.array_equal(B@np.asarray(np.asarray(L)<0,dtype=np.uint8)%2,s):
        return finish('CONVERGED',0)
    for t in range(1,T+1):
        c={}
        for a,i in v:
            neighbors=[j for j in range(len(free)) if B[a,j] and j!=i]
            if not neighbors:
                c[a,i]=(-1 if s[a] else 1)*limit
            else:
                product=-1.0 if s[a] else 1.0
                for j in neighbors:
                    product *= math.tanh(v[a,j]/2)
                cap=math.tanh(limit/2)
                c[a,i]=clip(2*math.atanh(max(-cap,min(cap,product))))
        next_v={}
        for i in range(len(free)):
            total=0.0
            for a in range(len(s)):
                if B[a,i]: total+=c[a,i]
            L[i]=clip(prior[i]+total)
            for a in range(len(s)):
                if not B[a,i]: continue
                total=0.0
                for b in range(len(s)):
                    if b!=a and B[b,i]: total+=c[b,i]
                next_v[a,i]=clip(prior[i]+total)
        v=next_v
        history.append(L.copy())
        trace.append(snap())
        if np.array_equal(B@np.asarray(np.asarray(L)<0,dtype=np.uint8)%2,s):
            return finish('CONVERGED',t)
    return finish('NONCONVERGENCE',T)
