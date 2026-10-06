import bpy,bmesh,json,math,sys
from pathlib import Path
from collections import Counter
from mathutils import Matrix,Vector

root=Path('C:/Users/artsafro/.AGR_Project/jobs/REVIT-OPENINGS');out=root/'outputs/library-v001'
types=json.loads((out/'rebuilt-core.json').read_text(encoding='utf-8'))
raw={t['id']:t for t in json.loads((root/'outputs/source-v001/types.json').read_text(encoding='utf-8'))}
systems=json.loads((out/'curtain-types.json').read_text(encoding='utf-8'))
checks=json.loads((out/'reconstruction-check.json').read_text(encoding='utf-8'))
byid={}
for r in checks:byid.setdefault(r['id'],[]).append(r)
bpy.ops.wm.read_factory_settings(use_empty=True)
default=bpy.context.scene

def mat(name,color,metallic=0):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Roughness'].default_value=.45;bs.inputs['Metallic'].default_value=metallic
    m['status']='DIAGNOSTIC_PREVIEW_NOT_PROJECT_FINISH';return m
frame_mat=mat('PREVIEW_Frame_Leaf_UNSPECIFIED',(.22,.27,.32),.15)
glass_mat=mat('PREVIEW_Glass_candidate_UNCONFIRMED',(.29,.53,.65))
opaque_mat=mat('PREVIEW_Opaque_panel_UNSPECIFIED',(.40,.44,.48))
review_mat=mat('PREVIEW_Source_geometry_REVIEW',(.58,.32,.14))
materials={'GLASS':glass_mat,'GLASS_CANDIDATE':glass_mat,'OPAQUE_PANEL':opaque_mat}
prototypes={};qa=[]

def make_mesh(name,vertices,faces,material):
    me=bpy.data.meshes.new(name);me.from_pydata(vertices,[],faces);me.update();me.materials.append(material)
    bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
    # Preview UV: consistent planar projection per face; no project finish assignment.
    uv=me.uv_layers.new(name='PreviewUV')
    for f in me.polygons:
        axis=max(range(3),key=lambda i:abs(f.normal[i]));xy=[i for i in range(3) if i!=axis]
        coords=[me.vertices[i].co for i in f.vertices]
        lo=[min(c[i] for c in coords) for i in xy];span=[max(c[i] for c in coords)-lo[j] for j,i in enumerate(xy)]
        for li in f.loop_indices:
            p=me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv=[.01+.98*(p[i]-lo[j])/max(span[j],1e-9) for j,i in enumerate(xy)]
    return me

for t in types:
    col=bpy.data.collections.new(t['id']);col['source_name']=t['source'];col['source_instance_count']=len(t['instances'])
    col['material_status']=t['material_status'];col['source_geometry_variants']=json.dumps(t['raw_ids']);col['type_identity']='GEOMETRIC_VARIANT_NOT_VERIFIED_REVIT_FAMILY_TYPE'
    col['source_instance_names']=json.dumps(t['instances'],ensure_ascii=False)
    col['omitted_hardware_components']=len(t['details'])
    problems=[r for r in byid.get(t['id'],[]) if r['nonmanifold_edges'] or r['ray_disagreement_cells'] or r['bbox_error_m']>.00002]
    col['qa_status']='REVIEW' if problems or t['fallback'] else 'CORE_TOPOLOGY_CHECKED_VISUAL_PENDING'
    for p in t['parts']:
        name=f"{t['id']}_{p['role']}_{p['component']:02d}"
        me=make_mesh(name,p['vertices'],p['faces'],materials.get(p['role'],frame_mat))
        o=bpy.data.objects.new(name,me);col.objects.link(o)
        o['source_name']=t['source'];o['source_component']=p['component'];o['role']=p['role'];o['method']=p['method']
        attr=me.attributes.new('source_component','INT','FACE')
        for value in attr.data:value.value=p['component']
        qa.append({'name':name,'type':t['id'],'role':p['role'],'method':p['method'],'polygons':len(me.polygons)})
    # Never silently drop exceptional curved/angled source components.
    for p in t['fallback']:
        sr=raw[t['id']];faces=[sr['faces'][i] for i in p['faces']];used=sorted(set(i for f in faces for i in f));idx={i:j for j,i in enumerate(used)}
        name=f"{t['id']}_SOURCE_REVIEW_{p['component']:02d}"
        me=make_mesh(name,[sr['vertices'][i] for i in used],[[idx[i] for i in f] for f in faces],review_mat)
        o=bpy.data.objects.new(name,me);col.objects.link(o);o['qa_status']='SOURCE_REFERENCE_NOT_REBUILT';o['reason']=p['reason'];o['source_name']=t['source']
    prototypes[t['id']]=col
    if t['category'] in ['WINDOW','DOOR']:
        col.asset_mark();col.asset_data.description=f"Measured FBX geometry. {len(t['instances'])} instances. Materials unconfirmed. QA: {col['qa_status']}."

def setup_scene(name):
    s=bpy.data.scenes.new(name);s.unit_settings.system='METRIC';s.unit_settings.scale_length=1
    s.render.engine='BLENDER_WORKBENCH';s.display.shading.light='STUDIO';s.display.shading.color_type='MATERIAL';s.display.shading.show_shadows=True;s.display.shading.show_cavity=True
    s.display.shading.cavity_type='BOTH';s.display.shading.background_type='WORLD';s.world=bpy.data.worlds.new(name+'_World');s.world.color=(.8,.8,.8)
    s['status']='WORKING_LIBRARY_VISUAL_REVIEW_PENDING';s['source_snapshot']=str(root/'outputs/source-v001/source-snapshot.blend')
    return s

