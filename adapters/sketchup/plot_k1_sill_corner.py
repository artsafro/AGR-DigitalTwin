"""Diagnostic plan view of source top-sill polygons at the open corner."""
import json
from pathlib import Path
from PIL import Image,ImageDraw
root=Path('jobs/GLB-NPM/outputs/tower-k1-v011')
rows=json.loads((root/'top-sill-horizontal-v022.json').read_text())
rows=[r for r in rows if abs(r['z']-66.501052)<.0002]
scale=100;ox,oy=5.5,17.0
im=Image.new('RGB',(900,750),'white');draw=ImageDraw.Draw(im)
def xy(p):return (int((p[0]-ox)*scale),int(750-(p[1]-oy)*scale))
for r in rows:
 pts=[xy(p) for p in r['xy']]
 if any(x<0 or x>900 or y<0 or y>750 for x,y in pts):continue
 draw.polygon(pts,fill='#9bd3ff' if r['normal_z']>0 else '#ffcb9b',outline='#46515c')
for p in ((6.562690258,18.969316483),(9.99216938,22.327690125)):
 x,y=xy(p);draw.ellipse((x-8,y-8,x+8,y+8),fill='red')
im.save(root/'top-sill-corner-plan-v022.png')
print(root/'top-sill-corner-plan-v022.png')
