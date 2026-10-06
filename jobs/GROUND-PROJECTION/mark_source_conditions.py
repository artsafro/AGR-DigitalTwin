import bpy,json
from pathlib import Path
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(r'C:/Users/artsafro/.AGR_Project/jobs/GROUND-PROJECTION/outputs/v003');S=R.parent/'v001'
bpy.ops.wm.open_mainfile(filepath=str(R/'GROUND_projected_v003.blend'))
o=bpy.data.objects['GROUND_PROJECTED'];d=np.load(R/'quad_mesh.npz');r=np.load(S/'Relef_arrays.npz');tr=r['v'][r['f']]
n=np.cross(tr[:,1]-tr[:,0],tr[:,2]-tr[:,0]);ok=np.abs(n[:,2])/np.maximum(np.linalg.norm(n,axis=1),1e-30)>.001
bvh=BVHTree.FromPolygons(r['v'].tolist(),r['f'][ok].tolist(),all_triangles=True)
outside=np.array([bvh.ray_cast(Vector((x,y,1000)),Vector((0,0,-1)))[2] is None for x,y,z in d['vertices']],dtype=bool)
outside_faces=outside[d['faces']].any(axis=1)
conflicts=json.loads((S/'ground_overlaps.json').read_text());parents={f for p in conflicts for f in p['faces']}
affected=np.isin(d['source_faces'],list(parents))
for name,values in [('extrapolated',outside_faces),('source_overlap_parent',affected)]:
    attr=o.data.attributes.get(name) or o.data.attributes.new(name,'INT','FACE');attr.data.foreach_set('value',values.astype(np.int32))
for name,values in [('EXTRAPOLATED_AREA',outside_faces),('SOURCE_OVERLAP_FACES',affected)]:
    g=o.vertex_groups.new(name=name);g.add(np.unique(d['faces'][values]).tolist(),1,'REPLACE')
bpy.ops.wm.save_as_mainfile(filepath=str(R/'GROUND_projected_v003.blend'))
(R/'source_condition_marks.json').write_text(json.dumps({'extrapolated_face_candidates':int(outside_faces.sum()),'source_overlap_parent_faces':int(affected.sum()),'note':'Groups mark whole faces; source_overlap_parent marks children of source triangles participating in overlaps, not exact clipped overlap regions.'},indent=2))
print('MARKS_SAVED',int(outside_faces.sum()),int(affected.sum()))
