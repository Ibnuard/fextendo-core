"""Exercise the actual prepared 1.9.5 descriptor, allocator and kernel blocks."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from build_ams195 import REVISION, OLD, git, sha
from check_ams112 import block


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tree', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--prepared-source', action='store_true', help='Check the sealed Standard source before payloads finish building')
    a=p.parse_args(); tree=a.tree.resolve(); out=a.output.resolve()
    assert git(tree,'rev-parse','HEAD').decode().strip()==REVISION
    actual=hashlib.sha256(git(tree,'diff','--binary','HEAD')).hexdigest()
    if a.prepared_source:
        r=None; prepared=json.loads((out/'prepared.json').read_text())
        assert prepared['revision']==REVISION and actual==prepared['patch_sha256']
    else:
        r=json.loads((out/'build.json').read_text())
        assert r['revision']==REVISION and r['atmosphere']=='1.9.5' and not r['hardware_tested']
        assert actual==r['patches']['atmosphere-1.9.5-hoc.patch']
        for name,digest in r['files'].items(): assert sha(out/name)==digest
        for name,digest in r['patches'].items(): assert sha(out/name)==digest
    svc=tree/'libraries/libvapours/include/vapours/svc'
    loader=tree/'stratosphere/loader/source/ldr_process_creation.cpp'
    abi=OLD/'source/src/experimental/low_window'
    assert sha(svc/'svc_fextendo_memory.hpp')==sha(abi/'fextendo_memory_abi.hpp')
    assert sha(loader.parent/'ldr_fextendo_memory.inc')==sha(abi/'ldr_fextendo_memory.inc')
    code=(OLD/'source/tests/fextendo_auto.cpp').read_text()
    for before,after in [('../src/experimental/low_window/fextendo_memory_abi.hpp',svc/'svc_fextendo_memory.hpp'),
                         ('../src/experimental/low_window/ldr_fextendo_memory.inc',loader.parent/'ldr_fextendo_memory.inc'),
                         ('../src/experimental/low_window/forwarder_auto.inc',abi/'forwarder_auto.inc')]:
        code=code.replace(before,str(after))
    (out/'auto-host.cpp').write_text(code)
    compiler=['g++','-std=c++17','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=undefined']
    subprocess.run([*compiler,str(out/'auto-host.cpp'),'-o',str(out/'auto-host')],check=True)
    results=[]
    def execute(name):
        v=subprocess.run([str(out/name)],capture_output=True,text=True,check=True)
        assert 'runtime error:' not in v.stderr, v.stderr
        results.append(v.stdout.strip())
    execute('auto-host')
    text=loader.read_text(); creation=block(text,'Result CreateProcessAndLoadAutoLoadModules(')
    order=[creation.index(n) for n in ['GetCreateProcessParameter(', 'ApplyFextendoMemoryDescriptor(',
                                       'DecideAddressSpaceLayout(', 'svc::CreateProcess(']]
    assert order==sorted(order)
    switch=block(text,'switch (out_param->flags & svc::CreateProcessFlag_AddressSpaceMask)')
    page=(tree/'libraries/libmesosphere/source/kern_k_page_table_base.cpp').read_text()
    assert page.index('if (m_address_space_width == 39)') < page.index('if (ams::svc::fextendo::Requested(flags))')
    optin=block(page,'if (ams::svc::fextendo::Requested(flags))')
    process=(tree/'libraries/libmesosphere/source/svc/kern_svc_process.cpp').read_text()
    guard=block(process,'if (ams::svc::fextendo::Requested(params.flags))')
    known=next(line.strip() for line in process.splitlines() if 'R_UNLESS((params.flags & ~ams::svc::CreateProcessFlag_All)' in line)
    enum=block((svc/'svc_types_common.hpp').read_text(),'enum CreateProcessFlag : u32')+';'
    layout='''#include <cassert>
#include <cstdint>
#include <cstdio>
using u32=uint32_t;using u64=uint64_t;
#include "ABI"
#include "MAP"
namespace ams::svc {
ENUM
int ResultInvalidCombination(){return 1;} int ResultInvalidAddress(){return 2;} int ResultInvalidEnumValue(){return 3;}
}
namespace svc=ams::svc;
#define AMS_UNREACHABLE_DEFAULT_CASE() default: assert(false)
#define R_UNLESS(c,r) do{if(!(c))return r;}while(0)
struct Param {u32 flags;u64 code_address=0;};
int validate(Param params) {
 KNOWN
 GUARD
 return 0;
}
u64 aslr(u32 flags) {
 Param p{flags};auto* out_param=&p;u64 aslr_start=0,aslr_size=0;
 SWITCH
 assert(aslr_size>0);return aslr_start;
}
int page(u32 flags,unsigned m_address_space_width,u64 code_address,u64& m_code_region_start,u64& m_alias_code_region_start) {
 OPTIN
 return 0;
}
int main(){
 assert(validate({0x40000067,0x100000000})==0);
 assert(validate({0x40000067,0xfffff000})==2);
 assert(validate({0x40000065,0x100000000})==1);
 assert(validate({0x40000063,0x100000000})==1);
 assert(validate({0x40000027,0x100000000})==1);
 assert(validate({0x400000e7,0x100000000})==1);
 assert(validate({0x40002067,0x100000000})==1);
 for(unsigned bit=14;bit<32;bit++)if(bit!=30)assert(validate({0x40000067|(1u<<bit),0x100000000})==3);
 assert(aslr(0x61)==svc::AddressSmallMap32Start);
 assert(aslr(0x65)==svc::AddressSmallMap32Start);
 assert(aslr(0x63)==svc::AddressSmallMap36Start);
 assert(aslr(0x67)==svc::AddressMap39Start);
 assert(aslr(0x40000067)==0x100000000);
 u64 code=99,alias=77;
 assert(page(0x67,39,0x100000000,code,alias)==0&&code==99&&alias==77);
 assert(page(0x40000067,36,0x100000000,code,alias)==1&&code==99&&alias==77);
 assert(page(0x40000067,39,0xfffff000,code,alias)==2&&code==99&&alias==77);
 assert(page(0x40002067,39,0x100000000,code,alias)==1);
 assert(page(0x400000e7,39,0x100000000,code,alias)==1);
 assert(page(0x40000067,39,0x100000000,code,alias)==0&&code==0x100000000&&alias==svc::AddressSmallMap32Start);
 puts("PASS: 1.9.5 upstream 32/36/39 ASLR, opt-in native placement, invalid flags/pools/layout rejection, low-code rejection, unchanged unmarked layouts");
}
'''.replace('ABI',str(svc/'svc_fextendo_memory.hpp')).replace('MAP',str(svc/'svc_memory_map.hpp')).replace('ENUM',enum).replace('SWITCH',switch).replace('OPTIN',optin).replace('KNOWN',known).replace('GUARD',guard)
    (out/'layout-host.cpp').write_text(layout)
    stub=out/'host-include/vapours';stub.mkdir(parents=True,exist_ok=True)
    (stub/'common.hpp').write_text('''#pragma once
#include <cstddef>
#include <cstdint>
constexpr std::size_t operator""_MB(unsigned long long n){return n*1024*1024;}
constexpr std::size_t operator""_GB(unsigned long long n){return n*1024*1024*1024;}
''')
    subprocess.run([*compiler,'-DATMOSPHERE_ARCH_ARM64','-I'+str(stub.parent),str(out/'layout-host.cpp'),'-o',str(out/'layout-host')],check=True)
    execute('layout-host')
    evidence='prepared-source-validation.txt' if a.prepared_source else 'host-validation.txt'
    (out/evidence).write_text('\n'.join(results)+'\n')
    report=dict(passed=True,evidence_sha256=sha(out/evidence),
        harnesses={n:sha(out/n) for n in ['auto-host.cpp','layout-host.cpp']},checker_sha256=sha(Path(__file__)))
    if r is not None:
        r['host_validation']=report
        (out/'build.json').write_text(json.dumps(r,indent=2)+'\n')
    print('\n'.join(results))


if __name__=='__main__': main()
