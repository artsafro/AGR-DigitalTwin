import importlib.util
from pathlib import Path

import pytest
np=pytest.importorskip('numpy')


def tool(name):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).parents[1]/'tools'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def subdivided_cube():
    vertices,faces,lookup=[],[],{}
    for axis in range(3):
        u,v=(axis+1)%3,(axis+2)%3
        for sign in (-1,1):
            for i in range(3):
                for j in range(3):
                    f=[]
                    for a,b in [(i,j),(i+1,j),(i+1,j+1),(i,j+1)]:
                        q=[0,0,0];q[axis]=0 if sign<0 else 3;q[u],q[v]=a,b
                        q=tuple(q)
                        if q not in lookup:lookup[q]=len(vertices);vertices.append(q)
                        f.append(lookup[q])
                    faces.append(f if sign>0 else f[::-1])
    return np.array(vertices,dtype=float),np.array(faces,dtype=np.int32)


def test_removes_redundant_loops_but_preserves_all_box_corners_and_sources():
    v,f=subdivided_cube()
    vv,ff,sources,history=tool('optimize_body_loops').optimize(v,f,[{i} for i in range(len(f))])
    assert len(ff)==6 and len(vv)==8
    assert set(map(tuple,vv))=={(x,y,z) for x in (0.,3.) for y in (0.,3.) for z in (0.,3.)}
    assert set().union(*sources)==set(range(54))
    assert all(len(s)==9 for s in sources)
    assert ff.shape[1]==4


def test_refuses_an_open_input_instead_of_erasing_border_edges():
    v,f=subdivided_cube()
    with pytest.raises(ValueError,match='closed manifold'):
        tool('optimize_body_loops').optimize(v,f[:-1],[{i} for i in range(len(f)-1)])


def test_planar_strip_reducer_leaves_geometric_box_corners_fixed():
    v,f=subdivided_cube()
    # Millimetre-scale test detail: eligible interior strips, protected creases.
    v*=.01
    vv,ff,sources,history=tool('reduce_body_planar_strips').reduce(v,f,[{1} for _ in f])
    assert set((x,y,z) for x in (0.,.03) for y in (0.,.03) for z in (0.,.03)).issubset(set(map(tuple,vv)))
    assert ff.shape[1]==4
    edges=np.sort(np.stack([ff,np.roll(ff,-1,axis=1)],axis=2).reshape(-1,2),axis=1)
    assert (np.unique(edges,axis=0,return_counts=True)[1]==2).all()
