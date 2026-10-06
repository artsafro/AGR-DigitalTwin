"""Facade samples: measured panel outlines, one recessed skin, two material IDs."""
import bpy,json,math
from pathlib import Path
from mathutils import Vector,Matrix
import numpy as np
ROOT=Path('C:/Users/artsafro/.AGR_Project/jobs/REVIT-OPENINGS')
OUT=ROOT/'outputs/simple-v002';OUT.mkdir(parents=True,exist_ok=True)
src=ROOT/'outputs/source-v001'
types={t['id']:t for t in json.loads((src/'types.json').read_text(encoding='utf-8'))}
cores={t['id']:t for t in json.loads((ROOT/'outputs/library-v001/rebuilt-core.json').read_text(encoding='utf-8'))}
systems=json.loads((ROOT/'outputs/library-v001/curtain-types.json').read_text(encoding='utf-8'))

def panes(tid,matrix=None):
    m=np.eye(4) if matrix is None else np.array(matrix)
    out=[]
    for p in cores[tid]['parts']:
        if p['role'] not in ['GLASS','GLASS_CANDIDATE']:continue
        v=np.array(p['vertices']);v=v@m[:3,:3].T+m[:3,3];lo=v.min(axis=0);hi=v.max(axis=0)
        out.append({'rect':[round(float(lo[0]),4),round(float(lo[2]),4),round(float(hi[0]),4),round(float(hi[2]),4)],
                    'source_type':tid,'source_component':p['component'],'source_depth':round(float(lo[1]),4)})
    return out

cw=next(t for t in systems if t['id']=='CW_001')
wide_panes=[p for m in cw['members'] for p in panes(m['type'],m['matrix'])]
door=max((t for t in types.values() if t['category']=='DOOR' and 'AC_ДверьВитражная_Двупольная' in t['source'] and 1.5<t['dimensions'][0]<1.7),key=lambda t:len(t['instances']))
specs=[{'id':'W01_WIDE_3_BAYS','label':'W01  3 bays / 5 panes','width':round(cw['dimensions'][0],4),'height':round(cw['dimensions'][2],4),'panes':wide_panes,'source':'CW_001','source_occurrences':len(cw['placements']),'references':['reference-01.png','reference-06.png']},
       {'id':'W02_TWO_BAYS','label':'W02  2 bays / 4 panes','width':2.05,'height':2.85,'panes':panes('WINDOW_027'),'source':'WINDOW_027','references':['reference-01.png','reference-02.png','reference-06.png']},
       {'id':'W03_NARROW','label':'W03  narrow / 3 panes','width':.85,'height':2.85,'panes':panes('WINDOW_025'),'source':'WINDOW_025','references':['reference-02.png','reference-03.png','reference-06.png']},
       {'id':'D01_GLAZED_DOUBLE','label':'D01  glazed double door','width':round(door['dimensions'][0],4),'height':round(door['dimensions'][2],4),'panes':panes(door['id']),'source':door['id'],'references':['reference-06.png'],'reference_status':'opening schematic; detailed doorway match pending'}]

# Ignore protruding hardware: take the measured outer frame, normalized to its lower left.
for s in specs:
    if s['source'].startswith('WINDOW'):
        t=cores[s['source']];v=np.array([p for part in t['parts'] if part['role']=='FRAME_LEAF' for p in part['vertices']]);lo=v.min(axis=0);hi=v.max(axis=0)
        s['width']=round(float(hi[0]-lo[0]),4);s['height']=round(float(hi[2]-lo[2]),4)
        for p in s['panes']:
            p['rect']=[round(p['rect'][0]-float(lo[0]),4),round(p['rect'][1]-float(lo[2]),4),round(p['rect'][2]-float(lo[0]),4),round(p['rect'][3]-float(lo[2]),4)]
    depths=[p['source_depth'] for p in s['panes'] if p['source_depth']>0]
    s['recess']=round(float(np.median(depths)),4) if depths else .03
    s['depth_method']='median measured front surface of source infill; individual frame steps simplified'
    s['status']='SAMPLE_NOT_APPROVED';s['material_ids']={'1':'frame_and_mullions','2':'infill'}

def skin(spec):
    w=spec['width'];h=spec['height'];depth=spec['recess']
    rects=[p['rect'] for p in spec['panes']]
    assert all(0<=x0<x1<=w+.0001 and 0<=z0<z1<=h+.0001 for x0,z0,x1,z1 in rects)
    xs=sorted(set([0,w]+[r[i] for r in rects for i in [0,2]]));zs=sorted(set([0,h]+[r[i] for r in rects for i in [1,3]]))
    verts=[];faces=[];ids=[];lookup={};levels={}
    def vid(x,y,z):
        key=(round(x,6),round(y,6),round(z,6))
        if key not in lookup:lookup[key]=len(verts);verts.append(key)
        return lookup[key]
    for i in range(len(xs)-1):
        for j in range(len(zs)-1):
            x=(xs[i]+xs[i+1])/2;z=(zs[j]+zs[j+1])/2
            inside=any(a<x<c and b<z<d for a,b,c,d in rects)
            y=depth if inside else 0;levels[i,j]=y
            faces.append([vid(xs[i],y,zs[j]),vid(xs[i+1],y,zs[j]),vid(xs[i+1],y,zs[j+1]),vid(xs[i],y,zs[j+1])]);ids.append(1 if inside else 0)
    # Each step is one quad per boundary segment, welded to both surface levels.
    for (i,j),y in levels.items():
        if y!=0:continue
        edges=[((i,j-1),((xs[i],zs[j]),(xs[i+1],zs[j]))),((i+1,j),((xs[i+1],zs[j]),(xs[i+1],zs[j+1]))),((i,j+1),((xs[i+1],zs[j+1]),(xs[i],zs[j+1]))),((i-1,j),((xs[i],zs[j+1]),(xs[i],zs[j])))]
        for neighbor,(a,b) in edges:
            if levels.get(neighbor,0)>0:
                yy=levels[neighbor];faces.append([vid(*[b[0],0,b[1]]),vid(*[a[0],0,a[1]]),vid(*[a[0],yy,a[1]]),vid(*[b[0],yy,b[1]])]);ids.append(0)
    return verts,faces,ids

bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene;scene.name='SIMPLE_OPENINGS_v002';scene.unit_settings.system='METRIC'
frame=bpy.data.materials.new('ID01_FRAME');frame.diffuse_color=(.07,.085,.10,1)
glass=bpy.data.materials.new('ID02_INFILL');glass.diffuse_color=(.30,.44,.51,1)
for m in [frame,glass]:m['status']='preview based on references; exact finish not assigned'
models=bpy.data.collections.new('SIMPLE_OPENINGS_MODELS_v002');scene.collection.children.link(models)
labels=bpy.data.collections.new('PRESENTATION_LABELS');scene.collection.children.link(labels)
x=0
for s in specs:
    v,f,ids=skin(s);me=bpy.data.meshes.new(s['id']);me.from_pydata(v,[],f);me.update();me.materials.append(frame);me.materials.append(glass)
    attr=me.attributes.new('Material_ID','INT','FACE')
    for p,mi,a in zip(me.polygons,ids,attr.data):p.material_index=mi;a.value=mi+1
    # Physical planar UV in metres; finish/atlas assignment is a later task.
    uv=me.uv_layers.new(name='UVMap')
    for p in me.polygons:
        axis=max(range(3),key=lambda i:abs(p.normal[i]));axes=[i for i in range(3) if i!=axis]
        for li in p.loop_indices:
            co=me.vertices[me.loops[li].vertex_index].co;uv.data[li].uv=(co[axes[0]],co[axes[1]])
    o=bpy.data.objects.new(s['id'],me);models.objects.link(o);o.location=(x,0,0)
    o['source_reference']=s['source'];o['status']='SAMPLE_NOT_APPROVED';o['construction']='single facade skin with recessed infill; exterior perimeter intentionally open';o['hardware']='omitted per user';o['source_rectangles']=json.dumps(s['panes'])
    o.asset_mark();o.asset_data.description='Simplified plane/inset/recess, two IDs; no hardware. Visual review pending.'
    s['faces']=len(f);s['vertices']=len(v);s['gallery_x']=x
    d=bpy.data.curves.new(s['id']+'_label','FONT');d.body=s['label'];d.size=.14;d.materials.append(frame)
    ob=bpy.data.objects.new(s['id']+'_label',d);labels.objects.link(ob);ob.rotation_euler=(math.pi/2,0,0);ob.location=(x,-.02,-.32)
    x+=s['width']+.7
scene['source_snapshot']=str(src/'source-snapshot.blend');scene['status']='FOUR_SAMPLES_NOT_FULL_TYPE_LIBRARY'
readme=bpy.data.texts.new('README_RU');readme.write('Четыре первых образца по FBX и визуализациям.\nОдна фасадная поверхность: профиль ID1, заполнение ID2, небольшое заглубление.\nБез ручек, доводчиков, обратных стенок и многослойных профилей.\nВнешний периметр намеренно открыт, внутренние стыки сварены.\nЭто образцы для проверки подхода, не полный перечень типов.\nЦвета приблизительные, UV в метрах без атласа.\nИсходный Revit/FBX не изменён.\n')
scene.world=bpy.data.worlds.new('PreviewWorld')
scene.render.engine='BLENDER_WORKBENCH';scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL';scene.display.shading.show_shadows=False;scene.display.shading.show_cavity=True;scene.display.shading.cavity_type='BOTH';scene.display.shading.background_type='WORLD';scene.world.color=(.8,.8,.8)
scene.render.resolution_x=1800;scene.render.resolution_y=680;scene.render.resolution_percentage=100
camd=bpy.data.cameras.new('PreviewCamera');cam=bpy.data.objects.new('PreviewCamera',camd);scene.collection.objects.link(cam);scene.camera=cam;camd.type='ORTHO';camd.ortho_scale=x+.15
center=Vector(((x-.7)/2,0,1.25));cam.location=center+Vector((0,-18,0));cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            space=area.spaces.active;space.shading.color_type='MATERIAL';space.region_3d.view_rotation=cam.rotation_euler.to_quaternion();space.region_3d.view_location=center;space.region_3d.view_distance=x;space.region_3d.view_perspective='ORTHO'
for o in models.objects:o.select_set(True)
bpy.context.view_layer.objects.active=models.objects[0]
(OUT/'sample-specs.json').write_text(json.dumps(specs,ensure_ascii=False,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Simple_Openings_v002.blend'))
scene.render.filepath=str(OUT/'samples-front.png');bpy.ops.render.render(write_still=True)
print(json.dumps({'models':len(specs),'quads':sum(s['faces'] for s in specs),'file':str(OUT/'Simple_Openings_v002.blend')}))
