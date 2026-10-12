"""Import verified Standard loaders without changing the published HOC pairs."""
import argparse, hashlib, json, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('build',type=Path);a=p.parse_args()
    report=json.loads((a.build/'build.json').read_text())
    assert report['revision']=='28d6a2e11f2640077bbb8a9fbd463d3fa12b6984'
    assert report['loader_kind']=='stock' and report['abi']=='fxtmem-v1' and report['extension']=='fxtauto-v1'
    assert not report['hoc_symbols'] and report['host_validation']['passed']
    assert sha(a.build/'standard-1.12.0.patch')==report['patch_sha256']
    assert sha(a.build/'host-validation.txt')==report['host_validation']['evidence_sha256']
    assert sha(ROOT/'tools/build_stock_112.py')==report['builder_sha256']
    assert sha(ROOT/'tools/check_ams112.py')==report['host_validation']['checker_sha256']
    new=a.build/'loader-stock-1.12.0-auto-v1.3.0.kip'
    assert sha(new)==report['payload_sha256'] and new.stat().st_size==report['payload_bytes']
    olddir=ROOT/'provenance/memory-auto-v1.1.0'
    old=json.loads((olddir/'build.json').read_text());assert old['passed'] and old['kernel_unchanged']
    stock=olddir/'loader-stock.kip';assert sha(stock)==old['files']['loader-stock.kip']
    catalog=json.loads((ROOT/'romfs/catalog.json').read_text())
    for ams,source in [('1.11.2',stock),('1.12.0',new)]:
        base=next(b for b in catalog['bundles'] if b['atmosphere']==ams and b.get('loader_kind','hoc')=='hoc')
        b=json.loads(json.dumps(base));b.update(version='1.3.0',loader_kind='stock',hoc='',hoc_configuration='not-applicable')
        dest=ROOT/'romfs/boot'/f'loader-stock-{ams}-auto-v1.3.0.kip'
        if dest.exists():assert sha(dest)==sha(source)
        else:shutil.copy2(source,dest)
        b['loader']=dict(asset=dest.name,bytes=dest.stat().st_size,sha256=sha(dest))
        matches=[x for x in catalog['bundles'] if x['atmosphere']==ams and x.get('loader_kind')=='stock']
        if matches:assert matches==[b]
        else:catalog['bundles'].append(b)
    catalog.update(catalog_version='1.3.0',min_app_version='1.3.0')
    (ROOT/'romfs/catalog.json').write_text(json.dumps(catalog,indent=2)+'\n')
    dest=ROOT/'provenance/standard-1.12.0';dest.mkdir(parents=True,exist_ok=True)
    for name in ['build.json','standard-1.12.0.patch','host-validation.txt','auto-host.cpp','layout-host.cpp']:
        shutil.copy2(a.build/name,dest/name)
    print('Imported two Standard loaders; existing kernel and HOC payloads retained.')
if __name__=='__main__':main()
