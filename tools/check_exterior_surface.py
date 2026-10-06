"""Verify saved exterior faces against the registered perimeter and openings."""
import argparse
import json
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import Polygon


def check(p, angle=None):
    report=json.loads((p/'exterior-surface.json').read_text(encoding='utf-8'))
    data=np.load(p/'exterior-readback.npz')
    if angle is None:
        angle=report.get('angle_rad')
    if angle is None:
        angle=float(np.load(p/'body-grid.npz')['angle'])
    v=data['vertices'].copy()
    v[:,:2]=v[:,:2]@np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
    faces=data['faces'];labels=data['facade_indices']
    contour=shapely.from_geojson(report['contour_geojson'])
    assert contour.is_valid and not contour.interiors
    tol=5e-6
    max_error=0.;overlap=0.;opening_leak=0.;invalid=0;wrong_normals=0;extra_cuts=0
    for ri,run in enumerate(report['profiles'],1):
        q=v[faces[labels==ri]];a=run['axis'];u=run['along_axis']
        assert len(q)>0
        assert np.max(abs(q[:,:,a]-run['start'][a]))<tol
        normal=np.cross(q[:,1]-q[:,0],q[:,2]-q[:,0])
        wrong_normals+=int((normal[:,:2]@np.array(run['outward'])<=0).sum())
        # Quantize only readback float error to exact registered coordinates.
        projected=q[:,:,[u,2]].copy()
        for axis,cuts in enumerate([run['u_cuts_m'],report['z_cuts_m']]):
            cuts=np.array(cuts)
            nearest=cuts[np.argmin(abs(projected[:,:,axis,None]-cuts),axis=2)]
            extra_cuts+=int((abs(nearest-projected[:,:,axis])>tol).sum())
            projected[:,:,axis]=nearest
        polys=[Polygon(x) for x in projected]
        invalid+=sum(not poly.is_valid or poly.area<=0 or abs(poly.convex_hull.area-poly.area)>1e-9 for poly in polys)
        union=shapely.union_all(polys)
        expected=shapely.from_geojson(run['profile_geojson'])
        max_error=max(max_error,union.symmetric_difference(expected).area)
        overlap+=max(0.,sum(x.area for x in polys)-union.area)
        for opening in run['openings']:
            opening_leak+=union.intersection(shapely.from_geojson(opening['geometry_geojson'])).area
        # Every run belongs to the outer ring: internal wall planes are excluded.
        line=shapely.LineString([run['start'],run['end']])
        assert line.difference(contour.boundary.buffer(1e-8)).length<1e-8
    result={'facade_runs_checked':len(report['profiles']),'invalid_or_nonconvex_quads':invalid,
            'inward_faces':wrong_normals,'unregistered_cut_coordinates':extra_cuts,
            'max_profile_difference_m2':max_error,'coplanar_overlap_m2':overlap,
            'opening_fill_area_m2':opening_leak,'readback_coordinate_tolerance_m':tol,
            'scope':'Saved pre-Shell exterior surface against registered measured profiles; height assumption remains'}
    ok=invalid==wrong_normals==extra_cuts==0 and max_error<1e-8 and overlap<1e-8 and opening_leak<1e-8
    qa=json.loads((p/'exterior-qa.json').read_text(encoding='utf-8'))
    ok=ok and all(qa[k]==0 for k in ['exact_duplicate_vertices','exact_duplicate_faces','edges_with_more_than_two_faces','boundary_junction_vertices','faces_with_edge_below_10mm'])
    ok=ok and qa['readback_max_error_m']<tol
    result['geometry_checks_passed']=bool(ok)
    qa['geometry_checks_passed']=bool(ok)
    qa['remaining']=['Resolve recorded height/top-gap assumptions against source design intent','Enable and validate Shell 0.4m, then model and fit windows']
    (p/'exterior-surface-check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (p/'exterior-qa.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
    if (p/'report.json').exists():
        import sys
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
        from dt_ai.core.adapter_report import AdapterReport
        record=json.loads((p/'report.json').read_text(encoding='utf-8'))
        if record.get('operation')=='extract-exterior':
            for item in record['checks']:
                if item['id']=='dcc_profile_readback':
                    item.update(status='pass' if ok else 'fail',evidence=str(p/'exterior-surface-check.json'))
            record=AdapterReport.model_validate(record).model_dump(mode='json')
            (p/'report.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result))
    assert ok, result
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path)
    check(parser.parse_args().directory)
