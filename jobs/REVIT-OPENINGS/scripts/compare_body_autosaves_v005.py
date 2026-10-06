"""Check whether a later Blender autosave changed the target body's mesh or pose."""
import hashlib
import json
from pathlib import Path
import bpy

root=Path(__file__).resolve().parents[1]/'outputs/body-v005'
records=[]
for name in ('live-autosave-snapshot.blend','live-autosave-current-for-compare.blend'):
    bpy.ops.wm.open_mainfile(filepath=str(root/name))
    obj=bpy.data.objects.get('skolka')
    mesh=obj.data
    h=hashlib.sha256()
    for vertex in mesh.vertices:
        h.update(bytes(str(tuple(round(float(x),6) for x in vertex.co)),encoding='ascii'))
    for face in mesh.polygons:
        h.update(bytes(str((tuple(face.vertices),face.material_index)),encoding='ascii'))
    record={'file':name,'objects':len(bpy.context.scene.objects),
            'body_vertices':len(mesh.vertices),'body_faces':len(mesh.polygons),
            'body_matrix':[[round(float(x),6) for x in row] for row in obj.matrix_world],
            'body_geometry_hash':h.hexdigest()}
    records.append(record)
result={'same_target_geometry_and_pose':all(records[0][key]==records[1][key]
    for key in ['objects','body_vertices','body_faces','body_matrix','body_geometry_hash']),
    'snapshots':records}
(root/'autosave-comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
