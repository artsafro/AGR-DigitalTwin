"""Recover exact contributing v004 source-owner IDs by planar area intersection."""
import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import Polygon


def run(p):
    old=np.load(p/'body-structured-mesh.npz')
    new=np.load(p/'body-optimized-mesh.npz')
    grid=np.load(p/'body-grid.npz')
    axes=[grid[k] for k in 'xyz']; angle=float(grid['angle'])
    rotation=np.array([[np.cos(angle),np.sin(angle)],[-np.sin(angle),np.cos(angle)]])
    def projected(data):
        v=data['vertices'].copy();v[:,:2]=v[:,:2]@rotation.T
        for f in data['faces']:
            q=v[f];a=int(np.argmin(np.ptp(q,axis=0)))
            plane=int(np.argmin(abs(axes[a]-q[0,a])))
            yield (a,plane),Polygon(q[:,[(a+1)%3,(a+2)%3]])
    planes=defaultdict(list)
    for fi,(key,polygon) in enumerate(projected(old)):
        planes[key].append((fi,polygon))
    trees={key:shapely.STRtree([poly for fi,poly in records]) for key,records in planes.items()}
    groups,lookup,indices=[],{},[]
    maximum_area_error=0.
    for key,polygon in projected(new):
        source=set();covered=0.
        for i in trees[key].query(polygon,predicate='intersects'):
            fi,other=planes[key][i]
            area=polygon.intersection(other).area
            if area>1e-12:
                source.add(int(old['source_indices'][fi]));covered+=area
        error=abs(covered-polygon.area);maximum_area_error=max(error,maximum_area_error)
        if not source or error>1e-8:
            raise ValueError(f'Source coverage mismatch: {key}, {error}')
        group=tuple(sorted(source))
        if group not in lookup:
            lookup[group]=len(groups)+1;groups.append(list(group))
        indices.append(lookup[group])
    np.savez_compressed(p/'body-optimized-mesh.npz',vertices=new['vertices'],faces=new['faces'],source_indices=np.array(indices,dtype=np.int32))
    report=json.loads((p/'body-optimization.json').read_text(encoding='utf-8'))
    report.update(source_groups=groups,provenance_note='Exact positive-area intersections with v004 source-owner faces; representative union ownership inherited from v004',
                  source_coverage_max_area_error_m2=maximum_area_error)
    (p/'body-optimization.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Source groups',len(groups),'max area error',maximum_area_error)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output_directory',type=Path)
    run(parser.parse_args().output_directory)
