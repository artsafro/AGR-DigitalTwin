import pytest
np=pytest.importorskip('numpy')
pytest.importorskip('shapely')
from dt_ai.geometry.exterior import extract_exterior


def fixture():
    owner=np.ones((3,3,1),dtype=np.int32);owner[1,1,:]=0
    return dict(owner=owner,x=np.array([0,.2,1.8,2]),y=np.array([0,.2,1.8,2]),z=np.array([0,2.9]),angle=0.)


def params():
    return dict(height_m=3.,coordinate_budget_m=.001,microgap_closure_m=.001,
                opening_match_m=.005,window_plane_distance_m=.5,
                wall_top_policy='extend_to_height_record_unmatched_top_gaps',
                units='m',height_basis='synthetic fixture, not real project')


def test_explicit_height_changes_surface_without_mutating_input():
    data=fixture();saved=data['owner'].copy()
    a,report=extract_exterior(data,[],**params())
    args=params();args['height_m']=3.4
    b,_=extract_exterior(data,[],**args)
    assert a['vertices'][:,2].max()==3.
    assert b['vertices'][:,2].max()==3.4
    assert report['facade_runs']==4
    assert np.array_equal(saved,data['owner'])
    assert all(r['source_ids']==[1] for r in report['profiles'])


@pytest.mark.parametrize('change',[{'height_m':float('nan')},{'units':'mm'},
    {'coordinate_budget_m':0},{'microgap_closure_m':-1},{'opening_match_m':0},
    {'wall_top_policy':'guess'},{'height_basis':''}])
def test_invalid_parameters_rejected(change):
    args=params();args.update(change)
    with pytest.raises(ValueError):extract_exterior(fixture(),[],**args)


def test_multiple_components_and_unsorted_grid_are_rejected():
    data=fixture();data['x']=data['x'][::-1]
    with pytest.raises(ValueError,match='increasing'):extract_exterior(data,[],**params())
    data=fixture();data['owner'][:]=0;data['owner'][0,0]=1;data['owner'][2,2]=2
    with pytest.raises(ValueError,match='Multiple'):extract_exterior(data,[],**params())


def test_explicit_window_id_is_preserved_and_opening_stays_empty():
    x=np.array([0,.2,1,2,3.8,4.])
    y=np.array([0,.2,1.8,2.])
    z=np.array([0,.8,2.55,2.9])
    owner=np.zeros((len(x)-1,len(y)-1,len(z)-1),dtype=np.int32)
    owner[0,:,:]=11;owner[-1,:,:]=12;owner[:,0,:]=13;owner[:,-1,:]=14
    owner[2,0,1:2]=0
    data=dict(owner=owner,x=x,y=y,z=z,angle=0.)
    window={'id':'synthetic-window-1','min':[1,0,.8],'max':[2,.2,2.55]}
    arrays,report=extract_exterior(data,[window],**params())
    openings=[o for run in report['profiles'] for o in run['openings']]
    assert [o['source_window_ids'] for o in openings]==[['synthetic-window-1']]
    assert sum(r['closed_openings'] for r in report['profiles'])==1
    q=arrays['vertices'][arrays['faces']]
    front=q[np.all(np.isclose(q[:,:,1],0),axis=1)]
    for face in front:
        low=face[:,[0,2]].min(0);high=face[:,[0,2]].max(0)
        overlap=np.maximum(0,np.minimum(high,[2,2.55])-np.maximum(low,[1,.8]))
        assert np.prod(overlap)==0


def test_grid_and_window_identity_contracts_are_rejected():
    data=fixture();data['owner']=data['owner'].astype(float)
    with pytest.raises(ValueError,match='ownership'):extract_exterior(data,[],**params())
    duplicate={'id':'same','min':[0,0,0],'max':[1,.2,1]}
    with pytest.raises(ValueError,match='Duplicate'):
        extract_exterior(fixture(),[duplicate,duplicate.copy()],**params())
