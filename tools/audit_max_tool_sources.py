"""Read-only source inventory for the proposed NPM/VPM workbench."""
from pathlib import Path
import hashlib, json, re, zipfile
from collections import Counter, defaultdict

ROOTS = [Path(r'C:\Users\artsafro\Desktop\zavod'), Path(r'C:\Users\artsafro\Desktop\!3D viz\Плагины 3dMax')]
OUT = Path('docs/research/max-workbench')
OUT.mkdir(parents=True, exist_ok=True)
rows, archives = [], []
for root in ROOTS:
    for p in sorted(root.rglob('*')):
        if not p.is_file() or any(x in p.parts for x in ('.git','node_modules','.venv','__pycache__')):
            continue
        ext = p.suffix.lower()
        if ext in ('.zip', '.mzp'):
            try:
                with zipfile.ZipFile(p) as z:
                    members = [i.filename for i in z.infolist() if Path(i.filename).suffix.lower() in ('.ms','.mcr','.mse','.dll','.dlm')]
                    matches = []
                    if p.name == 'Для Артема.zip':
                        for name in members:
                            target = root / 'Andrew_scripts' / Path(name).name
                            matches.append({'member':name,'matches_Andrew':target.exists() and hashlib.sha256(z.read(name)).digest()==hashlib.sha256(target.read_bytes()).digest()})
                archives.append({'path':str(p),'scripts':members,'source_comparison':matches})
            except Exception as e:
                archives.append({'path':str(p),'error':type(e).__name__})
        if ext not in ('.ms','.mcr','.mse','.mzp','.dll','.dlo','.dlm','.dlu','.exe','.rar','.7z'):
            continue
        row = {'root':root.name,'relative':str(p.relative_to(root)),'path':str(p),'bytes':p.stat().st_size,'extension':ext}
        if ext in ('.ms','.mcr','.mse'):
            raw=p.read_bytes(); row['sha256']=hashlib.sha256(raw).hexdigest()
            if ext != '.mse':
                for enc in ('utf-8-sig','utf-16','cp1251'):
                    try: s=raw.decode(enc); break
                    except UnicodeError: pass
                else: s=raw.decode('utf-8',errors='replace')
                row['lines']=len(s.splitlines())
                row['functions']=re.findall(r'(?im)^\s*(?:fn|function)\s+(\w+)',s)
                row['ui']=[{'line':i,'text':v.strip()[:250]} for i,v in enumerate(s.splitlines(),1) if re.search(r'^\s*(rollout|button|group|macroScript)\b',v,re.I)]
                row['integration_signals']=[{'line':i,'text':v.strip()[:250]} for i,v in enumerate(s.splitlines(),1) if re.search(r'fileIn|resetMaxFile|exportFile|saveMaxFile|loadMaxFile|deleteFile|shellLaunch|python\.execute|callbacks\.addScript|registerRedrawViewsCallback|System\.IO\.File.*Copy',v,re.I)]
        rows.append(row)
groups=defaultdict(list)
for r in rows:
    if 'sha256' in r: groups[r['sha256']].append(r['path'])
data={'scope':'Filesystem inventory and static source index; no Max execution; archive members listed without installation. Regex signals are not a parser or proof of behavior.','counts':dict(Counter(r['extension'] for r in rows)),'files':rows,'duplicates':[v for v in groups.values() if len(v)>1],'archives':archives}
(OUT/'inventory.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'counts':data['counts'],'duplicate_groups':len(data['duplicates']),'archives':len(archives)},ensure_ascii=False))
for r in rows:
    if 'Andrew_scripts' in r['relative'] and r['extension'] in ('.ms','.mcr'):
        print(r['relative'],r.get('lines'), ' | '.join(x['text'] for x in r.get('ui',[]) if not x['text'].lower().startswith('macroscript'))[:2300])
