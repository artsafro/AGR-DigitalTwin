import bpy,json,numpy as np,sys,zlib,struct,math
from pathlib import Path
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).parent));from npm_surface import Field
R=Path(r'C:/Users/artsafro/.AGR_Project/jobs/GROUND-PROJECTION/outputs/v008');D=np.load(R/'quad_mesh.npz');v=D['vertices'];f=D['faces'];m=D['materials']
bpy.ops.wm.open_mainfile(filepath=str(R.parent/'v001/source_import.blend'))
s=bpy.context.scene;s.unit_settings.system='METRIC';s.unit_settings.scale_length=1
original_mats=list(bpy.data.objects['Ground'].data.materials);materials=[];names=[];colors=[]
for mat in original_mats:
 name=mat.name;names.append(name);colors.append(list(mat.diffuse_color[:3]));mat.name='REFERENCE_'+name;copy=mat.copy();copy.name=name;materials.append(copy)
# Corrected physical scale, also for the hidden reference meshes.
for o in list(s.objects):
 o.matrix_world.translation*=.01;o.scale*=.01;o.hide_set(True);o.hide_render=True;o.select_set(False)
origin=np.array([79.44,0,0]);mesh=bpy.data.meshes.new('GROUND_NPM_QUADS');mesh.from_pydata((v-origin).tolist(),[],f.tolist());mesh.update()
o=bpy.data.objects.new('SM_GROUND_NPM_Ground',mesh);s.collection.objects.link(o);o.location=origin
for mat in materials:mesh.materials.append(mat)
mesh.polygons.foreach_set('material_index',m.astype(np.int32));mesh.polygons.foreach_set('use_smooth',np.ones(len(f),dtype=bool))
field=Field(R/'heightfield.npz');eps=.01
dx=(field.sample(v[:,:2]+[eps,0])-field.sample(v[:,:2]-[eps,0]))/(2*eps);dy=(field.sample(v[:,:2]+[0,eps])-field.sample(v[:,:2]-[0,eps]))/(2*eps)
normals=np.column_stack((-dx,-dy,np.ones(len(v))));normals/=np.linalg.norm(normals,axis=1)[:,None];mesh.normals_split_custom_set_from_vertices(normals.tolist())
# Exact solid source colors, not invented paving/grass texture patterns.
res=1024;rgb=np.zeros((res,res,3),dtype=np.uint8);cells=[]
for i,c in enumerate(colors):
 x0=round((i%6)*res/6);x1=round((i%6+1)*res/6);y0=round((i//6)*res/3);y1=round((i//6+1)*res/3)
 a=np.array(c);srgb=np.where(a<=.0031308,12.92*a,1.055*np.power(a,1/2.4)-.055);col=np.clip(np.round(srgb*255),0,255).astype(np.uint8)
 rgb[res-y1:res-y0,x0:x1]=col;cells.append((x0,y0,x1,y1))
def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',res,res,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(b'\x00'+row.tobytes() for row in rgb),9))+chunk(b'IEND',b'')
tex=R/'GROUND_NPM_source_colors.png';tex.write_bytes(png);img=bpy.data.images.load(str(tex));img.pack()
for mat in materials:
 mat.use_nodes=True;bsdf=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
 for link in list(bsdf.inputs['Base Color'].links):mat.node_tree.links.remove(link)
 node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=img;node.interpolation='Linear';mat.node_tree.links.new(node.outputs['Color'],bsdf.inputs['Base Color'])
uv=mesh.uv_layers.new(name='NPM_20px_m');uvs=[];uv_report=[]
for poly,face,mat in zip(mesh.polygons,f,m):
 p=v[face];n=np.cross(p[1]-p[0],p[2]-p[0])+np.cross(p[2]-p[0],p[3]-p[0]);n/=np.linalg.norm(n)
 e=p[1]-p[0];e-=n*np.dot(e,n);e/=np.linalg.norm(e);b=np.cross(n,e);q=np.column_stack(((p-p.mean(axis=0))@e,(p-p.mean(axis=0))@b))
 area=abs(np.sum(q[:,0]*np.roll(q[:,1],-1)-q[:,1]*np.roll(q[:,0],-1)))/2
 q*=math.sqrt(poly.area/area)*20/res
 x0,y0,x1,y1=cells[mat];center=np.array([(x0+x1)/2,(y0+y1)/2])/res;q+=center
 if not (np.all(q.min(axis=0)>np.array([x0+8,y0+8])/res) and np.all(q.max(axis=0)<np.array([x1-8,y1-8])/res)):
  raise ValueError({'face':poly.index,'xyz':p.tolist(),'polyarea':poly.area,'flat_area':area,'uv_span_px':(np.ptp(q,axis=0)*res).tolist(),'mat':int(mat)})
 for loop,coord in zip(poly.loop_indices,q):uv.data[loop].uv=coord
 uvs.append(q)
o['units']='Meters; source world coordinates multiplied by0.01 after user confirmed116x164m extent'
o['terrain']='Simplified smooth field:0.25m height quantization,1.6m Gaussian sigma; micro steps suppressed'
o['source_overlaps']='Different-ID footprint overlaps retained by user instruction'
o['UV']='20px/m target; source solid colors, shared1024RGB atlas; same-material UV overlaps intentional'
o.select_set(True);bpy.context.view_layer.objects.active=o
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   sp=area.spaces.active;sp.clip_end=2000;sp.shading.type='SOLID';sp.shading.color_type='MATERIAL';sp.region_3d.view_location=Vector((23,38,2));sp.region_3d.view_distance=200
bpy.ops.wm.save_as_mainfile(filepath=str(R/'GROUND_NPM_v008.blend'))
common=dict(use_selection=True,object_types={'MESH'},axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',use_mesh_modifiers=False,mesh_smooth_type='OFF',bake_anim=False,add_leaf_bones=False,path_mode='COPY',embed_textures=True,use_custom_props=True)
bpy.ops.export_scene.fbx(filepath=str(R/'GROUND_NPM_QUADS_v008.fbx'),use_triangles=False,**common)
# Explicit fixed diagonals preserve both triangles and material IDs of every quad.
tf=np.stack((f[:,[0,1,2]],f[:,[0,2,3]]),axis=1).reshape(-1,3)
tm=bpy.data.meshes.new('NPM_TRI_EXPORT');tm.from_pydata((v-origin).tolist(),[],tf.tolist());tm.update()
for mat in materials:tm.materials.append(mat)
tm.polygons.foreach_set('material_index',np.repeat(m,2).astype(np.int32));tm.polygons.foreach_set('use_smooth',np.ones(len(tf),dtype=bool));tm.normals_split_custom_set_from_vertices(normals.tolist())
tu=tm.uv_layers.new(name='NPM_20px_m');quv=np.array(uvs);tuv=np.stack((quv[:,[0,1,2]],quv[:,[0,2,3]]),axis=1).reshape(-1,3,2)
for poly,face,mat in zip(tm.polygons,tf,np.repeat(m,2)):
 p=v[face];e=p[1]-p[0];e/=np.linalg.norm(e);n=np.cross(p[1]-p[0],p[2]-p[0]);n/=np.linalg.norm(n);b=np.cross(n,e)
 q=np.column_stack(((p-p.mean(axis=0))@e,(p-p.mean(axis=0))@b));area=abs(np.linalg.det(np.array([q[1]-q[0],q[2]-q[0]])))*.5
 q*=math.sqrt(poly.area/area)*20/res;x0,y0,x1,y1=cells[mat];q+=np.array([(x0+x1)/2,(y0+y1)/2])/res
 for li,coord in zip(poly.loop_indices,q):tu.data[li].uv=coord
o.data=tm
bpy.ops.export_scene.fbx(filepath=str(R/'GROUND_NPM_TRI_v008.fbx'),use_triangles=False,**common)
o.data=mesh
np.savez_compressed(R/'expected.npz',vertices=v,faces=f,materials=m,uv=np.array(uvs))
(R/'material_ids.json').write_text(json.dumps([{'id':i+1,'name':name,'source_linear_rgb':colors[i],'atlas_pixel_rect':cells[i],'faces':int((m==i).sum())} for i,name in enumerate(names)],ensure_ascii=False,indent=2),encoding='utf-8')
print('SAVED',len(v),len(f),'TRI',len(f)*2)




