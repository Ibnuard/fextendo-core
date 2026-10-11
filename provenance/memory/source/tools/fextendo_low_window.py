"""Versioned opt-in low-window overlay for AMS 1.11.2 / HOC 2.5.1.

Applies after the pinned Autorun low-window patch. No Title ID predicates remain.
"""
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src/experimental/low_window'
AMS_REV = '5388824be146a89619e8d641acd64599cf1c5f62'
HOC_REV = 'd9906a794c6015a892c60744d520faf793d22549'
AUTORUN_REV = 'cbb0e4e6e7fa7f47f328d92441f51bfb507f266f'


def descriptor():
    return struct.pack('<8sIIIIQ', b'FXTMEM\0\0', 1, 32, 1, 0, 0)


def exact(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError('Source anchor changed: ' + old[:100])
    return text.replace(old, new, 1)


def edit(path, old, new):
    path.write_text(exact(path.read_text(), old, new))


def apply(tree, hoc=False):
    svc = tree / 'libraries/libvapours/include/vapours/svc'
    (svc / 'svc_fextendo_memory.hpp').write_bytes((SOURCE / 'fextendo_memory_abi.hpp').read_bytes())
    header = svc / 'svc_types_common.hpp'
    edit(header, '#include <vapours/svc/svc_common.hpp>',
         '#include <vapours/svc/svc_common.hpp>\n#include <vapours/svc/svc_fextendo_memory.hpp>')
    edit(header, '        /* Mask of all flags. */\n        CreateProcessFlag_All',
         '        /* Private, versioned FEXTendo kernel/loader ABI; not an NPDM bit. */\n'
         '        CreateProcessFlag_FextendoLowWindow = fextendo::RequestFlag,\n\n'
         '        /* Mask of all flags. */\n        CreateProcessFlag_All')
    edit(header, '                                CreateProcessFlag_EnableAliasRegionExtraSize,',
         '                                CreateProcessFlag_EnableAliasRegionExtraSize |\n'
         '                                CreateProcessFlag_FextendoLowWindow,')
    edit(header, '    /* Debug types. */', '''    static_assert(CreateProcessFlag_Is64Bit == 1);
    static_assert(CreateProcessFlag_AddressSpaceMask == 0x0e);
    static_assert(CreateProcessFlag_AddressSpace64Bit == 6);
    static_assert(CreateProcessFlag_IsApplication == 0x40);
    static_assert(CreateProcessFlag_PoolPartitionMask == 0x780);
    static_assert(CreateProcessFlag_PoolPartitionApplication == 0);
    static_assert(CreateProcessFlag_EnableAliasRegionExtraSize == 0x2000);
    static_assert((CreateProcessFlag_All & ~CreateProcessFlag_FextendoLowWindow) == 0x3fff);

    /* Debug types. */''')
    edit(svc / 'svc_memory_map.hpp', '''    constexpr inline bool HasAutorunLowWindow(u64 program_id) {
        return program_id == UINT64_C(0x0548EABB35576000);
    }

    constexpr inline u64 AutorunNativeAddressStart = UINT64_C(0x100000000);

''', '')
    process = tree / 'libraries/libmesosphere/source/kern_k_process.cpp'
    edit(process, 'ams::svc::HasAutorunLowWindow(params.program_id)',
         'ams::svc::fextendo::Requested(params.flags)')
    page_table = tree / 'libraries/libmesosphere/source/kern_k_page_table_base.cpp'
    text = page_table.read_text()
    if text.count('ams::svc::AutorunNativeAddressStart') != 2:
        raise RuntimeError('Unexpected low-window page table source')
    page_table.write_text(text.replace('ams::svc::AutorunNativeAddressStart', 'ams::svc::fextendo::NativeStart'))
    kernel = tree / 'libraries/libmesosphere/source/svc/kern_svc_process.cpp'
    edit(kernel, '            /* Validate that 64-bit process is okay. */', '''            /* Validate the opt-in layout independently of the userland loader. */
            if (ams::svc::fextendo::Requested(params.flags)) {
                R_UNLESS(ams::svc::fextendo::CompatibleFlags(params.flags), svc::ResultInvalidCombination());
                R_UNLESS(params.code_address >= ams::svc::fextendo::NativeStart, svc::ResultInvalidAddress());
            }

            /* Validate that 64-bit process is okay. */''')
    apply_loader(tree, hoc)


def apply_loader(tree, hoc=False):
    folder = tree / 'stratosphere/loader/source'
    (folder / 'ldr_fextendo_memory.inc').write_bytes((SOURCE / 'ldr_fextendo_memory.inc').read_bytes())
    path = folder / 'ldr_process_creation.cpp'
    edit(path, '        /* Convenience defines. */',
         '        #include "ldr_fextendo_memory.inc"\n\n        /* Convenience defines. */')
    # Both pinned loaders call this before their own ASLR/layout calculation.
    edit(path, '            R_TRY(GetCreateProcessParameter(std::addressof(param), meta, flags, resource_limit));',
         '            R_TRY(GetCreateProcessParameter(std::addressof(param), meta, flags, resource_limit));\n'
         '            R_TRY(ApplyFextendoMemoryDescriptor(std::addressof(param)));')
    if hoc:
        edit(path, '                        aslr_size  = svc::AddressMap39Size;\n                        break;',
             '                        aslr_size  = svc::AddressMap39Size;\n'
             '                        if (svc::fextendo::Requested(out_param->flags)) {\n'
             '                            aslr_start = svc::fextendo::NativeStart;\n'
             '                            aslr_size  = svc::AddressMap39End - aslr_start;\n'
             '                        }\n                        break;')
    else:
        edit(path, 'svc::HasAutorunLowWindow(out_param->program_id)', 'svc::fextendo::Requested(out_param->flags)')
        edit(path, 'svc::AutorunNativeAddressStart', 'svc::fextendo::NativeStart')

