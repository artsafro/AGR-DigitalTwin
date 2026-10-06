"""Build or independently read back an exterior-only pre-Shell Blender surface."""
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

p=Path(sys.argv[sys.argv.index('--')+1]).resolve()
source=np.load(p/'exterior-surface.npz',allow_pickle=False)
report=json.loads((p/'exterior-surface.json').read_text(encoding='utf-8'))
blend=p/'EXTERIOR_SURFACE.blend'

if '--check' in sys.argv:
    digest=hashlib.sha256(blend.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
    assert len(meshes)==1
    obj=meshes[0];mesh=obj.data
    assert not mesh.validate(verbose=False,clean_customdata=False), 'Saved mesh required repair'
    v=np.empty(len(mesh.vertices)*3);mesh.vertices.foreach_get('co',v);v=v.reshape(-1,3)
    degree=np.empty(len(mesh.polygons),dtype=np.int32);mesh.polygons.foreach_get('loop_total',degree)
    assert (degree==4).all()
    f=np.empty(len(mesh.loops),dtype=np.int32);mesh.loops.foreach_get('vertex_index',f);f=f.reshape(-1,4)
    labels=np.empty(len(f),dtype=np.int32);mesh.attributes['facade_run_index'].data.foreach_get('value',labels)
    assert np.array_equal(f,source['faces']) and np.array_equal(labels,source['facade_indices'])
    assert json.loads(bpy.data.texts['EXTERIOR_source_profiles.json'].as_string())==report
    edges=np.sort(np.stack([f,np.roll(f,-1,axis=1)],axis=2).reshape(-1,2),axis=1)
    unique,counts=np.unique(edges,axis=0,return_counts=True)
    boundary=unique[counts==1]
    boundary_degree=defaultdict(int)
    for edge in boundary:
        for i in edge:boundary_degree[int(i)]+=1
    q=v[f];lengths=np.linalg.norm(np.roll(q,-1,axis=1)-q,axis=2)
    shell=obj.modifiers.get('SHELL_0.4m_AFTER_SURFACE_REVIEW')
    result={'blend':str(blend),'sha256':digest,'scope':'exterior surface only, before Shell',
            'vertices':len(v),'quads':len(f),'exact_duplicate_vertices':len(v)-len(np.unique(v,axis=0)),
            'exact_duplicate_faces':len(f)-len(np.unique(np.sort(f,axis=1),axis=0)),
            'edges_with_more_than_two_faces':int((counts>2).sum()),
            'intentional_boundary_edges':len(boundary),'boundary_junction_vertices':sum(n!=2 for n in boundary_degree.values()),
            'minimum_edge_m':float(lengths.min()),'faces_with_edge_below_10mm':int((lengths.min(axis=1)<.01).sum()),
            'readback_max_error_m':float(np.linalg.norm(v-source['vertices'],axis=1).max()),
            'source_mapping_readback':True,'shell_thickness_m':None,
            'shell_enabled':shell is not None,
            'geometry_checks_passed':False,'passed':False,
            'remaining':['Independent exterior/profile/overlap verification','Surface review before enabling and validating Shell']}
    assert not result['shell_enabled']
    np.savez_compressed(p/'exterior-readback.npz',vertices=v,faces=f,facade_indices=labels)
    (p/'exterior-qa.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result))
    raise SystemExit(0)

if blend.exists():raise FileExistsError(blend)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system='METRIC'
bpy.context.scene.unit_settings.scale_length=1.0
mesh=bpy.data.meshes.new('EXTERIOR_SURFACE')
mesh.from_pydata(source['vertices'].tolist(),[],source['faces'].tolist());mesh.update()
assert not mesh.validate(verbose=False,clean_customdata=False), 'Generated mesh required repair'
obj=bpy.data.objects.new('BODY_EXTERIOR',mesh);bpy.context.collection.objects.link(obj)
mesh.attributes.new('facade_run_index','INT','FACE').data.foreach_set('value',source['facade_indices'])
bpy.data.texts.new('EXTERIOR_source_profiles.json').write(json.dumps(report,ensure_ascii=False))
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
print('SAVED_EXTERIOR',len(mesh.polygons))
