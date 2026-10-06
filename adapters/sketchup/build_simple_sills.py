"""Simplify source sill envelopes; paint existing reveal polygons, add no reveals."""
import bpy,bmesh,json,sys,hashlib
from pathlib import Path
from collections import defaultdict
from mathutils import Vector
job=Path(sys.argv[sys.argv.index('--')+1]).resolve();out=job/'outputs/sills-ab-v003'
target=out/'GLB_AB_sills_v003.blend';assert not target.exists(),'New version required'
data=json.loads((out/'measured-sills-and-reveals.json').read_text(encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=str(job/'outputs/sills-base-v003/GLB_AB_source_reference.blend'))
mat=bpy.data.materials['<auto>52'].copy();mat.name='M_Reveal_Color'
mat['role']='Color ID on existing opening faces, no overlay mesh'
sillmat=bpy.data.materials['<auto>52'].copy();sillmat.name='M_Sill_Color'
report={'version':'v003','delivery':False,'floors':{},'added_reveal_geometry':0,
        'limits':['Remaining BODY is source topology.','Window texture/atlas remains user task.','Full AGR QA pending.']}
for label,desc in data['floors'].items():
    selected={pid for r in desc['reveals'] for pid in r['existing_wall_face_pids']}
    painted=0;found=set();body_before={}
    for ob in bpy.data.objects:
        if ob.type!='MESH' or not ob.name.startswith(label+'_'):continue
        mesh=ob.data;attr=mesh.attributes.get('source_face_pid')
        if not attr:continue
        body_before[ob.name]=(len(mesh.vertices),len(mesh.polygons))
        ids=[v.value for v in attr.data]
        indices=[p.index for p in mesh.polygons if ids[p.index] in selected]
        if not indices:continue
        slot=len(mesh.materials);mesh.materials.append(mat)
        for i in indices:
            mesh.polygons[i].material_index=slot;painted+=1;found.add(ids[i])
    assert selected==found,(label,selected-found)
    assert all((len(bpy.data.objects[n].data.vertices),len(bpy.data.objects[n].data.polygons))==counts for n,counts in body_before.items())
    verts=[];faces=[]
    for sill in desc['sills']:
        xy=sill['xy'];s=len(verts)
        verts.extend([(x,y,sill['bottom']) for x,y in xy]+[(x,y,sill['top']) for x,y in xy])
        faces.extend([tuple(s+i for i in f) for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]])
    # Remove BOTH coincident interface faces before welding; welding alone keeps one.
    face_groups=defaultdict(list)
    for i,f in enumerate(faces):
        key=tuple(sorted(tuple(round(c,5) for c in verts[v]) for v in f))
        face_groups[key].append(i)
    interface_ids={i for ids in face_groups.values() if len(ids)==2 for i in ids}
    faces=[f for i,f in enumerate(faces) if i not in interface_ids]
    me=bpy.data.meshes.new(label+'_Sills_mesh');me.from_pydata(verts,[],faces);me.update()
    bm=bmesh.new();bm.from_mesh(me);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00001)
    bm.verts.index_update();groups=defaultdict(list)
    for f in bm.faces:groups[tuple(sorted(v.index for v in f.verts))].append(f)
    internal=[f for same in groups.values() if len(same)==2 for f in same]
    if internal:bmesh.ops.delete(bm,geom=internal,context='FACES_ONLY')
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free();me.update()
    assert all(len(p.vertices)==4 and p.area>1e-9 for p in me.polygons)
    uv=me.uv_layers.new(name='Sill_UV')
    for p in me.polygons:
        normal=p.normal;drop=max(range(3),key=lambda i:abs(normal[i]));axes=[i for i in range(3) if i!=drop]
        for idx in p.loop_indices:
            co=me.vertices[me.loops[idx].vertex_index].co;uv.data[idx].uv=(co[axes[0]],co[axes[1]])
    me.materials.append(sillmat)
    ob=bpy.data.objects.new(label+'_Sills_Simple',me);bpy.context.scene.collection.objects.link(ob)
    ob['role']='simple_sills';ob['source_pieces']=len(desc['sills'])
    report['floors'][label]={'source_reveal_overlays_removed':len(desc['reveals']),
      'existing_source_reveal_faces_painted':len(found),'painted_mesh_polygons':painted,
      'source_sill_pieces':len(desc['sills']),'sill_meshes':1,'sill_quads':len(me.polygons),
      'internal_join_faces_removed':len(internal)+len(interface_ids),'body_geometry_unchanged_by_paint':True,
      'thickness_range_m':[min(s['top']-s['bottom'] for s in desc['sills']),max(s['top']-s['bottom'] for s in desc['sills'])]}
# Preserve v002 window/AC meshes, matrices, materials, UV and source properties exactly.
prior=job/'outputs/planes-ab-v002/GLB_AB_planes_v002.blend'
with bpy.data.libraries.load(str(prior),link=False) as (available,requested):
    requested.objects=[n for n in available.objects if '_windows_' in n or '_ac_' in n]
coll=bpy.data.collections.new('Window_AC_planes_v002_preserved');bpy.context.scene.collection.children.link(coll)
for ob in requested.objects:coll.objects.link(ob)
assert len(requested.objects)==74
scene=bpy.context.scene;scene['status']='SIMPLIFIED_SILLS_REVEAL_COLOR_V003';scene['delivery']=False
scene.render.filepath=str(out/'AB_sills_v003.png')
bpy.ops.wm.save_as_mainfile(filepath=str(target));bpy.ops.wm.open_mainfile(filepath=str(target))
report['saved_readback']=True
report['readback_sill_meshes']=sum(o.get('role')=='simple_sills' for o in bpy.data.objects)
report['readback_plane_objects']=sum(o.get('role') in ['windows','ac'] for o in bpy.data.objects)
report['readback_total_polygons']=sum(len(o.data.polygons) for o in bpy.data.objects if o.type=='MESH')
assert report['readback_sill_meshes']==2 and report['readback_plane_objects']==74
(out/'sills-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
bpy.ops.render.render(write_still=True)
print('SILLS_RESULT '+json.dumps(report))
