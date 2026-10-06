"""Native editable periodic F1 texture source; mirrored, with wrap padding."""
import numpy as np,json,hashlib
from pathlib import Path
from PIL import Image
root=Path(__file__).resolve().parents[1]/'outputs';N=4096;PAD=20;PERIOD=N-2*PAD
source=root/'T_Template_Address_001_Diffuse_1.1001.png'
with Image.open(source) as im:base=float(np.median(np.asarray(im)[768:900,430:560]))
image=np.empty((N,N,3),np.uint8);x=np.arange(N,dtype=np.float32)[None,:]
for top in range(0,N,128):
    y=np.arange(top,top+128,dtype=np.float32)[:,None];u=1-(x+.5-PAD)/PERIOD;v=(y+.5-PAD)/PERIOD
    plain=base+.55*np.sin(2*np.pi*16*u)*np.sin(2*np.pi*16*v)
    cx=abs(3*u-np.rint(3*u))*PERIOD/3;cy=abs(8*v-np.rint(8*v))*PERIOD/8
    grey=np.where((cx<2.5)|(cy<2.5),85.,plain)
    h=abs(8*v-.5-np.rint(8*v-.5))*PERIOD/8
    ha=.68*np.exp(-.5*(h/7.5)**2)+.15*np.exp(-.5*(h/18)**2)
    phase=2*u+v-.22;dist=abs(phase-np.rint(phase))*PERIOD/np.sqrt(5)
    da=.55*np.exp(-.5*(dist/7)**2)+.06*np.exp(-.5*(dist/19)**2)
    a=np.maximum(ha,da);lit=plain*(1-a)+220*a;value=np.where(a>=.17,lit,grey*(1-a)+220*a)
    image[top:top+128]=np.clip(np.rint(value),0,255).astype(np.uint8)[:,:,None]
# Guard rows are the exact wrapped opposite rows, including bilinear sampling.
for k in range(2*PAD):
    image[k]=image[k+PERIOD];image[:,k]=image[:,k+PERIOD]
target=root/'T_Template_Address_001_Diffuse_FlipH_v005.1001.png';Image.fromarray(image).save(target)
with Image.open(target) as check:
    a=np.asarray(check);assert check.size==(4096,4096)
    assert np.array_equal(a[PAD-1:PAD+1],a[N-PAD-1:N-PAD+1])
    assert np.array_equal(a[:,PAD-1:PAD+1],a[:,N-PAD-1:N-PAD+1])
report={'resolution':[N,N],'padding':PAD,'period_pixels':PERIOD,'base':base,'cassette_columns':3,'cassette_rows':8,'white_horizontal_lines':8,'diagonal_lines':2,'horizontal_mirror':True,'bilinear_boundary_samples_equal':True,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'method':'Native editable F1 procedural texture source; imagegen study discarded because counts/edge continuity were not preserved'}
(root/'texture-v005-qa.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
