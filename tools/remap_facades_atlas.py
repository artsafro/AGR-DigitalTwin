"""Metric material-band atlases for the explicitly supplied facades.blend.

Run only in background Blender on source; writes a NEW directory and scene.
"""
import bpy,json,sys,math,hashlib
from pathlib import Path
from collections import Counter
import numpy as np
from mathutils import Vector

out=Path(sys.argv[sys.argv.index('--')+1]).resolve()
out.mkdir(parents=True,exist_ok=False)
N=2048;D=80.;PAD=16
# Pixel rectangles are half-open. Internal pattern has physical panel-sized periods.
regions={101:(16,16,2016,288),102:(16,336,2016,384),103:(16,752,2016,384),
         104:(16,1168,2016,384),105:(16,1584,2016,384)}
periods={101:(1.6,1.2),102:(1.2,1.6),103:(1.2,1.6),104:(1.2,1.6),105:(1.2,1.6)}
# Original names retained. Numbering follows user size description, NOT legacy bitmap suffix.
corpora={'Object012':'01','Object009':'02','Object010':'03'}
baseline={};qa={};manifest={'atlas_size':N,'sampling_px_m':D,'sampling_is_not_NPM_OKS_requirement':True,
    'panel_dimensions_m':periods,'brick_m':[.25,.065],'brick_joint_m':.01,
    'panel_joint_m':.005,'panel_dimensions_include_joint':True,'regions_px':regions,'objects':{},
    'source_blend':bpy.data.filepath,'source_sha256':hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest()}

def geom_hash(o):
 m=o.data
 return hashlib.sha256(json.dumps({'v':[v.co[:] for v in m.vertices],
     'f':[p.vertices[:] for p in m.polygons],'ids':[p.material_index for p in m.polygons],
     'matrix':list(map(list,o.matrix_world))},sort_keys=True).encode()).hexdigest()

def pattern(mid,x,y,color):
 pw,ph=periods[mid]
 px=x%pw;py=y%ph
 if mid==101:
  row=np.floor(py/.075)
  col=np.floor((px+(row%2)*.13)/.26)
  mortar=((py%.075)<.01)|(((px+(row%2)*.13)%.26)<.01)
  variation=.92+.12*(.5+.5*np.sin(col*12.31+row*43.11))
  texture=.985+.015*np.sin(x*370+np.sin(y*211))*np.sin(y*470)
  rgb=np.broadcast_to(color,(*np.broadcast_shapes(x.shape,y.shape),3))*variation[...,None]*texture[...,None]
  rgb=np.where(mortar[...,None],np.array([.29,.265,.23]),rgb)
 else:
  rgb=np.broadcast_to(color,(*np.broadcast_shapes(x.shape,y.shape),3)).copy()
 # A 5mm panel joint lies inside the nominal 1200x1600 / 1600x1200 module.
 joint=(px<.005)|(py<.005)
 return np.clip(np.where(joint[...,None],np.array(color)*.40,rgb),0,1)

