"""Import a verified fxtauto-v1 loader update while retaining the v1 kernel.

No SD card is modified. Run prepare.py afterwards to regenerate catalog hashes.
"""
import argparse,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('build',type=Path);a=p.parse_args()
    r=json.loads((a.build/'build.json').read_text())
    assert r['passed'] and r['abi']=='fxtmem-v1' and r['extension']=='fxtauto-v1' and r['version']=='1.1.0'
    assert r['kernel_unchanged'] and r['hoc_configuration']=='official-release-default'
    assert r['atmosphere']=='1.11.2' and r['revision']=='5388824be146a89619e8d641acd64599cf1c5f62'
    assert r['hoc']=='2.5.1'
    for n,h in r['files'].items():assert sha(a.build/n)==h,n
    loader=(a.build/'loader-hoc.kip').read_bytes()
    off=r['hoc_settings_output_offset'];size=r['hoc_settings_bytes']
    assert loader[:4]==b'KIP1' and not loader[31]&7 and loader.find(b'CUST',256)==off
    assert hashlib.sha256(loader[off:off+size]).hexdigest()==r['hoc_settings_sha256']=='7f2ecdbb11bd27cedd1c49d2086cd006cab18087f945272178292254bdbfdf3f'
    for n,h in r['sources'].items():assert sha(a.build/'source'/n)==h,n
    for name,x in r['changes'].items():assert sha(a.build/'source'/f'{name}-fxtauto.patch')==x['patch_sha256']
    catalog=json.loads((ROOT/'romfs/catalog.json').read_text());assert len(catalog['bundles'])==1
    bundle=catalog['bundles'][0]
    kernel=ROOT/'romfs/boot'/bundle['kernel']['asset']
    assert sha(kernel)==r['files']['mesosphere.bin']
    # Versioned filename avoids reusing an old immutable loader asset identity.
    dest=ROOT/'romfs/boot/loader-hoc-1.11.2-auto-v1.1.0.kip'
    if dest.exists():assert sha(dest)==r['files']['loader-hoc.kip']
    else:shutil.copy2(a.build/'loader-hoc.kip',dest)
    bundle['version']='1.1.0'
    bundle['loader']={'asset':dest.name,'bytes':dest.stat().st_size,'sha256':sha(dest)}
    catalog['catalog_version']='1.1.0'
    # The existing schema and installer already handle this bundle; min stays 1.0.0.
    (ROOT/'romfs/catalog.json').write_text(json.dumps(catalog,indent=2)+'\n')
    shutil.copytree(a.build,ROOT/'provenance/memory-auto-v1.1.0',dirs_exist_ok=True)
    print('Imported automatic-mode loader v1.1.0; kernel and official HOC settings preserved.')
if __name__=='__main__':main()
