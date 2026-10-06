import bpy,json,hashlib,math
from pathlib import Path
from collections import Counter
from mathutils import Vector
from mathutils.geometry import closest_point_on_tri
root=Path('C:/Users/artsafro/.AGR_Project/jobs/UV-CONTINUOUS/outputs')
bpy.ops.wm.open_mainfile(filepath=str(root/'walls_UV550-1500_FlipH_v006.blend'))
o=next(o for o in bpy.context.scene.objects if o.type=='MESH');m=o.data;m.calc_loop_triangles();layer=m.uv_layers.active.data
td=[];bounds=[];area=0;pa=[0.]*len(m.polygons);pu=[0.]*len(m.polygons)
for tri in m.loop_triangles:
    q=[o.matrix_world@m.vertices[i].co for i in tri.vertices];a=(q[1]-q[0]).cross(q[2]-q[0]).length/2
    u=[layer[i].uv for i in tri.loops];b=abs((u[1]-u[0]).cross(u[2]-u[0]))/2
    if a>1e-14:td.append(4096*math.sqrt(b/a))
    pa[tri.polygon_index]+=a;pu[tri.polygon_index]+=b
    area+=a
for x in layer:bounds.extend(x.uv)
edges=Counter(tuple(sorted((a,b))) for p in m.polygons for a,b in zip(p.vertices,list(p.vertices[1:])+[p.vertices[0]]))
img=next(n.image for n in m.materials[0].node_tree.nodes if n.type=='TEX_IMAGE' and n.image and 'Diffuse' in n.image.name)
expected=hashlib.sha256((root/'T_Template_Address_001_Diffuse_FlipH_v005.1001.png').read_bytes()).hexdigest()
source=json.loads((root/'source.json').read_text());points=[o.matrix_world@v.co for v in m.vertices];maxerr=0;source_tris={}
for tri in source['triangles']:source_tris.setdefault(tri['face'],[]).append([Vector(source['vertices'][i]) for i in tri['vertices']])
for p in m.polygons:
    sf=source['faces'][m.attributes['source_face'].data[p.index].value];q=[Vector(source['vertices'][i]) for i in sf]
    triangles=source_tris[m.attributes['source_face'].data[p.index].value]
    maxerr=max(maxerr,max(min((points[i]-closest_point_on_tri(points[i],*tri)).length for tri in triangles) for i in p.vertices))
rep={'file':bpy.data.filepath,'faces':len(m.polygons),'polygon_sizes':dict(Counter(len(p.vertices) for p in m.polygons)),'density_min_max':[min(td),max(td)],'td_outside_550_1500':sum(x<550 or x>1500 for x in td),'uv_bounds':[min(bounds),max(bounds)],'outside_1001':sum(x<0 or x>1 for x in bounds),'surface_area_m2':area,'edge_counts':dict(Counter(edges.values())),'nonmanifold_gt2':sum(x>2 for x in edges.values()),'mesh_validate_repairs':m.validate(verbose=False),'packed_diffuse_matches':hashlib.sha256(img.packed_file.data).hexdigest()==expected,'source_plane_error_m':maxerr,'delivery_passed':False}
polytd=[4096*math.sqrt(u/a) for u,a in zip(pu,pa) if a>1e-14]
rep.pop('source_plane_error_m');rep['source_surface_distance_m']=maxerr;rep['face_density_min_max']=[min(polytd),max(polytd)]
rep['loose_vertices']=len(m.vertices)-len({i for p in m.polygons for i in p.vertices})
phase_edges={};phase_residual=[];phase_failures=[]
for p in m.polygons:
    parent=m.attributes['source_face'].data[p.index].value
    if abs(source['normals'][parent][2])>.001:continue
    loops=list(p.loop_indices)
    for la,lb in zip(loops,loops[1:]+loops[:1]):
        va,vb=m.loops[la].vertex_index,m.loops[lb].vertex_index
        key=tuple(sorted((va,vb)));vals={va:layer[la].uv.copy(),vb:layer[lb].uv.copy()}
        if key in phase_edges:
            prev,prevparent=phase_edges[key]
            for vi in key:
                diff=(vals[vi]-prev[vi])*(4096/4056)
                phase_residual.append(max(abs(x-round(x)) for x in diff)*4056)
                if phase_residual[-1]>.1:phase_failures.append({'parents':[prevparent,parent],'edge':key,'point':list(points[vi]),'residual_px':phase_residual[-1]})
        else:phase_edges[key]=(vals,parent)
rep['vertical_shared_edge_sample_max_phase_px']=max(phase_residual)
rep['vertical_shared_edge_samples']=len(phase_residual)
rep['vertical_phase_samples_over_0_1px']=sum(x>.1 for x in phase_residual)
(root/'phase-failures-v006.json').write_text(json.dumps(phase_failures,indent=2))
(root/'readback_v006.json').write_text(json.dumps(rep,indent=2));print(json.dumps(rep))