for o in [x for x in bpy.data.objects if x.type=='MESH']:
 if o.name not in corpora:raise ValueError('Unexpected mesh '+o.name)
 cid=corpora[o.name];m=o.data;baseline[o.name]=geom_hash(o)
 old=m.uv_layers.active
 if old is None:raise ValueError('Source UV required')
 source_uv=np.array([d.uv[:] for d in old.data]);uvhash=hashlib.sha256(source_uv.tobytes()).hexdigest()
 # Identify base colors by sampling the existing ID's atlas. Keep source color differences.
 colors={};images={}
 for mid in range(101,106):
  mat=m.materials[mid-1]
  img=next(n.image for n in mat.node_tree.nodes if n.type=='TEX_IMAGE' and n.image)
  if img.name not in images:images[img.name]=np.array(img.pixels[:],dtype=np.float32).reshape(img.size[1],img.size[0],4)
  arr=images[img.name];faces=[p for p in m.polygons if p.material_index==mid-1]
  samples=[]
  for p in faces:
   u,v=source_uv[list(p.loop_indices)].mean(0)
   samples.append(tuple(np.round(arr[int(v*img.size[1])%img.size[1],int(u*img.size[0])%img.size[0],:3],3)))
  # For brick preserve the warm body pixels, excluding grout/other atlas islands.
  if mid==101:
   samples=[c for c in samples if c[0]>c[1]*1.12 and c[1]>c[2]*1.1 and c[0]>.45]
   if not samples:
    warm=arr[:,:,:3];mask=(warm[:,:,0]>warm[:,:,1]*1.12)&(warm[:,:,1]>warm[:,:,2]*1.1)&(warm[:,:,0]>.45)
    samples=[tuple(x) for x in warm[mask][::20]]
   color=np.median(samples,axis=0)
  elif samples:color=np.array(Counter(samples).most_common(1)[0][0])
  else:color=np.array([.498,.498,.498]) # Unused ID103 in Object009; source gray sample.
  colors[mid]=color.tolist()
 atlas=np.zeros((N,N,4),dtype=np.float32);atlas[:,:,3]=1
 # Supersample analytical joints for stable sub-pixel lines at NPM resolution.
 for mid,(x0,y0,w,h) in regions.items():
  xs=(np.arange(w+2*PAD)-PAD)[None,:]/D
  ys=(np.arange(h+2*PAD)-PAD)[:,None]/D
  rgb=np.zeros((h+2*PAD,w+2*PAD,3),dtype=np.float32)
  for dx,dy in [(a,b) for a in (.125,.375,.625,.875) for b in (.125,.375,.625,.875)]:
   rgb+=pattern(mid,xs+dx/D,ys+dy/D,colors[mid])/16
  atlas[y0-PAD:y0+h+PAD,x0-PAD:x0+w+PAD,:3]=rgb
 img=bpy.data.images.new(f'T_Facades_{cid}_Atlas_d',width=N,height=N,alpha=False)
 img.colorspace_settings.name='sRGB';img.pixels.foreach_set(atlas.ravel())
 img.filepath_raw=str(out/f'T_Facades_{cid}_Atlas_d.png');img.file_format='PNG';img.save();img.pack()
 uv=m.uv_layers.new(name='Atlas_Metric_v002',do_init=False)
 world=np.array([o.matrix_world@v.co for v in m.vertices]);origin=world.min(0)
 records=[];max_error=0;outside=0
 for p in m.polygons:
  mid=p.material_index+1
  if mid not in regions:raise ValueError('Unexpected ID '+str(mid))
  q=world[list(p.vertices)]
  # Newell normal, independent of any custom vertex normal shading.
  normal=np.cross(q-np.mean(q,axis=0),np.roll(q,-1,axis=0)-np.mean(q,axis=0)).sum(0)
  length=np.linalg.norm(normal)
  if length<1e-12:raise ValueError(f'Degenerate polygon {o.name}:{p.index}')
  normal/=length
  if abs(normal[2])<.999:
   tangent=np.cross([0,0,1],normal);tangent/=np.linalg.norm(tangent)
   # Canonical orientation is independent of face winding/opposite facade sides.
   if tangent[np.argmax(abs(tangent))]<0:tangent=-tangent
   vertical=np.cross(normal,tangent)
   if vertical[2]<0:vertical=-vertical
  else:
   edges=q-np.roll(q,1,axis=0)
   tangent=edges[np.argmax(np.linalg.norm(edges,axis=1))];tangent=tangent/np.linalg.norm(tangent)
   if tangent[np.argmax(abs(tangent))]<0:tangent=-tangent
   vertical=np.cross(normal,tangent)
   if vertical[np.argmax(abs(vertical))]<0:vertical=-vertical
  xy=np.stack(((q-origin)@tangent,(q-origin)@vertical),axis=1)
  lo=xy.min(0);shift=np.floor((lo+1e-9)/np.array(periods[mid]))*np.array(periods[mid])
  folded=xy-shift
  # Tiny FP negatives are corrected by an entire repeat, never by stretching.
  for axis in range(2):
   if folded[:,axis].min() < -1e-8:folded[:,axis]+=periods[mid][axis];shift[axis]-=periods[mid][axis]
  x0,y0,w,h=regions[mid]
  if (folded.min(0)<-1e-7).any() or (folded.max(0)*D>np.array([w,h])+1e-5).any():
   raise ValueError(f'Face does not fit material band: {o.name}:{p.index}, ID{mid}, {folded.max(0)}')
  mapped=(folded*D+np.array([x0,y0]))/N
  for li,value in zip(p.loop_indices,mapped):uv.data[li].uv=value
  edge=np.linalg.norm(q-np.roll(q,1,axis=0),axis=1)
  edgeuv=np.linalg.norm(xy-np.roll(xy,1,axis=0),axis=1)
  error=float(np.max(abs(edge-edgeuv)))
  max_error=max(max_error,error)
  records.append({'face':p.index,'id':mid,'tangent':tangent.tolist(),'vertical':vertical.tolist(),'shift_m':shift.tolist(),'projection_edge_error_m':error})
 m.uv_layers.active=uv;uv.active_render=True
 # Keep slot indices / IDs; clone shaders locally and explicitly select the new UV layer.
 for mid in range(101,106):
  mat=m.materials[mid-1].copy();mat.name=f'M_Facades_{cid}_ID{mid}_d';m.materials[mid-1]=mat
  nodes=mat.node_tree.nodes;links=mat.node_tree.links
  uvnode=nodes.new('ShaderNodeUVMap');uvnode.uv_map=uv.name
  for node in nodes:
   if node.type=='TEX_IMAGE':
    node.image=img;node.interpolation='Linear';node.extension='EXTEND';links.new(uvnode.outputs['UV'],node.inputs['Vector'])
 o['corpus_by_user_size']=cid;o['atlas_recipe']='FACADES-ATLAS/metric-v002'
 if geom_hash(o)!=baseline[o.name]:raise AssertionError('Geometry or ID mutation')
 manifest['objects'][o.name]={'corpus':cid,'source_images':list(images),'base_colors':colors,'faces':len(m.polygons),
    'geometry_hash':baseline[o.name],'original_uv_layer':old.name,'original_uv_hash':uvhash,'new_uv_layer':uv.name,
    'origin_m':origin.tolist(),'records_file':f'{o.name}_uv_records.json','max_projection_edge_error_m':max_error,
    'polygon_degrees':dict(Counter(len(p.vertices) for p in m.polygons))}
 (out/f'{o.name}_uv_records.json').write_text(json.dumps(records),encoding='utf-8')
 print('MAPPED',o.name,cid,len(records),'max_projection_error',max_error)
(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
bpy.data.texts.new('ATLAS_RECIPE.json').write(json.dumps(manifest,ensure_ascii=False,indent=2))
bpy.ops.wm.save_as_mainfile(filepath=str(out/'facades_metric_v002.blend'))
print('SAVED',out)
