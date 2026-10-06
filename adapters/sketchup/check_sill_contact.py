"""Run with Blender to export faces, then normal Python to check coplanar contact."""
import json,sys
from pathlib import Path
job=Path('jobs/GLB-NPM').resolve();out=job/'outputs/sills-ab-v004'
if '--blender-export' in sys.argv:
    import bpy
    bpy.ops.wm.open_mainfile(filepath=str(out/'GLB_AB_sills_v004.blend'))
    faces=[]
    for o in bpy.data.objects:
        if o.type!='MESH':continue
        for p in o.data.polygons:
            faces.append({'object':o.name,'sill':o.get('role')=='simple_sills','index':p.index,
                          'points':[list(o.matrix_world@o.data.vertices[i].co) for i in p.vertices]})
    (out/'faces-readback.json').write_text(json.dumps(faces),encoding='utf-8')
else:
    import numpy as np
    from shapely.geometry import Polygon
    fs=json.loads((out/'faces-readback.json').read_text())
    pts=[np.array(f['points']) for f in fs];norms=[]
    for p in pts:
        n=np.cross(p[1]-p[0],p[2]-p[0]);norms.append(n/np.linalg.norm(n))
    norms=np.array(norms);centers=np.array([p.mean(0) for p in pts]);hits=[]
    for i,f in enumerate(fs):
        if not f['sill']:continue
        n=norms[i];drop=np.argmax(abs(n));axes=[j for j in range(3) if j!=drop]
        candidates=np.where((abs(norms@n)>.9999999)&(abs((centers-pts[i][0])@n)<1e-5))[0]
        a=Polygon(pts[i][:,axes])
        for j in candidates:
            if j==i or (fs[j]['sill'] and j<i):continue
            if np.max(abs((pts[j]-pts[i][0])@n))>1e-5:continue
            area=a.intersection(Polygon(pts[j][:,axes])).area
            if area>1e-7:hits.append({'a':[f['object'],f['index']],'b':[fs[j]['object'],fs[j]['index']],
                                    'projected_area_m2':float(area),'horizontal_sill':bool(abs(n[2])>.999)})
    report={'coplanar_overlap_pairs':hits,'count':len(hits),'horizontal_count':sum(h['horizontal_sill'] for h in hits),
            'distance_tolerance_m':1e-5,'area_threshold_m2':1e-7,'volume_penetration_is_intentional':True}
    (out/'coplanar-contact-check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print({k:v for k,v in report.items() if k!='coplanar_overlap_pairs'})
