"""Build fxtauto-v1 loaders from the exact distributed v1 sources, in isolation.

The already-tested kernel binary remains byte-identical. HOC retains official
release defaults. No installed boot configuration or other checkout is edited.
"""
import argparse,hashlib,json,os,shutil,subprocess
from pathlib import Path
from fextendo_low_window import ROOT,SOURCE,AMS_REV,exact
BUILD=Path('out/nintendo_nx_arm64_armv8a/release')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--installer',type=Path,default=ROOT.parent/'fextendo-patch');a=p.parse_args()
    assert not a.work.exists() and not a.output.exists(),'Use fresh build and output paths'
    old=a.installer/'provenance/memory';receipt=json.loads((old/'provenance/original-build.json').read_text())
    assert receipt['ams_revision']==AMS_REV
    a.work.mkdir(parents=True);a.output.mkdir(parents=True)
    (a.output/'source').mkdir();(a.output/'evidence').mkdir()
    env=dict(os.environ,DEVKITPRO='/opt/devkitpro',DEVKITA64='/opt/devkitpro/devkitA64',DEVKITARM='/opt/devkitpro/devkitARM',
        TMPDIR=str(a.work),TMP=str(a.work),TEMP=str(a.work))
    host=a.work/'auto-tests'
    subprocess.run(['g++','-std=c++17','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=undefined',
        str(ROOT/'tests/fextendo_auto.cpp'),'-o',str(host)],check=True)
    test=subprocess.run([str(host)],capture_output=True,text=True,check=True)
    assert 'runtime error:' not in test.stderr
    print(test.stdout.strip(),flush=True)
    (a.output/'evidence/auto-host.txt').write_text(test.stdout)
    changed={};trees=[]
    cache=Path('/home/blekjek/sleepingdogs-low-window-v1/atmosphere')
    assert subprocess.check_output(['git','-c','safe.directory='+str(cache),'-C',str(cache),'rev-parse','HEAD'],text=True).strip()==AMS_REV
    for name in ('atmosphere','atmosphere-hoc'):
        tree=a.work/name;trees.append(tree)
        subprocess.run(['git','-c','safe.directory='+str(cache),'clone','--no-hardlinks',str(cache),str(tree)],check=True,stdout=subprocess.DEVNULL)
        patch=old/'source'/f'{name}-fextendo.patch';assert sha(patch)==receipt['files'][patch.name]
        subprocess.run(['git','-C',str(tree),'apply',str(patch)],check=True)
        for n,h in receipt['prepared']['changes'][name].items():assert sha(tree/n)==h,n
        shutil.copy2(SOURCE/'fextendo_memory_abi.hpp',tree/'libraries/libvapours/include/vapours/svc/svc_fextendo_memory.hpp')
        shutil.copy2(SOURCE/'ldr_fextendo_memory.inc',tree/'stratosphere/loader/source/ldr_fextendo_memory.inc')
        # The distributed v1 call is already between parameter initialization
        # and ASLR layout. Validate the exact ordering in BOTH upstream loaders.
        text=(tree/'stratosphere/loader/source/ldr_process_creation.cpp').read_text()
        start=text.index('Result CreateProcessAndLoadAutoLoadModules(');fn=text[start:text.index('\n    }',start)]
        anchors=['GetCreateProcessParameter(', 'ApplyFextendoMemoryDescriptor(', 'DecideAddressSpaceLayout(', 'svc::CreateProcess(']
        positions=[fn.index(x) for x in anchors];assert positions==sorted(positions)
        assert 'switch (out_param->flags & svc::CreateProcessFlag_AddressSpaceMask)' in text
        subprocess.run(['git','-C',str(tree),'add','-N','.'],check=True)
        outpatch=a.output/'source'/f'{name}-fxtauto.patch'
        outpatch.write_bytes(subprocess.check_output(['git','-C',str(tree),'diff','--binary','HEAD']))
        changed[name]={'patch_sha256':sha(outpatch),'frontdoor_order':anchors}
        print('Building '+name+' loader',flush=True)
        with (a.work/(name+'.log')).open('w') as log:
            subprocess.run(['make','-s','-C',str(tree/'stratosphere/loader'),'-j4'],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    hoc=trees[1]/'stratosphere/loader'/BUILD
    hactool=Path('/home/blekjek/sleepingdogs-low-window-v1/hactool/hactool')
    subprocess.run([str(hactool),'-t','kip1','--uncompressed='+str(a.output/'loader-hoc.kip'),str(hoc/'loader.kip')],check=True,stdout=subprocess.DEVNULL)
    data=(a.output/'loader-hoc.kip').read_bytes();oldkip=(a.installer/'romfs/boot/loader-hoc-1.11.2.kip').read_bytes()
    assert sha(a.installer/'romfs/boot/loader-hoc-1.11.2.kip')==receipt['files']['loader-hoc.kip']
    at=data.index(b'CUST',256);assert data.find(b'CUST',at+4)==-1
    prev=receipt['hoc_settings_output_offset'];settings_bytes=receipt['hoc_settings_bytes']
    assert data[at:at+settings_bytes]==oldkip[prev:prev+settings_bytes] and hashlib.sha256(data[at:at+settings_bytes]).hexdigest()==receipt['hoc_settings_sha256']
    kernel=a.installer/'romfs/boot/mesosphere-1.11.2.bin';assert sha(kernel)==receipt['files']['mesosphere.bin']
    shutil.copy2(kernel,a.output/'mesosphere.bin')
    shutil.copy2(trees[0]/'stratosphere/loader'/BUILD/'loader.kip',a.output/'loader-stock.kip')
    for name in ('LICENSE.Atmosphere','LICENSE.HOC'):shutil.copy2(old/'licenses'/name,a.output/name)
    sources=['src/experimental/low_window/fextendo_memory_abi.hpp','src/experimental/low_window/ldr_fextendo_memory.inc',
        'src/experimental/low_window/forwarder_auto.inc','tools/build-fextendo-auto-loader.py','tests/fextendo_auto.cpp']
    for n in sources:
        dst=a.output/'source'/n;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/n,dst)
    report=dict(passed=True,hardware_tested=False,version='1.1.0',abi='fxtmem-v1',extension='fxtauto-v1',
        atmosphere='1.11.2',revision=AMS_REV,hoc='2.5.1',kernel_unchanged=True,hoc_configuration='official-release-default',
        hoc_settings_sha256=receipt['hoc_settings_sha256'],hoc_settings_output_offset=at,hoc_settings_bytes=settings_bytes,
        changes=changed,sources={n:sha(ROOT/n) for n in sources},
        files={n:sha(a.output/n) for n in ('mesosphere.bin','loader-hoc.kip','loader-stock.kip')})
    # Preserve both ELF hashes for later disassembly/ABI validation.
    report['elfs']={tree.name:sha(tree/'stratosphere/loader'/BUILD/'loader.elf') for tree in trees}
    (a.output/'build.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Built both loaders; kernel unchanged, official HOC settings identical. Switch validation pending.',flush=True)
if __name__=='__main__':main()
