"""Clip sill faces against measured opaque facade sections, retaining only exterior parts."""
import json,math,numpy as np,shapely
from pathlib import Path
from shapely.geometry import LineString,Polygon
from shapely.ops import polygonize,triangulate
out=Path('jobs/GLB-NPM/outputs/tower-k1-v011')
clean=json.loads((out/'v013-faces.json').read_text());original=json.loads((out/'assembly-faces.json').read_text())
facade=[f for f in clean if f['object'] in ['K1_BODY','K1_WINDOWS']]
floors=sorted(json.loads((out/'floor-instances.json').read_text()),key=lambda r:r['z_translation_m'])
levels=[r['z_translation_m']+.02 for r in floors];sections={}
for i,level in enumerate(levels):
 for typ,zz in [('belt',.5),('window',1.5)]:
  z=level+zz;lines=[]
  for f in facade:
   pts=f['points'];hits=[]
   for a,b in zip(pts,pts[1:]+pts[:1]):
    if min(a[2],b[2])<z<max(a[2],b[2]):
     t=(z-a[2])/(b[2]-a[2]);hits.append(tuple(a[j]+t*(b[j]-a[j]) for j in [0,1]))
   if len(hits)==2 and math.dist(*hits)>1e-7:lines.append(LineString(hits))
  polygons=[]
  for precision in [.00001,.00005,.0001]:
   polygons=list(polygonize(shapely.union_all(lines,grid_size=precision)))
   if polygons and max(p.area for p in polygons)>580:break
  shell=max(polygons,key=lambda p:p.area);assert 580<shell.area<610,(i,typ,shell.area)
  sections[i,typ]=shell
(out/'facade-sections.json').write_text(json.dumps({'levels':levels,'sections':{str(i)+'_'+typ:p.wkt for (i,typ),p in sections.items()}}),encoding='utf-8')
result=[];removed=0
def emit(f,points):
 p=np.array(f['points']);q=np.array(points);n=np.cross(p[1]-p[0],p[2]-p[0]);n/=np.linalg.norm(n)
 if np.cross(q[1]-q[0],q[2]-q[0])@n<0:q=q[::-1]
 # Affine source UV interpolation on the original face plane.
 fit=np.linalg.lstsq(np.c_[p,np.ones(len(p))],np.array(f['uv']),rcond=None)[0]
 result.append({'points':q.tolist(),'uv':(np.c_[q,np.ones(len(q))]@fit).tolist(),'material':f['material']})
for f in original:
 if f['object']!='K1_SIMPLE_SILLS':continue
 p=np.array(f['points']);lo=p[:,2].min();hi=p[:,2].max();idx=min(range(len(levels)),key=lambda i:abs((lo+hi)/2-levels[i]-1))
 interface=levels[idx]+1
 if hi-lo<.00001:
  poly=Polygon(p[:,:2]);shell=sections[idx,'belt' if lo<interface else 'window'];shape=poly.difference(shell)
  if shape.area<1e-7:removed+=1;continue
  parts=list(shape.geoms) if hasattr(shape,'geoms') else [shape]
  for part in parts:
   if part.geom_type!='Polygon' or part.area<1e-7:continue
   part=part.simplify(.00001,preserve_topology=True)
   xy=list(part.exterior.coords)[:-1]
   if not part.interiors and len(xy) in [3,4] and abs(part.convex_hull.area-part.area)<1e-8:
    emit(f,[[x,y,float(lo)] for x,y in xy])
   else:
    for tri in shapely.constrained_delaunay_triangles(part).geoms:
     if tri.area>1e-7 and part.covers(tri.representative_point()):emit(f,[[x,y,float(lo)] for x,y in list(tri.exterior.coords)[:-1]])
 else:
  pairs=[(np.linalg.norm(a[:2]-b[:2]),a[:2],b[:2]) for a in p for b in p];_,a,b=max(pairs,key=lambda x:x[0]);line=LineString([a,b])
  cuts=sorted(set([lo,hi]+([interface] if lo<interface<hi else [])));made=0
  for z0,z1 in zip(cuts,cuts[1:]):
   shell=sections[idx,'belt' if (z0+z1)/2<interface else 'window'];shape=line.difference(shell)
   geoms=list(shape.geoms) if hasattr(shape,'geoms') else [shape]
   for g in geoms:
    if g.geom_type!='LineString' or g.length<.0001:continue
    a,b=list(g.coords)[0],list(g.coords)[-1];emit(f,[[*a,float(z0)],[*b,float(z0)],[*b,float(z1)],[*a,float(z1)]]);made+=1
  if not made:removed+=1
(out/'sills-exterior-polygons.json').write_text(json.dumps(result),encoding='utf-8')
(out/'sills-section-trim-report.json').write_text(json.dumps({'closed_facade_sections':len(sections),'entire_hidden_faces_removed':removed,
 'retained_face_pieces':len(result),'section_noding_precision_max_m':.0001,'method':'Exact planar difference against belt/window facade cross sections; opaque windows close the contour.'},indent=2),encoding='utf-8')
print('SILL EXTERIOR',len(sections),'closed sections',removed,'removed',len(result),'pieces')
