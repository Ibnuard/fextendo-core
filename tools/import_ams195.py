"""Import verified 1.9.5 kernel and loader variants into the 1.3.0 catalog."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from build_ams195 import ROOT, REVISION, LIBNX_REVISION, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('build',type=Path)
    p.add_argument('--package-audit',type=Path,required=True)
    a=p.parse_args(); out=a.build
    r=json.loads((out/'build.json').read_text()); audit=json.loads(a.package_audit.read_text())
    assert r['revision']==REVISION and r['atmosphere']=='1.9.5' and r['version']=='1.3.0'
    assert r['libnx_revision']==LIBNX_REVISION and r['title_id_allowlist'] is None
    assert r['abi']=='fxtmem-v1' and r['extension']=='fxtauto-v1' and not r['stock_hoc_symbols']
    assert r['hoc']=='2.5.1' and r['hoc_configuration']=='official-release-default'
    assert r['builder_sha256']==sha(ROOT/'tools/build_ams195.py')
    assert r['host_validation']['passed'] and r['host_validation']['checker_sha256']==sha(ROOT/'tools/check_ams195.py')
    assert sha(out/'host-validation.txt')==r['host_validation']['evidence_sha256']
    for items in [r['files'],r['patches'],r['host_validation']['harnesses']]:
        for name,digest in items.items(): assert sha(out/name)==digest
    d=(out/'loader-hoc.kip').read_bytes(); at=r['hoc_settings_output_offset']; n=r['hoc_settings_bytes']
    assert hashlib.sha256(d[at:at+n]).hexdigest()==r['hoc_settings_sha256']=='7f2ecdbb11bd27cedd1c49d2086cd006cab18087f945272178292254bdbfdf3f'
    assert audit['user_matches_official'] and audit['revision']==REVISION[:8]
    assert audit['official_package3_sha256']==audit['user_package3_sha256']=='b7d595469a681218c34adde1c355253babf86b34d29e2f411d2235f690f65076'
    catalog=ROOT/'romfs/catalog.json'; c=json.loads(catalog.read_text())
    assert c['min_app_version']==c['catalog_version']=='1.3.0'
    copies={}
    for kind in ['stock','hoc']:
        b=dict(version='1.3.0', atmosphere='1.9.5', revision=REVISION[:8],
               hoc='2.5.1' if kind=='hoc' else '', tested_hos=r['reference_hos'],
               hoc_configuration='official-release-default' if kind=='hoc' else 'not-applicable')
        if kind=='stock': b['loader_kind']='stock'
        for key,src,dst in [('kernel','mesosphere.bin','mesosphere-1.9.5.bin'),
                            ('loader','loader-'+kind+'.kip','loader-'+kind+'-1.9.5-auto-v1.3.0.kip')]:
            dest=ROOT/'romfs/boot'/dst
            if dest.exists(): assert sha(dest)==r['files'][src], 'Refusing to overwrite a different payload'
            b[key]=dict(asset=dst,bytes=(out/src).stat().st_size,sha256=r['files'][src])
            copies[src]=dest
        previous=[x for x in c['bundles'] if x['atmosphere']=='1.9.5' and x.get('loader_kind','hoc')==kind]
        assert not previous or previous==[b], 'Published bundle is immutable'
        if not previous: c['bundles'].append(b)
    for src,dest in copies.items(): shutil.copy2(out/src,dest)
    catalog.write_text(json.dumps(c,indent=2)+'\n')
    dest=ROOT/'provenance/ams-1.9.5';dest.mkdir(parents=True,exist_ok=True)
    for name in ['build.json','prepared.json','hoc-prepared.json','atmosphere-1.9.5-standard.patch',
                 'atmosphere-1.9.5-hoc.patch','host-validation.txt','auto-host.cpp','layout-host.cpp']:
        shutil.copy2(out/name,dest/name)
    shutil.copy2(a.package_audit,dest/'package3-audit.json')
    print('Added Atmosphere 1.9.5 Standard and HOC; prior bundles retained.')


if __name__=='__main__': main()
