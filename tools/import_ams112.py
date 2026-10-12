"""Import a built, host-validated 1.12.0 pair without altering legacy bundles."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from build_ams112 import ROOT, REVISION, LIBNX_REVISION, OLD, OLD_PATCH_SHA, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('build',type=Path)
    a=p.parse_args();build=a.build
    r=json.loads((build/'build.json').read_text())
    assert r['revision']==REVISION and r['atmosphere']=='1.12.0' and r['version']=='1.2.0'
    assert r['libnx_revision']==LIBNX_REVISION
    assert r['abi']=='fxtmem-v1' and r['extension']=='fxtauto-v1'
    assert r['hoc']=='2.5.1' and r['hoc_configuration']=='official-release-default'
    assert r['hoc_settings_sha256']=='7f2ecdbb11bd27cedd1c49d2086cd006cab18087f945272178292254bdbfdf3f'
    assert r['host_validation']['passed'] and r['title_id_allowlist'] is None
    assert r['build_builder_sha256']==sha(ROOT/'tools/build_ams112.py')
    assert r['prepared']['builder_sha256']==sha(build/'preparation-builder.py')
    assert r['host_validation']['checker_sha256']==sha(ROOT/'tools/check_ams112.py')
    assert sha(OLD/'source/atmosphere-hoc-fxtauto.patch')==OLD_PATCH_SHA
    assert sha(build/'host-validation.txt')==r['host_validation']['evidence_sha256']
    patch=build/'atmosphere-1.12.0-fextendo-hoc.patch'
    assert sha(patch)==r['prepared']['patch_sha256']
    for name,digest in r['files'].items():assert sha(build/name)==digest
    for name,digest in r['host_validation']['harnesses'].items():assert sha(build/name)==digest
    data=(build/'loader-hoc.kip').read_bytes();off=r['hoc_settings_output_offset'];size=r['hoc_settings_bytes']
    assert data[:4]==b'KIP1' and not data[31]&7
    assert hashlib.sha256(data[off:off+size]).hexdigest()==r['hoc_settings_sha256']
    catalog_path=ROOT/'romfs/catalog.json';c=json.loads(catalog_path.read_text())
    assert c['schema']==1 and c['abi']=='fxtmem-v1'
    b=dict(version='1.2.0',atmosphere='1.12.0',revision=REVISION[:8],hoc='2.5.1',
           hoc_configuration='official-release-default',tested_hos=r['reference_hos'])
    for kind,source,dest in [('kernel','mesosphere.bin','mesosphere-1.12.0.bin'),
                             ('loader','loader-hoc.kip','loader-hoc-1.12.0-auto-v1.2.0.kip')]:
        path=ROOT/'romfs/boot'/dest
        if path.exists():assert sha(path)==r['files'][source], 'Refusing to overwrite a different payload'
        b[kind]=dict(asset=dest,bytes=(build/source).stat().st_size,sha256=r['files'][source])
    previous=[x for x in c['bundles'] if x['atmosphere']=='1.12.0' and x['revision']==REVISION[:8]]
    assert not previous or previous==[b], 'Same-version bundle must stay immutable'
    for kind,source in [('kernel','mesosphere.bin'),('loader','loader-hoc.kip')]:
        shutil.copy2(build/source,ROOT/'romfs/boot'/b[kind]['asset'])
    if not previous:c['bundles'].append(b)
    c['catalog_version']='1.2.0';catalog_path.write_text(json.dumps(c,indent=2)+'\n')
    dest=ROOT/'provenance/ams-1.12.0';dest.mkdir(parents=True,exist_ok=True)
    for name in ['build.json','prepared.json','preparation-builder.py','atmosphere-1.12.0-fextendo-hoc.patch',
                 'host-validation.txt','auto-host.cpp','layout-host.cpp']:
        shutil.copy2(build/name,dest/name)
    print('Imported Atmosphere 1.12.0 pair; existing bundles retained unchanged.')


if __name__=='__main__':main()
