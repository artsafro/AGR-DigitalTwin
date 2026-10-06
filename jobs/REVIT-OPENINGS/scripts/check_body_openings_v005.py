"""Read back saved body replacements and check plane fit, IDs and front polarity."""
import json
from collections import Counter
from pathlib import Path
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/body-v005'
mapping=json.loads((OUT/'body-opening-map.json').read_text(encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=str(OUT/'SOSH1150_Body_Openings_Replaced_v005.blend'))
body=bpy.data.objects['skolka']
issues=[];fit=[];polarity=[];quads=0
for row in mapping['records']:
    name=row['id']+'_'+row['type_id']
    obj=bpy.data.objects.get(name)
    if obj is None:
        issues.append((name,'missing object'));continue
    mesh=obj.data
    if len(mesh.materials)!=2 or {p.material_index for p in mesh.polygons}!={0,1}:
        issues.append((name,'material IDs are not exactly 1/2'))
    if any(len(p.vertices)!=4 for p in mesh.polygons):
        issues.append((name,'non-quad face'))
    quads+=len(mesh.polygons)
    normal=Vector(row['normal_out']);right=Vector(row['right']);origin=Vector(row['origin'])
    low_u,high_u=float('inf'),float('-inf')
    low_z,high_z=float('inf'),float('-inf')
    for v in mesh.vertices:
        p=obj.matrix_world@v.co
        u=(p-origin).dot(right);z=p.z-origin.z
        low_u=min(low_u,u);high_u=max(high_u,u)
        low_z=min(low_z,z);high_z=max(high_z,z)
    size_error=max(abs(low_u),abs(high_u-row['width_m']),abs(low_z),abs(high_z-row['height_m']))
    fit.append(size_error)
    if size_error>.002:issues.append((name,f'plane fit {size_error:.4f}m'))
    frame_faces=[p for p in mesh.polygons if p.material_index==0 and p.normal.y<-.9]
    glass_faces=[p for p in mesh.polygons if p.material_index==1 and p.normal.y<-.9]
    if not frame_faces or not glass_faces:
        issues.append((name,'missing front frame/glass faces'));continue
    front_normal=(obj.matrix_world.to_3x3()@Vector((0,-1,0))).normalized()
    facing=front_normal.dot(normal)
    polarity.append(facing)
    if facing<.999:issues.append((name,f'frame facing dot {facing:.6f}'))
    # Glass front must lie behind the frame along the outward direction.
    frame_depth=max((obj.matrix_world@mesh.vertices[i].co-origin).dot(normal)
                    for p in frame_faces for i in p.vertices)
    glass_depth=max((obj.matrix_world@mesh.vertices[i].co-origin).dot(normal)
                    for p in glass_faces for i in p.vertices)
    if frame_depth-glass_depth<.029:
        issues.append((name,f'frame/glass order {frame_depth-glass_depth:.4f}m'))

leftover=sum(p.material_index==1 for p in body.data.polygons)
if leftover:issues.append(('skolka',f'{leftover} ID2 planes remain'))
if len(body.data.polygons)!=21474-3203:issues.append(('skolka','body face count mismatch'))
result={'frames':len(mapping['records']),'body_faces':len(body.data.polygons),
        'body_window_faces_remaining':leftover,'frame_quads':quads,
        'max_fit_error_m':round(max(fit),6),'min_outward_dot':round(min(polarity),6),
        'scaled_review_count':sum('review required' in r['confidence'] for r in mapping['records']),
        'issues':issues,'geometry_checks_passed':not issues,
        'visual_acceptance':'pending','delivery_passed':False}
(OUT/'QA.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
