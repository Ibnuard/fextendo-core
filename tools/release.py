"""Validate the NRO, build a copy-ready folder and GitHub Release assets."""
from pathlib import Path
import argparse, hashlib, json, re, shutil, struct, subprocess, tarfile

ROOT=Path(__file__).resolve().parents[1]
VERSION='1.1.0'
def sha(data):return hashlib.sha256(data).hexdigest()
def inspect_nro(path, full_romfs=True):
    data=path.read_bytes()
    if len(data)<128 or data[16:20]!=b'NRO0':raise ValueError('Not a valid NRO')
    start=struct.unpack_from('<I',data,24)[0]
    if data[start:start+4]!=b'ASET':raise ValueError('NRO has no asset container')
    assets={}
    for key,offset in [('icon',8),('nacp',24),('romfs',40)]:
        pos,size=struct.unpack_from('<QQ',data,start+offset)
        if pos<56 or start+pos+size>len(data):raise ValueError(f'Invalid {key} range')
        assets[key]=data[start+pos:start+pos+size]
    if assets['nacp'][:512].split(b'\0')[0]!=b'FEXTendo Patch':raise ValueError('Wrong NACP app title')
    if assets['nacp'][0x3060:0x3070].split(b'\0')[0]!=VERSION.encode():raise ValueError('Wrong NACP app version')
    if not assets['icon'].startswith(b'\xff\xd8'):raise ValueError('Missing JPEG icon')
    # Packaging checks every generated UI file. Later CI jobs validate the
    # pinned boot files/catalog without depending on another Pillow version.
    payloads = (ROOT/'romfs').rglob('*') if full_romfs else [ROOT/'romfs/catalog.json', *(ROOT/'romfs/boot').rglob('*')]
    for p in payloads:
        if p.is_file() and p.read_bytes() not in assets['romfs']:raise ValueError(f'Missing embedded payload: {p}')
    return {'nro_sha256':sha(data),'nro_bytes':len(data),'nro_build_id':data[64:96].hex(),
            'title':'FEXTendo Patch','version':VERSION,'embedded':{k:len(v) for k,v in assets.items()}}

def release(output, assets_output, copy_only=False):
    receipt=inspect_nro(ROOT/'FEXTendo-Patch.nro')
    catalog=json.loads((ROOT/'romfs/catalog.json').read_text())
    seen={}
    for bundle in catalog['bundles']:
        for key in ['kernel','loader']:
            a=bundle[key];data=(ROOT/'romfs/boot'/a['asset']).read_bytes()
            if len(data)!=a['bytes'] or sha(data)!=a['sha256']:raise ValueError('Bad catalog asset: '+a['asset'])
            if a['asset'] in seen and seen[a['asset']]!=a['sha256']:raise ValueError('Conflicting release asset names')
            seen[a['asset']]=a['sha256']
    for folder in [output,assets_output]:
        folder.mkdir(parents=True,exist_ok=True)
    # Exact owned outputs only; no recursive delete and no edits to an existing SD.
    target=output/'switch/fextendo-patch';target.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'FEXTendo-Patch.nro',target/'FEXTendo-Patch.nro')
    for name in ['README.md','THIRD_PARTY.md','LICENSE','update.ini.example','MULAI-DI-SINI.txt']:
        shutil.copy2(ROOT/name,output/name)
    shutil.copytree(ROOT/'provenance',output/'provenance',dirs_exist_ok=True)
    shutil.copytree(ROOT/'docs',output/'docs',dirs_exist_ok=True)
    receipt['sources']={str(p.relative_to(ROOT)).replace('\\','/'):sha(p.read_bytes())
                        for folder in ['source','include','tools','tests'] for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in str(p)}
    receipt['hardware_validation']='Pending Switch test. Kernel matches earlier PASS probes; fxtauto-v1 loaders are newly built and host-tested.'
    commit=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True)
    receipt['source_commit']=commit.stdout.strip() if commit.returncode==0 else None
    receipt['update_repository']=re.search(r'FXP_DEFAULT_REPOSITORY "([^"]*)"',(ROOT/'include/generated.hpp').read_text()).group(1)
    (output/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    if copy_only:
        for name in ['source','include','tools','tests','romfs','assets','third_party','provenance','docs','.github',
                     'Makefile','LICENSE','README.md','THIRD_PARTY.md','MULAI-DI-SINI.txt','update.ini.example','.gitignore','.gitattributes']:
            path=ROOT/name;dest=output/'source'/name
            if not path.exists():continue
            if path.is_dir():shutil.copytree(path,dest,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
            else:dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
        (output/'SHA256SUMS.txt').write_text(''.join(sha(p.read_bytes())+'  '+p.relative_to(output).as_posix()+'\n'
            for p in sorted(output.rglob('*')) if p.is_file() and p.name!='SHA256SUMS.txt'))
        print(json.dumps(receipt|{'sources':len(receipt['sources']),'copy_ready':str(output)},indent=2));return
    shutil.copy2(ROOT/'FEXTendo-Patch.nro',assets_output/'FEXTendo-Patch.nro')
    shutil.copy2(ROOT/'romfs/catalog.json',assets_output/'fextendo-patch.json')
    shutil.copy2(ROOT/'README.md',assets_output/'README.md')
    shutil.copy2(output/'build-receipt.json',assets_output/'build-receipt.json')
    if (ROOT/'dist/toolchain.txt').exists():
        shutil.copy2(ROOT/'dist/toolchain.txt',assets_output/'toolchain.txt')
    for name in seen:shutil.copy2(ROOT/'romfs/boot'/name,assets_output/name)
    # Corresponding source for app and boot patch changes travels with release binaries.
    archive=assets_output/'FEXTendo-Patch-source.tar.gz'
    with tarfile.open(archive,'w:gz') as tar:
        for name in ['source','include','tools','tests','romfs','assets','third_party','provenance','docs','.github',
                     'Makefile','LICENSE','README.md','THIRD_PARTY.md','MULAI-DI-SINI.txt','update.ini.example','.gitignore','.gitattributes']:
            path=ROOT/name
            if not path.exists():continue
            if path.is_file():tar.add(path,arcname='fextendo-patch/'+name)
            else:
                for p in sorted(path.rglob('*')):
                    if p.is_file() and '__pycache__' not in str(p):tar.add(p,arcname='fextendo-patch/'+str(p.relative_to(ROOT)).replace('\\','/'))
    for folder in [output,assets_output]:
        lines=[]
        for p in sorted(folder.rglob('*')):
            if p.is_file() and p.name!='SHA256SUMS.txt':lines.append(sha(p.read_bytes())+'  '+str(p.relative_to(folder)).replace('\\','/'))
        (folder/'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n')
    print(json.dumps(receipt|{'sources':len(receipt['sources']),'copy_ready':str(output)},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'dist/FEXTendo-Patch-v1.1.0');p.add_argument('--assets-output',type=Path,default=ROOT/'dist/release-assets');p.add_argument('--copy-only',action='store_true');a=p.parse_args()
    release(a.output,a.assets_output,a.copy_only)
