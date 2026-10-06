"""Read-only local DCC discovery; writes metadata only under --output.

Does not import discovered Python, load scenes, traverse junctions or read cloud
placeholders. SHA256 identifies exact text-script duplicates, not usage history.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone

EXT = set('.ms .mcr .mse .mzp .py .pyd .lsp .fas .vlx .scr .cuix .cui .mnux .mnu .dyn .dyf .addin .dll .dlu .dlm .dlo .dlt .dle .gup .arx .dbx .ini .fbxexportpreset .fbximportpreset .xml .toml .ps1 .bat .cmd .cs .csproj .ahk .rte .dwt .arg .rps .mcg .maxstart .blend .max .json .md .txt .zip'.split())
TEXT = set('.ms .mcr .py .lsp .scr .dyn .dyf .addin .fbxexportpreset .fbximportpreset .ps1 .cs .ahk'.split())
SKIP = {'.git','node_modules','.venv','venv','__pycache__','.sync','.dropbox.cache','site-packages','cache','caches','logs','journals','textures','maps','renderoutput','autoback','$recycle.bin','system volume information','sessions','chats','memories','browser','browser-logs','.sandbox-secrets','.ssh','mcp-oauth-locks','sqlite','generated_images','dictation-history','ai-tracking','agent-transcripts','python','python3.11','python3.12','python3.10','lib','libs','meshes','sceneassets'}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--roots', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    roots=json.loads(Path(args.roots).read_text(encoding='utf-8'))
    files=[]; errors=[]; coverage=[]; seen=set()
    for root in roots:
        base=Path(root); count=0
        if not base.exists():
            coverage.append({'root':root,'status':'missing','files':0}); continue
        def err(e): errors.append({'path':e.filename,'error':str(e)})
        for directory, dirs, names in os.walk(base, followlinks=False, onerror=err):
            dirs[:]=[d for d in dirs if d.lower() not in SKIP and not os.path.islink(os.path.join(directory,d)) and not os.path.isjunction(os.path.join(directory,d))]
            for name in names:
                p=Path(directory)/name
                if p.suffix.lower() not in EXT or str(p).lower() in seen: continue
                seen.add(str(p).lower())
                try:
                    st=p.stat()
                    # REPARSE_POINT/OFFLINE/RECALL_ON_DATA_ACCESS: do not hydrate.
                    if getattr(st,'st_file_attributes',0) & (0x1000|0x40000): continue
                    rec={'path':str(p),'bytes':st.st_size,'mtime':datetime.fromtimestamp(st.st_mtime,timezone.utc).isoformat(),'ext':p.suffix.lower(),'root':root}
                    if p.suffix.lower() in TEXT and st.st_size < 2_000_000:
                        rec['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
                    files.append(rec); count+=1
                except OSError as e: err(e)
        coverage.append({'root':root,'status':'enumerated','files':count})
    groups={}
    for f in files:
        if 'sha256' in f: groups.setdefault(f['sha256'],[]).append(f['path'])
    result={'generated_at':datetime.now(timezone.utc).isoformat(),'coverage':coverage,'errors':errors,'files':files,'exact_duplicate_groups':[{'sha256':h,'paths':p} for h,p in groups.items() if len(p)>1], 'limitations':'Metadata/text only. No execution, no inferred usage. Pruned env/cache/map folders; cloud offline data excluded; scene files metadata only.'}
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'files':len(files),'roots':len(coverage),'errors':len(errors),'duplicate_groups':len(result['exact_duplicate_groups'])}))

if __name__=='__main__': main()
