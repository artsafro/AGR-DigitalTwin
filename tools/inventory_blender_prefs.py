"""Read saved enabled-addon names without importing Blender or any add-on.

Supports the classic little-endian 64-bit .blend header (verified on 4.4).
Newer headers are explicitly unsupported. Never writes the source preferences.
"""
import argparse
import struct,json
from pathlib import Path

def addons(p):
    b=p.read_bytes()
    if not b.startswith(b'BLENDER-v'): return {'path':str(p),'status':'unsupported_header','header':b[:16].decode('ascii','replace')}
    off=12;blocks=[]
    while off+24<=len(b):
        code,size,ptr,sdna,count=struct.unpack_from('<4sIQII',b,off)
        data=b[off+24:off+24+size];blocks.append((code,sdna,count,data));off+=24+size
        if code==b'ENDB':break
    dna=next(x[3] for x in blocks if x[0]==b'DNA1'); o=8
    def u32():
        nonlocal o
        n=struct.unpack_from('<I',dna,o)[0];o+=4;return n
    def strings():
        nonlocal o
        n=u32();r=[]
        for _ in range(n):
            end=dna.index(0,o);r.append(dna[o:end].decode());o=end+1
        o=(o+3)//4*4;return r
    names=strings();assert dna[o:o+4]==b'TYPE';o+=4;types=strings()
    assert dna[o:o+4]==b'TLEN';o+=4
    lens=struct.unpack_from('<'+'H'*len(types),dna,o);o+=2*len(types);o=(o+3)//4*4
    assert dna[o:o+4]==b'STRC';o+=4;n=u32();structs=[]
    for _ in range(n):
        t,num=struct.unpack_from('<HH',dna,o);o+=4
        fields=[]
        for _ in range(num):
            ft,fn=struct.unpack_from('<HH',dna,o);o+=4;fields.append((types[ft],names[fn]))
        structs.append((types[t],fields))
    result=[];shape=None
    for code,idx,num,data in blocks:
        if idx<len(structs) and structs[idx][0]=='bAddon':
            shape=structs[idx]
            assert shape[1][:3]==[('bAddon','*next'),('bAddon','*prev'),('char','module[128]')],shape
            result.append(data[16:144].split(b'\0')[0].decode())
    return {'path':str(p),'status':'parsed_DNA_bAddon','enabled_modules':result,'struct':shape,'note':'Saved preferences only; no addon executed, no current runtime claim.'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths',nargs='+',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    result=[addons(p) for p in args.paths]
    text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if args.output:
        if args.output.resolve() in {p.resolve() for p in args.paths}:
            parser.error('output must not overwrite input preferences')
        args.output.write_text(text,encoding='utf-8',newline='\n')
    else:
        print(text)

if __name__=='__main__':
    main()
