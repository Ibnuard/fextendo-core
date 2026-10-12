"""Run host checks against the actual prepared 1.12.0 source, not a model port."""
import argparse
import json
from pathlib import Path
import subprocess
from build_ams112 import ROOT, OLD, REVISION, sha


def block(text, anchor):
    start = text.index(anchor)
    brace = text.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        if text[end] == '{': depth += 1
        if text[end] == '}': depth -= 1
        end += 1
    return text[start:end]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tree', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    tree, out = a.tree.resolve(), a.output.resolve()
    receipt = json.loads((out/'build.json').read_text())
    assert receipt['revision'] == REVISION and not receipt['hardware_tested']
    for name, digest in receipt['prepared']['files'].items():
        assert sha(tree/name) == digest, 'Prepared source changed: '+name
    for name, digest in receipt['files'].items():
        assert sha(out/name) == digest
    svc = tree/'libraries/libvapours/include/vapours/svc'
    loader = tree/'stratosphere/loader/source/ldr_process_creation.cpp'
    page = tree/'libraries/libmesosphere/source/kern_k_page_table_base.cpp'
    abi = OLD/'source/src/experimental/low_window'
    code = (OLD/'source/tests/fextendo_auto.cpp').read_text()
    code = code.replace('../src/experimental/low_window/fextendo_memory_abi.hpp', str(svc/'svc_fextendo_memory.hpp'))
    code = code.replace('../src/experimental/low_window/ldr_fextendo_memory.inc', str(loader.parent/'ldr_fextendo_memory.inc'))
    code = code.replace('../src/experimental/low_window/forwarder_auto.inc', str(abi/'forwarder_auto.inc'))
    code = code.replace('CreateProcessFlag_FextendoLowWindow', 'CreateProcessParameterFlag_FextendoLowWindow')
    # Exercise the new ShadowStack bit and 42-bit address-space selector too.
    code = code.replace('flags<0x4000', 'flags<0x40000').replace('16384 flag combinations', '262144 flag combinations')
    source = out/'auto-host.cpp';source.write_text(code)
    compiler = ['g++','-std=c++17','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=undefined']
    subprocess.run([*compiler,str(source),'-o',str(out/'auto-host')],check=True)
    results = []
    def execute(name):
        r = subprocess.run([str(out/name)],capture_output=True,text=True,check=True)
        assert 'runtime error:' not in r.stderr, r.stderr
        results.append(r.stdout.strip())
    execute('auto-host')

    text = loader.read_text()
    creation = block(text, 'Result CreateProcessAndLoadAutoLoadModules(')
    order = [creation.index(n) for n in ['GetCreateProcessParameter(', 'ApplyFextendoMemoryDescriptor(',
                                        'DecideAddressSpaceLayout(', 'svc::CreateProcess(']]
    assert order == sorted(order)
    switch = block(text, 'switch (out_param->flags & svc::CreateProcessParameterFlag_AddressSpaceMask)')
    optin = block(page.read_text(), 'if (ams::svc::fextendo::Requested(flags))')
    process=(tree/'libraries/libmesosphere/source/svc/kern_svc_process.cpp').read_text()
    guard=block(process,'if (ams::svc::fextendo::Requested(params.flags))')
    known=next(line.strip() for line in process.splitlines() if 'R_UNLESS((params.flags & ~ams::svc::CreateProcessParameterFlag_All)' in line)
    enum = block((svc/'svc_types_common.hpp').read_text(), 'enum CreateProcessParameterFlag : u32')+';'
    # Use the real upstream memory-map constants and real enum, plus the actual
    # production ASLR switch and page-table opt-in block. Only surrounding kernel
    # objects and Result infrastructure are replaced with small host scaffolding.
    layout = '''#include <cassert>
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
int page(u32 flags, unsigned address_space_width,u64 code_address,u64& m_code_region_start,u64& m_alias_code_region_start) {
 OPTIN
 return 0;
}
int main(){
 assert(validate({0x40000067,0x100000000})==0);
 assert(validate({0x40020067,0x100000000})==0);
 assert(validate({0x40004067,0x100000000})==3);
 assert(validate({0x40000069,0x100000000})==1);
 assert(validate({0x40000067,0xfffff000})==2);
 assert(validate({0x40000065,0x100000000})==1);
 assert(aslr(0x65)==svc::AddressSmallMap32Start);
 assert(aslr(0x63)==svc::AddressSmallMap36Start);
 assert(aslr(0x67)==svc::AddressMap39Start);
 assert(aslr(0x69)==svc::AddressMap42Start);
 assert(aslr(0x40000067)==0x100000000);
 assert(aslr(0x40020067)==0x100000000);
 u64 code=99,alias=77;
 assert(page(0x67,39,0x100000000,code,alias)==0&&code==99&&alias==77);
 assert(page(0x69,42,0x100000000,code,alias)==0&&code==99&&alias==77);
 assert(page(0x40000067,42,0x100000000,code,alias)==1&&code==99&&alias==77);
 assert(page(0x40000067,39,0xfffff000,code,alias)==2&&code==99&&alias==77);
 assert(page(0x40002067,39,0x100000000,code,alias)==1);
 assert(page(0x400000e7,39,0x100000000,code,alias)==1);
 assert(page(0x40000067,39,0x100000000,code,alias)==0&&code==0x100000000&&alias==svc::AddressSmallMap32Start);
 puts("PASS: upstream 32/36/39/42 ASLR selection, opt-in high native placement, ShadowStack flag, low-code rejection, non-application and ASan rejection, unchanged unmarked layouts");
}
'''.replace('ABI',str(svc/'svc_fextendo_memory.hpp')).replace('MAP',str(svc/'svc_memory_map.hpp')).replace('ENUM',enum).replace('SWITCH',switch).replace('OPTIN',optin).replace('KNOWN',known).replace('GUARD',guard)
    path=out/'layout-host.cpp';path.write_text(layout)
    stub=out/'host-include/vapours';stub.mkdir(parents=True,exist_ok=True)
    (stub/'common.hpp').write_text('''#pragma once
#include <cstddef>
#include <cstdint>
constexpr std::size_t operator""_MB(unsigned long long n){return n*1024*1024;}
constexpr std::size_t operator""_GB(unsigned long long n){return n*1024*1024*1024;}
''')
    subprocess.run([*compiler,'-DATMOSPHERE_ARCH_ARM64','-I'+str(stub.parent),str(path),'-o',str(out/'layout-host')],check=True)
    execute('layout-host')
    (out/'host-validation.txt').write_text('\n'.join(results)+'\n')
    receipt['host_validation']={'passed':True,'evidence_sha256':sha(out/'host-validation.txt'),
        'harnesses':{n:sha(out/n) for n in ['auto-host.cpp','layout-host.cpp']},
        'checker_sha256':sha(Path(__file__))}
    (out/'build.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('\n'.join(results))


if __name__ == '__main__':main()