def instance(col,s,name,location=(0,0,0),matrix=None):
    o=bpy.data.objects.new(name,None);o.instance_type='COLLECTION';o.instance_collection=col;s.collection.objects.link(o)
    if matrix is None:o.location=location
    else:o.matrix_world=Matrix(matrix)
    return o

def label(s,text,x,z,size=.17):
    d=bpy.data.curves.new('Label','FONT');d.body=text;d.size=size;d.align_x='LEFT';d.extrude=0
    o=bpy.data.objects.new(text,d);s.collection.objects.link(o);o.rotation_euler=(math.pi/2,0,0);o.location=(x,-.08,z)
    d.materials.append(frame_mat)

windows=setup_scene('01_WINDOWS_34_VARIANTS')
doors=setup_scene('02_DOORS_127_VARIANTS')
curtains=setup_scene('03_CURTAIN_SYSTEMS_167_CANDIDATES')
for cat,scene,columns,pitch in [('WINDOW',windows,7,3.2),('DOOR',doors,9,2.9)]:
    ts=sorted([t for t in types if t['category']==cat],key=lambda t:t['id'])
    for i,t in enumerate(ts):
        x=(i%columns)*pitch;z=-(i//columns)*4
        o=instance(prototypes[t['id']],scene,t['id'],(x,0,z));o['source_instances']=len(t['instances']);o['qa_status']=prototypes[t['id']]['qa_status']
        label(scene,f"{t['id']}  x{len(t['instances'])}",x,z-.35)

rowx=0;rowz=0;rowheight=0
for t in systems:
    col=bpy.data.collections.new(t['id']);col['grouping_method']='2mm AABB adjacency: logical system boundaries require review';col['source_instance_count']=len(t['placements'])
    col['source_assembly']=t['source_assembly'];col['qa_status']='ASSEMBLY_CONTACT_QA_PENDING';col['source_members']=json.dumps(t['placements'][0]['source_members'],ensure_ascii=False)
    for i,m in enumerate(t['members']):
        o=bpy.data.objects.new(f"{t['id']}_{i:04d}_{m['type']}",None);o.instance_type='COLLECTION';o.instance_collection=prototypes[m['type']];o.matrix_world=Matrix(m['matrix']);col.objects.link(o);o['source_name']=m['source']
    col.asset_mark();col.asset_data.description=f"Candidate assembled curtain system; {len(t['placements'])} occurrences; grouping/contact QA pending."
    w,dep,h=t['dimensions']
    if rowx+w>45 and rowx>0:rowx=0;rowz-=rowheight+1.8;rowheight=0
    instance(col,curtains,t['id'],(rowx,0,rowz));label(curtains,f"{t['id']}  x{len(t['placements'])}",rowx,rowz-.4,.22)
    rowx+=w+1.2;rowheight=max(rowheight,h)
    prototypes[t['id']]=col

# A separate source-layout scene provides provenance and makes outliers visible.
source_layout=setup_scene('04_CURTAIN_SOURCE_PLACEMENTS')
for t in systems:
    for p in t['placements']:instance(prototypes[t['id']],source_layout,p['assembly'],matrix=p['to_world'])

readme=bpy.data.texts.new('READ_ME_RU')
readme.write('Библиотека геометрических вариантов по FBX Revit.\n34 окна, 127 дверей, 167 кандидатов витражных систем.\nЭто рабочая версия: проверка стыков и визуальная приёмка не завершены.\nСиние панели — диагностическая гипотеза стекла, проектных материалов в FBX нет.\nОранжевая геометрия — исходные сложные детали, ещё не перестроенные.\nМелкая фурнитура не входит в core-модели; сохранена в source-snapshot.blend.\nИдентичность штатным типам Revit не установлена: это геометрические варианты.\nОригинальная сцена и размещения сохранены отдельно; типы доступны как Collection Assets.\n')
if bpy.context.window:bpy.context.window.scene=windows
bpy.data.scenes.remove(default)
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            space=area.spaces.active;space.shading.type='SOLID';space.shading.color_type='MATERIAL';space.clip_end=2000
            space.region_3d.view_rotation=(Vector((0,-1,0))).to_track_quat('Z','Y')
            space.region_3d.view_location=Vector((10,0,-6));space.region_3d.view_distance=25;space.region_3d.view_perspective='ORTHO'
out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'Revit_Openings_Library_v001.blend'))
(out/'build-manifest.json').write_text(json.dumps({'status':'WORKING_LIBRARY_QA_PENDING','scenes':[s.name for s in bpy.data.scenes],'assets':sum(c.asset_data is not None for c in bpy.data.collections),'objects':len(bpy.data.objects),'meshes':len(bpy.data.meshes),'generated_parts':qa,'source_materials':0},ensure_ascii=False),encoding='utf-8')
print(json.dumps({'saved':str(out/'Revit_Openings_Library_v001.blend'),'scenes':len(bpy.data.scenes),'assets':sum(c.asset_data is not None for c in bpy.data.collections),'meshes':len(bpy.data.meshes)}))
