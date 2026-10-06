import bpy,json,numpy as np,sys,hashlib,collections,importlib.util
from pathlib import Path
from io_scene_fbx import parse_fbx
R=Path(r'C:/Users/artsafro/.AGR_Project/jobs/GROUND-PROJECTION/outputs/v008');D=np.load(R/'expected.npz');mapping=json.loads((R/'material_ids.json').read_text(encoding='utf-8'))
spec=importlib.util.spec_from_file_location('installed_td',R/'checker_td_snapshot.py');td=importlib.util.module_from_spec(spec);spec.loader.exec_module(td)
reports=[]
for variant in ['QUADS','TRI']:
 bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.unit_settings.system='METRIC';bpy.context.scene.unit_settings.scale_length=1
 path=R/f'GROUND_NPM_{variant}_v008.fbx';bpy.ops.import_scene.fbx(filepath=str(path),use_image_search=False)
 objects=[o for o in bpy.context.scene.objects if o.type=='MESH'];assert len(objects)==1
 o=objects[0];mesh=o.data;local=np.array([v.co[:] for v in mesh.vertices]);matrix=np.array(o.matrix_world);v=local@matrix[:3,:3].T+matrix[:3,3];f=np.array([p.vertices[:] for p in mesh.polygons]);m=np.array([p.material_index for p in mesh.polygons]);uv=np.array([[mesh.uv_layers.active.data[i].uv[:] for i in p.loop_indices] for p in mesh.polygons])
 points=v[f];area=np.zeros(len(f))
 for k in range(1,f.shape[1]-1):area+=np.linalg.norm(np.cross(points[:,k]-points[:,0],points[:,k+1]-points[:,0]),axis=1)*.5
 folded=0
 if variant=='QUADS':
  a=np.cross(points[:,1]-points[:,0],points[:,2]-points[:,0]);b=np.cross(points[:,2]-points[:,0],points[:,3]-points[:,0]);folded=int((a[:,2]*b[:,2]<-1e-15).sum())
 e=np.sort(np.concatenate([f[:,[i,(i+1)%f.shape[1]]] for i in range(f.shape[1])]),axis=1);eu,ec=np.unique(e,axis=0,return_counts=True)
 values=td._calculate_td(o,{1001:1024},False);dens=np.array(values[0])
 root,ver=parse_fbx.parse(str(path));objects_raw=next(x for x in root.elems if x.id==b'Objects');geom=next(x for x in objects_raw.elems if x.id==b'Geometry');layer=next(x for x in geom.elems if x.id==b'LayerElementMaterial');ids=next(x.props[0] for x in layer.elems if x.id==b'Materials')
 embedded=[]
 for item in objects_raw.elems:
  if item.id==b'Video':
   for c in item.elems:
    if c.id==b'Content' and c.props:embedded.append(hashlib.sha256(c.props[0]).hexdigest())
 png_hash=hashlib.sha256((R/'GROUND_NPM_source_colors.png').read_bytes()).hexdigest()
 report={'variant':variant,'fbx_version':ver,'vertices':len(v),'faces':len(f),'polygon_sides':f.shape[1],'material_slots':len(mesh.materials),'material_names_equal':[s.name for s in mesh.materials]==[x['name'] for x in mapping],'material_ids_equal':bool(np.array_equal(m,D['materials'] if variant=='QUADS' else np.repeat(D['materials'],2))),'raw_material_ids_equal':bool(np.array_equal(ids,m)),'exact_duplicate_vertices':len(v)-len(np.unique(v,axis=0)),'duplicate_faces':len(f)-len(np.unique(np.sort(f,axis=1),axis=0)),'zero_area_faces':int((area<1e-13).sum()),'folded_quads':folded,'boundary_edges':int((ec==1).sum()),'nonmanifold_edges':int((ec>2).sum()),'loose_vertices':len(v)-len(np.unique(f)),'smallest_area_m2':float(area.min()),'extent_m':np.ptp(v,axis=0).tolist(),'embedded_png_verified':png_hash in embedded,'uv_channels':len(mesh.uv_layers),'uv_range':[float(uv.min()),float(uv.max())],'checker_2_6_1':{'checked_faces':len(dens),'density_min':float(dens.min()),'density_max':float(dens.max()),'density_median':float(np.median(dens)),'below10':len(values[5]),'above40':len(values[6]),'source':'installed CheckUtils._calculate_td, unmodified AST body; not whole-addon compliance'},'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
 np.savez_compressed(R/f'readback_{variant}.npz',vertices=v,faces=f,materials=m,uv=uv)
 reports.append(report);print(json.dumps(report,ensure_ascii=False,indent=2))
(R/'readback.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
(R/'AGRChecker_data').mkdir(exist_ok=True);(R/'AGRChecker_data/td_ground_readback.json').write_text(json.dumps([r['checker_2_6_1'] for r in reports],indent=2))
bpy.ops.wm.open_mainfile(filepath=str(R/'GROUND_NPM_v008.blend'));o=bpy.data.objects['SM_GROUND_NPM_Ground'];assert len(o.data.polygons)==len(D['faces']);assert all(len(p.vertices)==4 for p in o.data.polygons)
print('BLEND_READBACK_OK')




