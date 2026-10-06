"""Measured exterior shell rims and simplified window planes; originals untouched."""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import Polygon, Point


def components(item):
    parent=list(range(len(item['vertices'])))
    def root(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    for f in item['faces']:
        for i in f[1:]:parent[root(i)]=root(f[0])
    groups=defaultdict(list)
    for i in range(len(parent)):groups[root(i)].append(i)
    return list(groups.values())


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dt_ai.geometry.shell import Mesh, shell_body


def build(p,clean=False):
    exterior=np.load(p/'exterior-surface.npz');report=json.loads((p/'exterior-surface.json').read_text(encoding='utf-8'))
    angle=float(np.load(p/'body-grid.npz')['angle']);R=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
    v=exterior['vertices'].copy();v[:,:2]=v[:,:2]@R
    f=exterior['faces'];labels=exterior['facade_indices']
    result = shell_body(v, f, [report['profiles'][label-1]['outward']+[0.] for label in labels],
                        thickness_m=.4, name='BODY_Shell_400mm_NoInnerFaces', units='m',
                        source_refs=[f"facade:{label}" for label in labels])
    body_data = result['mesh']
    source=json.loads((p/'contour-source.json').read_text(encoding='utf-8'))
    items={i['props'].get('revit_element_id'):i for i in source['items']}
    meshes=[body_data];records=[];pending=[]
    for ri,run in enumerate(report['profiles'],1):
        a,u=run['axis'],run['along_axis'];sign=run['outward'][a];plane=run['start'][a]
        for oi,opening in enumerate(run['openings']):
            if opening['kind']!='closed':
                pending.append({'run':ri,'opening':oi,'reason':'clipped stair window: full adjacent-floor source needed','ids':opening['source_window_ids']});continue
            assert len(opening['source_window_ids'])==1
            identity=opening['source_window_ids'][0];item=items[identity]
            vv=np.array(item['vertices']);vv[:,:2]=vv[:,:2]@R
            groups=components(item);panes=[];pane_vertices=set()
            for group in groups:
                q=vv[group];lo,hi=q.min(0),q.max(0)
                # Revit rectangular panel components: 8 corners, measured 30mm depth.
                if len(group)==8 and hi[u]-lo[u]>.1 and hi[2]-lo[2]>.1 and .02<hi[a]-lo[a]<.04:
                    panes.append((lo,hi));pane_vertices.update(group)
            assert panes, identity
            planes=defaultdict(float)
            for face in item['faces']:
                if set(face)<=pane_vertices:continue
                q=vv[face]
                if np.ptp(q[:,a])>1e-5:continue
                depth=(plane-q[:,a].mean())*sign
                if not 0<depth<.4:continue
                poly=Polygon(q[:,[u,2]])
                if poly.is_valid:planes[round(float(q[:,a].mean()),4)]+=poly.area
            assert planes
            panel_front=max((hi[a] if sign>0 else lo[a])*sign for lo,hi in panes)
            candidates={coord:area for coord,area in planes.items() if coord*sign>=panel_front-1e-4}
            assert candidates, identity
            front=max(candidates,key=candidates.get)
            outline=shapely.from_geojson(opening['geometry_geojson']);x0,z0,x1,z1=outline.bounds
            # 10mm lateral embed is explicit user-authorized joint, not welding tolerance.
            outer=shapely.box(x0-.01,z0-.01,x1+.01,z1+.01)
            holes=[shapely.box(lo[u],lo[2],hi[u],hi[2]) for lo,hi in panes]
            assert all(outline.covers(h) for h in holes)
            frame=outer.difference(shapely.union_all(holes))
            uc=sorted({x0-.01,x1+.01,*[float(t) for lo,hi in panes for t in [lo[u],hi[u]]]})
            zc=sorted({z0-.01,z1+.01,*[float(t) for lo,hi in panes for t in [lo[2],hi[2]]]})
            mesh=Mesh('WINDOW_'+identity)
            def point(x,z,d):
                q=[0.,0.,z];q[u]=float(x);q[a]=float(d);return q
            normal=np.array(run['outward']+[0.])
            if clean:
                # Four convex quads around each measured panel, with shared cells
                # between panels. No propagation of every pane coordinate across frame.
                rows=defaultdict(list)
                for lo,hi in panes:rows[round(float(lo[2]),3)].append((lo,hi))
                rows=[sorted(row,key=lambda pair:pair[0][u]) for _,row in sorted(rows.items())]
                assert len({len(row) for row in rows})==1
                nx=len(rows[0]);ny=len(rows)
                xs=[x0-.01]+[(max(row[col][1][u] for row in rows)+min(row[col+1][0][u] for row in rows))/2 for col in range(nx-1)]+[x1+.01]
                zs=[z0-.01]+[(max(hi[2] for lo,hi in rows[row])+min(lo[2] for lo,hi in rows[row+1]))/2 for row in range(ny-1)]+[z1+.01]
                for row in range(ny):
                    for col in range(nx):
                        lo,hi=rows[row][col]
                        outer_ring=[(xs[col],zs[row]),(xs[col+1],zs[row]),(xs[col+1],zs[row+1]),(xs[col],zs[row+1])]
                        inner_ring=[(lo[u],lo[2]),(hi[u],lo[2]),(hi[u],hi[2]),(lo[u],hi[2])]
                        assert xs[col]<lo[u]<hi[u]<xs[col+1] and zs[row]<lo[2]<hi[2]<zs[row+1]
                        for k in range(4):
                            j=(k+1)%4
                            mesh.face([point(*outer_ring[k],front),point(*outer_ring[j],front),point(*inner_ring[j],front),point(*inner_ring[k],front)],normal,1)
            for l,r in zip(uc,uc[1:]):
                for b,t in zip(zc,zc[1:]):
                    if not clean and frame.covers(Point((l+r)/2,(b+t)/2)):
                        mesh.face([point(l,b,front),point(r,b,front),point(r,t,front),point(l,t,front)],normal,1)
            pane_records=[]
            for lo,hi in panes:
                depth=hi[a] if sign>0 else lo[a]
                if (front-depth)*sign < -1e-4:
                    raise ValueError('Selected frame lies behind panel '+identity)
                # Split panel/rim on shared frame cuts to avoid T junctions.
                xs=[lo[u],hi[u]] if clean else [x for x in uc if lo[u]-1e-8<=x<=hi[u]+1e-8]
                zs=[lo[2],hi[2]] if clean else [z for z in zc if lo[2]-1e-8<=z<=hi[2]+1e-8]
                for l,r in zip(xs,xs[1:]):
                    for b,t in zip(zs,zs[1:]):
                        mesh.face([point(l,b,depth),point(r,b,depth),point(r,t,depth),point(l,t,depth)],normal,2)
                if abs(front-depth)>1e-6:
                    for x,n in [(lo[u],1),(hi[u],-1)]:
                        nrm=np.zeros(3);nrm[u]=n
                        for b,t in zip(zs,zs[1:]):mesh.face([point(x,b,front),point(x,b,depth),point(x,t,depth),point(x,t,front)],nrm,1)
                    for z,n in [(lo[2],1),(hi[2],-1)]:
                        nrm=np.array([0.,0.,n])
                        for l,r in zip(xs,xs[1:]):mesh.face([point(l,z,front),point(r,z,front),point(r,z,depth),point(l,z,depth)],nrm,1)
                pane_records.append({'bounds':[float(lo[u]),float(lo[2]),float(hi[u]),float(hi[2])],'plane':float(depth)})
            entry={'id':identity,'type':item['props']['source_fbx_full_name'].split(' [')[0],
                   'run':ri,'opening':oi,'axis':a,'along_axis':u,'outward_sign':sign,
                   'facade_plane':plane,'frame_plane':front,'recess_m':(plane-front)*sign,
                   'opening_bounds':[x0,z0,x1,z1],
                   'lateral_embed_m':.01,'panels':pane_records,
                   'scope':'Simplified frame from opening plane minus measured source panel rectangles; no handles or rear faces',
                   'material_status':'Neutral preview; panel role inferred from source box components, not verified Revit material'}
            records.append(entry);meshes.append(mesh.dump())
    for mesh in meshes:
        coords=np.array(mesh['vertices']);coords[:,:2]=coords[:,:2]@R.T;mesh['vertices']=coords.tolist()
    result={'meshes':meshes,'windows':records,'pending':pending,'angle':angle,
            'shell_m':.4,'inner_faces':False,'height_assumption_inherited_from_v006':True}
    result['window_topology']='four quads around each measured panel; no propagated pane grid' if clean else 'Cartesian pane grid'
    (p/('shell-windows-optimized.json' if clean else 'shell-windows.json')).write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
    print('meshes',len(meshes),'windows',len(records),'pending',len(pending),'quads',sum(len(m['faces']) for m in meshes))


if __name__=='__main__':build(Path(sys.argv[1]),'--clean' in sys.argv)
