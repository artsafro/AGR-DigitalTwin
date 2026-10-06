"""Independent simplified profile lofts from measured horizontal sections."""
import json,ast,math
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
from shapely.geometry import Polygon,LineString,Point
from shapely.ops import unary_union,polygonize,snap,nearest_points
from shapely import make_valid,set_precision,STRtree
base=Path(__file__).resolve().parents[1];out=base/'outputs/master-v001'
tree=ast.parse((base/'scripts/mesh_patches.py').read_text())
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom,ast.FunctionDef))],type_ignores=[]),'quad_routines','exec'))
data=json.loads((out/'reference.json').read_text());names=['MultiMat_22','MultiMat_26','Material #200','Material #230','Material #219'];result=[];failures=[]
for o in data:
 if o['name'] not in names:continue
 v=np.array(o['vertices']);parent=list(range(len(v)));lookup={}
 def root(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 def union(a,b):parent[root(a)]=root(b)
 for i,p in enumerate(v):
  key=tuple(np.round(p,4))
  if key in lookup:union(i,lookup[key])
  else:lookup[key]=i
 for f in o['faces']:
  for i in f:union(f[0],i)
 groups=defaultdict(list)
 for fi,f in enumerate(o['faces']):groups[root(f[0])].append(fi)
 for ci,inds in enumerate(groups.values()):
  ids=sorted(set(i for fi in inds for i in o['faces'][fi]));pts=v[ids];lo=pts.min(axis=0);hi=pts.max(axis=0);height=hi[2]-lo[2]
  if height<.015:continue
  tris=[]
  for fi in inds:
   f=o['faces'][fi]
   tris.extend(v[[f[0],f[k],f[k+1]]] for k in range(1,len(f)-1))
  tris=np.array(tris)
  if max(hi[0]-lo[0],hi[1]-lo[1])>3.5:
   projected=[];source_tris=[]
   for q in tris:
    p=Polygon(q[:,:2])
    if p.area>1e-7:projected.append(p);source_tris.append(q)
   footprint=unary_union([set_precision(p,.001) for p in projected]).simplify(.008,preserve_topology=True)
   fps=[footprint] if footprint.geom_type=='Polygon' else [g for g in getattr(footprint,'geoms',[]) if g.geom_type=='Polygon']
   tree2=STRtree(projected);source_tris=np.array(source_tris)
   for part_index,fp in enumerate(fps):
    if fp.area<.001:continue
    inner=fp.buffer(-.003)
    def heights(xy):
     p=Point(xy)
     if not inner.is_empty:p=nearest_points(p,inner)[1]
     cand=tree2.query(p.buffer(.0001));zs=[]
     for ii in cand:
      if projected[ii].distance(p)>.0001:continue
      q=source_tris[ii];bary=np.linalg.solve(np.vstack([q[:,:2].T,np.ones(3)]),[p.x,p.y,1]);zs.append(float(bary@q[:,2]))
     if not zs:
      ii=int(tree2.nearest(p));p=nearest_points(p,projected[ii])[1];q=source_tris[ii];bary=np.linalg.solve(np.vstack([q[:,:2].T,np.ones(3)]),[p.x,p.y,1]);zs=[float(bary@q[:,2])]
     low,high=min(zs),max(zs)
     if high-low<.003:low=low-.003;high=high+.003
     return low,high
    quads,method=make_quads(fp);vv=[];ff=[];lookup2={};bottom=[];top=[]
    def pair(xy):
     key=tuple(round(float(x),6) for x in xy)
     if key not in lookup2:
      low,high=heights(xy);lookup2[key]=(len(vv),len(vv)+1);vv.extend([[*xy,low],[*xy,high]])
     return lookup2[key]
    for quad in quads:
     if signed_area(quad)<0:quad=quad[::-1]
     bb,tt=zip(*(pair(p) for p in quad));bottom.append(list(bb));top.append(list(tt));ff.extend([list(bb)[::-1],list(tt)])
    ec=Counter(tuple(sorted((a,b))) for f in top for a,b in zip(f,f[1:]+f[:1]))
    for f in top:
     for a,b in zip(f,f[1:]+f[:1]):
      if ec[tuple(sorted((a,b)))]==1:ff.append([a,b,b-1,a-1])
    result.append(dict(vertices=vv,faces=ff,source_plane=-4,source_object=o['name'],source_faces=inds,normal=[0,0,0],area=fp.area,role='profiles',method='independent_footprint_loft_measured_top_bottom',component=ci,levels=[float(lo[2]),float(hi[2])]))
   continue
  def section(z):
   lines=[]
   for q in tris[(tris[:,:,2].min(axis=1)<z)&(tris[:,:,2].max(axis=1)>z)]:
    cross=[]
    for a,b in zip(q,np.roll(q,-1,axis=0)):
     if (a[2]-z)*(b[2]-z)<0:cross.append(a[:2]+(b[:2]-a[:2])*(z-a[2])/(b[2]-a[2]))
    if len(cross)==2 and np.linalg.norm(cross[0]-cross[1])>1e-6:lines.append(LineString(np.round(cross,4)))
   network=unary_union(lines);network=snap(network,network,.001)
   ps=list(polygonize(network))
   if not ps:return None
   p=max(ps,key=lambda p:p.area).simplify(.008,preserve_topology=True)
   return Polygon(p.exterior)
  column=height>1.5 and max(hi[0]-lo[0],hi[1]-lo[1])<3.5
  levels=[float(lo[2]),float(hi[2])]
  if column:
   # Preserve meaningful source height changes; omit small bevel levels.
   zz=sorted(set(round(float(z),3) for z in pts[:,2]));inner=[]
   for z in zz:
    if z-lo[2]>.15 and hi[2]-z>.15 and (not inner or z-inner[-1]>.15):inner.append(z)
   if len(inner)>1:inner=[float((lo[2]+hi[2])/2)]
   levels=levels[:1]+inner+levels[1:]
  rings=[]
  for z in levels:
   sample=min(max(z,lo[2]+.006),hi[2]-.006) if column else (lo[2]+hi[2])/2
   p=section(sample)
   if p is None:p=section((lo[2]+hi[2])/2)
   if p is None:
    from shapely import make_valid
    projected=[make_valid(Polygon(q[:,:2])) for q in tris if Polygon(q[:,:2]).area>1e-8]
    footprint=unary_union(projected)
    candidates=[footprint] if footprint.geom_type=='Polygon' else [g for g in getattr(footprint,'geoms',[]) if g.geom_type=='Polygon']
    if candidates:p=Polygon(max(candidates,key=lambda p:p.area).exterior).simplify(.008,preserve_topology=True)
   if p is None:break
   cc=list(p.exterior.coords)[:-1]
   if signed_area(cc)<0:cc=cc[::-1]
   # Stable seam near the minimum X/Y corner of each section.
   start=min(range(len(cc)),key=lambda i:(round(cc[i][0],2),round(cc[i][1],2)));cc=cc[start:]+cc[:start]
   lens=np.linalg.norm(np.roll(np.array(cc),-1,axis=0)-np.array(cc),axis=1);ts=np.r_[0,np.cumsum(lens)];ts/=ts[-1]
   rings.append((np.array(cc),ts,z))
  if len(rings)!=len(levels):failures.append(dict(object=o['name'],component=ci,reason='section polygonization'));continue
  equal=all(len(cc)==len(rings[0][0]) for cc,times,z in rings)
  perimeter=max(Polygon(cc).length for cc,times,z in rings)
  ts=list(range(len(rings[0][0]))) if equal else merged_values([t for cc,times,z in rings for t in times[:-1]],.004/perimeter)
  vv=[];ff=[];ring_ids=[];lk={}
  def vertex(xyz):
   key=tuple(np.round(xyz,6))
   if key not in lk:lk[key]=len(vv);vv.append(list(xyz))
   return lk[key]
  for cc,times,z in rings:
   loop_ids=[]
   for t in ts:
    if equal:p=cc[t]
    else:
     k=min(len(cc)-1,int(np.searchsorted(times,t,side='right')-1));fraction=(t-times[k])/(times[k+1]-times[k]);p=cc[k]+fraction*(cc[(k+1)%len(cc)]-cc[k])
    loop_ids.append(vertex([*p,z]))
   ring_ids.append(loop_ids)
  for low,high in zip(ring_ids,ring_ids[1:]):
   for i in range(len(ts)):j=(i+1)%len(ts);ff.append([low[i],low[j],high[j],high[i]])
  for r,reverse in [(ring_ids[0],True),(ring_ids[-1],False)]:
   poly=Polygon([vv[i][:2] for i in r]);quads,method=make_quads(poly)
   for q in quads:
    if signed_area(q)<0:q=q[::-1]
    if reverse:q=q[::-1]
    ff.append([vertex([a,b,vv[r[0]][2]]) for a,b in q])
  result.append(dict(vertices=vv,faces=ff,source_plane=-3,source_object=o['name'],source_faces=inds,normal=[0,0,0],area=1,role='profiles',method='independent_section_loft_8mm_outline_simplification',component=ci,levels=levels))
(out/'profiles-quad.json').write_text(json.dumps(result));(out/'profile-loft-report.json').write_text(json.dumps(dict(components=len(result),quads=sum(len(p['faces']) for p in result),failed=failures,outline_simplification_m=.008),indent=2))
print('lofts',len(result),'quads',sum(len(p['faces']) for p in result),'failed',len(failures),failures[:5])
