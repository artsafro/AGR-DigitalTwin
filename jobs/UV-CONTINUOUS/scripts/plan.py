import json, numpy as np
from collections import defaultdict, Counter, deque
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'outputs'
d=json.loads((root/'source.json').read_text());v=np.array(d['vertices']);norm=np.array(d['normals'])
t=np.column_stack((norm[:,1],-norm[:,0],np.zeros(len(norm))))
length=np.linalg.norm(t,axis=1);vertical=length>.999
t[vertical]/=length[vertical,None]
edges=defaultdict(list)
for fi,f in enumerate(d['faces']):
    for a,b in zip(f,f[1:]+f[:1]):
        key=tuple(sorted((tuple(np.round(v[a],5)),tuple(np.round(v[b],5)))))
        edges[key].append(fi)
adj=defaultdict(list)
for (a,b),fs in edges.items():
    if len(fs)==2 and all(vertical[fs]) and abs(a[0]-b[0])+abs(a[1]-b[1])<1e-4:
        i,j=fs; pos=(np.array(a)+b)/2;delta=pos@(t[i]-t[j])
        adj[i].append((j,delta));adj[j].append((i,-delta))
    elif len(fs)==2 and all(vertical[fs]) and t[fs[0]]@t[fs[1]]>.99999:
        i,j=fs;pos=(np.array(a)+b)/2;delta=pos@(t[i]-t[j])
        adj[i].append((j,delta));adj[j].append((i,-delta))
parent=list(range(len(norm)))
def find(i):
    while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
    return i
for i,links in adj.items():
    for j,delta in links:
        if t[i]@t[j]>.99999:
            a,b=find(i),find(j);parent[b]=a
groups=defaultdict(list)
for i in np.flatnonzero(vertical):groups[find(int(i))].append(int(i))
for ids in groups.values():
    tangent=t[ids].mean(axis=0);tangent/=np.linalg.norm(tangent);t[ids]=tangent
gadj=defaultdict(list)
for i,links in adj.items():
    for j,delta in links:
        a,b=find(i),find(j)
        if a!=b:
            common=set(d['faces'][i]).intersection(d['faces'][j])
            if common:delta=v[list(common)].mean(axis=0)@(t[i]-t[j])
            gadj[a].append((b,delta,i,j))
goff={}
for seed in sorted(groups,key=lambda g:-len(groups[g])):
    if seed in goff:continue
    goff[seed]=0.;q=deque([seed])
    while q:
        a=q.popleft()
        for b,delta,i,j in gadj[a]:
            if b not in goff:goff[b]=goff[a]+delta;q.append(b)
offset={i:goff[g] for g,ids in groups.items() for i in ids};components=[]
for seed in sorted(np.flatnonzero(vertical),key=lambda i:-len(adj[i])):
    if any(int(seed) in c for c in components):continue
    visited={int(seed)};q=deque([int(seed)]);comp=[]
    while q:
        i=q.popleft();comp.append(i)
        for j,delta in adj[i]:
            if j not in visited:visited.add(j);q.append(j)
    components.append(comp)
conflicts=[]
for i,links in adj.items():
    for j,delta in links:
        common=set(d['faces'][i]).intersection(d['faces'][j])
        if common:delta=v[list(common)].mean(axis=0)@(t[i]-t[j])
        if i<j and abs(offset[j]-offset[i]-delta)>1e-4:conflicts.append([i,j,offset[j]-offset[i]-delta])
uv=[]
for i,f in enumerate(d['faces']):
    p=v[f]
    if vertical[i]:uv.append(np.column_stack((p@t[i]+offset[i],p[:,2])).tolist())
    else:
        n=norm[i];a=p[1]-p[0];a/=np.linalg.norm(a);b=np.cross(n,a);b/=np.linalg.norm(b)
        uv.append(np.column_stack((p@a,p@b)).tolist())
report={'vertical_faces':int(vertical.sum()),'components':len(components),'component_sizes':sorted(map(len,components),reverse=True)[:20], 'conflicts':conflicts,'edge_counts':dict(Counter(map(len,edges.values()))), 'polygon_sizes':dict(Counter(map(len,d['faces'])))}
(root/'plan.json').write_text(json.dumps({'metric_uv':uv,'report':report}))
(root/'charts.json').write_text(json.dumps({'groups':{str(g):ids for g,ids in groups.items()},'tangents':t.tolist(),'offsets':{str(i):x for i,x in offset.items()},'adj':{str(i):links for i,links in adj.items()}}))
print(json.dumps({**report,'conflicts':conflicts[:25],'conflict_count':len(conflicts)}))
