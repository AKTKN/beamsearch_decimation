"""Small exhaustive test oracle; explicit sliced matrices, no production imports."""
from itertools import combinations, product
import math
import numpy as np
from bp_oracle import scalar_bp


def patterns(H,p,s,r,flips,M,q,K):
    H=np.asarray(H,dtype=np.uint8); s=np.asarray(s,dtype=np.uint8)
    n=H.shape[1]; w=[math.log1p(-float(x))-math.log(float(x)) for x in p]
    U=sorted(range(n),key=lambda j:(r[j],-flips[j],j))[:M]
    out=[]; rejected=0
    for F in combinations(sorted(U),q):
        free=[j for j in range(n) if j not in F]
        B=H[:,free]
        for bits in product((0,1),repeat=q):
            residual=s^(H[:,F]@np.array(bits,dtype=np.uint8)%2)
            if np.any((B.sum(axis=1)==0)&(residual==1)):
                rejected+=1; continue
            odd=np.flatnonzero(residual); k=B[odd,:].sum(axis=0)
            h=sum(min(w[free[j]]/int(k[j]) for j in range(len(free)) if B[a,j]) for a in odd)
            g=sum(w[j]*b for j,b in zip(F,bits))
            rho=sum(r[j] for j in F)
            key=tuple(x for pair in zip(F,bits) for x in pair)
            out.append((g+h,rho,key,g,h))
    return U,sorted(out)[:K],rejected,len(out)+rejected


def search(H,p,s,cfg):
    initial=scalar_bp(H,p,s,cfg.T0,cfg.Lmax,cfg.history_window)
    if initial['status']=='CONVERGED': return initial['last_decision'],None,initial,None,[]
    if initial['status']=='LOCAL_CONTRADICTION': return None,None,initial,None,[]
    hist=np.array(initial['history']); r=np.abs(hist.mean(axis=0)); flips=((hist[1:]<0)!=(hist[:-1]<0)).sum(axis=0)
    screen=patterns(H,p,s,r,flips,cfg.M,cfg.q,cfg.K)
    successes=[]
    for _,_,key,_,_ in screen[1]:
        fixed=np.full(len(p),-1)
        fixed[list(key[::2])]=key[1::2]
        post=scalar_bp(H,p,s,cfg.Tpost,cfg.Lmax,0,fixed)
        if post['status']=='CONVERGED':
            e=post['last_decision']
            cost=sum(math.log1p(-float(p[j]))-math.log(float(p[j])) for j,b in enumerate(e) if b)
            successes.append((cost,e,key))
    if not successes: return None,None,initial,screen,successes
    best=min(successes,key=lambda entry:entry[:2])
    return best[1],best[2],initial,screen,successes
