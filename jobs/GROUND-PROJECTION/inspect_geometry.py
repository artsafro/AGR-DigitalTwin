import bpy, json, collections
from pathlib import Path
from mathutils.bvhtree import BVHTree
from mathutils import Vector
from io_scene_fbx import parse_fbx
root=Path(r'C:/Users/artsafro/.AGR_Project/jobs/GROUND-PROJECTION/outputs/v001')
bpy.ops.wm.open_mainfile(filepath=str(root/'source_import.blend'))
g=bpy.data.objects['Ground']; r=bpy.data.objects['Relef']
rv=[r.matrix_world@v.co for v in r.data.vertices]
tree=BVHTree.FromPolygons(rv,[list(p.vertices) for p in r.data.polygons],all_triangles=True)
miss=[];hits=[]
for v in g.data.vertices:
    p=g.matrix_world@v.co
    hit=tree.ray_cast(Vector((p.x,p.y,10000)),Vector((0,0,-1)))[0]
    if hit is None:miss.append({'id':v.index,'xy':list(p)[:2]})
    else:hits.append(hit.z)
root_fbx,ver=parse_fbx.parse(r'C:/Users/artsafro/Downloads/Telegram Desktop/GROUND.fbx')
glob=next(e for e in root_fbx.elems if e.id==b'GlobalSettings')
settings={e.props[0].decode():(e.props[-1].decode() if isinstance(e.props[-1],bytes) else e.props[-1]) for e in glob.elems[1].elems}
out={'fbx_settings':settings,'vertex_ray_misses':miss,'vertex_hits':len(hits),'hit_z_range':[min(hits),max(hits)],'scene_units':bpy.context.scene.unit_settings.scale_length}
(root/'ray_audit.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps({**out,'vertex_ray_misses_count':len(miss),'vertex_ray_misses':miss[:5]},indent=2))

