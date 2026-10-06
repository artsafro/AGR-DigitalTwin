import hashlib,json,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'outputs'
folder=root/'FBX_For_Max_v006';target=root/'Walls_FlipH_v006_FBX_For_Max.zip'
names=['Walls_FlipH_v006.fbx','Walls_FlipH_v006_Diffuse.png','README.txt','FBX_READBACK.json']
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
    for name in names:archive.write(folder/name,arcname=name)
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None
    assert sorted(archive.namelist())==sorted(names)
    for name in names:assert archive.read(name)==(folder/name).read_bytes()
rep={'zip':str(target),'archive_readback_verified':True,'files':{n:{'bytes':(folder/n).stat().st_size,'sha256':hashlib.sha256((folder/n).read_bytes()).hexdigest()} for n in names}}
(folder/'PACKAGE_QA.json').write_text(json.dumps(rep,indent=2))
print(json.dumps({'zip':str(target),'bytes':target.stat().st_size,'files':names,'readback':True}))
