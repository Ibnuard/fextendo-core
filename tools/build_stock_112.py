"""Build the Standard 1.12.0 loader from the sealed low-window source port.

Uses a fresh, pinned Atmosphere checkout and the already built pinned libnx.
The HOC sources, capabilities and hooks are excluded; the FEXTendo ABI stays.
"""
import argparse, hashlib, json, os, shutil, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REV = '28d6a2e11f2640077bbb8a9fbd463d3fa12b6984'
NX_REV = 'feebd026ca0f5dcc2119f46ad8e0d16ad3dd4973'
BUILD = Path('out/nintendo_nx_arm64_armv8a/release')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def git(tree,*args): return subprocess.check_output(['git','-C',str(tree),*args])
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['tree','output','libnx']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--jobs',type=int,default=4);a=p.parse_args()
    assert git(a.tree,'rev-parse','HEAD').decode().strip()==REV
    assert not git(a.tree,'status','--porcelain').strip(), 'Use a fresh checkout'
    assert git(a.libnx,'rev-parse','HEAD').decode().strip()==NX_REV
    assert not git(a.libnx,'status','--porcelain').strip()
    patch=ROOT/'provenance/ams-1.12.0/atmosphere-1.12.0-fextendo-hoc.patch'
    assert sha(patch)=='7f07c3803d1f94bd359887c98f9ad285c03d39e0afa51101ed23c21e743f4ec5'
    subprocess.run(['git','-C',str(a.tree),'apply','--exclude=stratosphere/loader/source/oc/*',
                    '--exclude=stratosphere/loader/loader.json',str(patch)],check=True)
    source=a.tree/'stratosphere/loader/source/ldr_process_creation.cpp'
    text=source.read_text()
    for hook in ['#include "oc/oc_loader.hpp"\n',
                 '        bool g_is_pcv;\n        bool g_is_ptm;\n',
                 '            g_is_pcv = meta->aci->program_id == ncm::SystemProgramId::Pcv;\n'
                 '            g_is_ptm = meta->aci->program_id == ncm::SystemProgramId::Ptm;\n',
                 '                if (g_is_pcv) hoc::pcv::Patch(map_address, nso_size);\n'
                 '                if (g_is_ptm) hoc::ptm::Patch(map_address, nso_size);\n']:
        assert text.count(hook)==1, 'HOC hook changed'
        text=text.replace(hook,'')
    assert 'hoc::' not in text and 'oc_loader' not in text
    source.write_text(text)
    assert not (a.tree/'stratosphere/loader/source/oc').exists()
    assert not git(a.tree,'diff','--','stratosphere/loader/loader.json').strip()
    for name in ['ldr_fextendo_memory.inc']:
        expected=json.loads((ROOT/'provenance/ams-1.12.0/prepared.json').read_text())['files']['stratosphere/loader/source/'+name]
        assert sha(a.tree/'stratosphere/loader/source'/name)==expected
    order=[text.index(s) for s in ['R_TRY(GetCreateProcessParameter(', 'R_TRY(ApplyFextendoMemoryDescriptor(', 'R_TRY(DecideAddressSpaceLayout(']]
    assert order==sorted(order)
    a.output.mkdir(parents=True,exist_ok=True)
    subprocess.run(['git','-C',str(a.tree),'add','-N','.'],check=True)
    (a.output/'standard-1.12.0.patch').write_bytes(git(a.tree,'diff','--binary','HEAD'))
    env=dict(os.environ,DEVKITPRO='/opt/devkitpro',DEVKITA64='/opt/devkitpro/devkitA64',
             DEVKITARM='/opt/devkitpro/devkitARM',LIBNX=str(a.libnx/'nx'),TMPDIR=str(a.output))
    env['CPLUS_INCLUDE_PATH']=env['C_INCLUDE_PATH']=str(a.libnx/'nx/external/bsd/include')
    with (a.output/'build.log').open('w') as log:
        subprocess.run(['make','-s','-C',str(a.tree/'stratosphere/loader'),'-j'+str(a.jobs)],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    kip=a.tree/'stratosphere/loader'/BUILD/'loader.kip'
    data=kip.read_bytes();assert data[:4]==b'KIP1' and int.from_bytes(data[16:24],'little')==0x0100000000000001
    # Symbol audit is independent of compressed KIP bytes.
    symbols=subprocess.check_output(['/opt/devkitpro/devkitA64/bin/aarch64-none-elf-nm','-C',str(a.tree/'stratosphere/loader'/BUILD/'loader.elf')]).decode()
    assert 'ams::ldr::hoc::' not in symbols
    shutil.copy2(kip,a.output/'loader-stock-1.12.0-auto-v1.3.0.kip')
    r=dict(atmosphere='1.12.0',revision=REV,loader_kind='stock',abi='fxtmem-v1',extension='fxtauto-v1',
           hardware_tested=False,libnx_revision=NX_REV,libnx_sha256=sha(a.libnx/'nx/lib/libnx.a'),
           builder_sha256=sha(Path(__file__)),patch_sha256=sha(a.output/'standard-1.12.0.patch'),
           payload_sha256=sha(kip),payload_bytes=len(data),hoc_symbols=False,descriptor_order=order)
    (a.output/'build.json').write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps(r,indent=2))
if __name__=='__main__':main()
