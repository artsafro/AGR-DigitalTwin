"""Conform quad edge junctions by opposite-edge Connect; preserve face metadata."""
import numpy as np
from collections import defaultdict
from mathutils.kdtree import KDTree
def conform(vv,ff,pid,mats,tolerance=2e-5):
 vv=[list(v) for v in vv];ff=[list(f) for f in ff];splits=0;welds=0
 for iteration in range(100):
  pts=np.array(vv);tree=KDTree(len(pts))
  for i,p in enumerate(pts):tree.insert(p,i)
  tree.balance();edges=defaultdict(list)
  incident=defaultdict(set)
  for fi,f in enumerate(ff):
   for vi in f:incident[vi].add(fi)
   for k in range(4):edges[tuple(sorted((f[k],f[(k+1)%4])))].append((fi,k))
  requests={};weld={};used={i for f in ff for i in f}
  for (a,b),links in edges.items():
   if len(links)!=1:continue
   fi,k=links[0]
   if fi in requests:continue
   delta=pts[b]-pts[a];den=delta@delta
   if den<1e-12:continue
   for co,i,d in tree.find_range((pts[a]+pts[b])/2,float(np.sqrt(den)/2+tolerance)):
    if i in [a,b] or i not in used:continue
    t=(pts[i]-pts[a])@delta/den
    if not 1e-6<t<1-1e-6 or np.linalg.norm(pts[i]-pts[a]-t*delta)>tolerance:continue
    near=a if t<.5 else b
    if np.linalg.norm(pts[i]-pts[near])<.0001 and not incident[i].intersection(incident[near]):weld[max(i,near)]=min(i,near);break
    requests[fi]=(k,i);break
  if weld:
   def target(i):
    seen=set()
    while i in weld and i not in seen:seen.add(i);i=weld[i]
    return i
   ff=[[target(i) for i in f] for f in ff];welds+=len(weld);continue
  if not requests:break
  lookup={tuple(np.round(p,6)):i for i,p in enumerate(vv)}
  for fi,(k,mid) in requests.items():
   a,b,c,d=[ff[fi][(k+j)%4] for j in range(4)]
   if mid in [a,b,c,d]:continue
   t=float((pts[mid]-pts[a])@(pts[b]-pts[a])/np.linalg.norm(pts[b]-pts[a])**2)
   q=pts[d]+t*(pts[c]-pts[d]);co,op,dist=tree.find(q)
   if dist>tolerance:
    key=tuple(np.round(q,6))
    if key not in lookup:lookup[key]=len(vv);vv.append(q.tolist())
    op=lookup[key]
   if len({a,mid,op,d})<4 or len({mid,b,c,op})<4:continue
   ff[fi]=[a,mid,op,d];ff.append([mid,b,c,op]);pid.append(pid[fi]);mats.append(mats[fi]);splits+=1
  if splits>15000:raise RuntimeError('excessive Connect propagation')
  if iteration%10==0:print('CONNECT',iteration,len(ff),splits,welds,flush=True)
 used=sorted({i for f in ff for i in f});remap={i:k for k,i in enumerate(used)}
 return [vv[i] for i in used],[[remap[i] for i in f] for f in ff],dict(splits=splits,welds=welds,iterations=iteration)
