"""Build isolated Atmosphere 1.9.5 FEXTendo Standard and optional HOC payloads.

The kernel and loader stay on the upstream 1.9.5 commit. Only the versioned
memory descriptor and reviewed HOC sources are ported; old payloads stay intact.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from build_ams112 import ROOT, OLD, OLD_PATCH_SHA, git, replace, run, sha

REVISION = 'de9b02007bbfc62f2f9ee2abf4a96bc337f5f86a'
LIBNX_REVISION = '7644c9b26099aa2d2145bc72a21ee24190e92085'  # v4.12.0: legacy PGL API, current newlib ABI
HAC_REVISION = '3121a5bf08cd81d3a99719feb2cab3b60767afd5'
# GCC 16 newly warns about an empty argument-pack index and dead switch arms
# after inlining DebuggerAttached's one-element parameter array. Keep the
# upstream code unchanged and the warnings visible; all other warnings stay fatal.
COMPILER_COMPAT = '-Wno-error=unused-but-set-variable -Wno-error=array-bounds'


def prepare(tree):
    assert git(tree, 'rev-parse', 'HEAD').decode().strip() == REVISION
    assert not git(tree, 'status', '--porcelain').strip(), 'Use a clean 1.9.5 checkout'
    svc = tree/'libraries/libvapours/include/vapours/svc'
    abi = OLD/'source/src/experimental/low_window'
    shutil.copy2(abi/'fextendo_memory_abi.hpp', svc/'svc_fextendo_memory.hpp')
    header = svc/'svc_types_common.hpp'
    replace(header, '#include <vapours/svc/svc_common.hpp>',
            '#include <vapours/svc/svc_common.hpp>\n#include <vapours/svc/svc_fextendo_memory.hpp>')
    replace(header, '        /* Mask of all flags. */\n        CreateProcessFlag_All',
            '        /* Private FEXTendo ABI; never an NPDM flag. */\n'
            '        CreateProcessFlag_FextendoLowWindow = fextendo::RequestFlag,\n\n'
            '        /* Mask of all flags. */\n        CreateProcessFlag_All')
    replace(header, '                                CreateProcessFlag_EnableAliasRegionExtraSize,',
            '                                CreateProcessFlag_EnableAliasRegionExtraSize |\n'
            '                                CreateProcessFlag_FextendoLowWindow,')
    replace(header, '    /* Debug types. */', '''    static_assert(CreateProcessFlag_Is64Bit == 1);
    static_assert(CreateProcessFlag_AddressSpaceMask == 0x0e);
    static_assert(CreateProcessFlag_AddressSpace32BitWithoutAlias == 4);
    static_assert(CreateProcessFlag_AddressSpace64Bit == 6);
    static_assert(CreateProcessFlag_IsApplication == 0x40);
    static_assert(CreateProcessFlag_PoolPartitionMask == 0x780);
    static_assert(CreateProcessFlag_PoolPartitionApplication == 0);
    static_assert(CreateProcessFlag_EnableAliasRegionExtraSize == 0x2000);
    static_assert((CreateProcessFlag_All & ~CreateProcessFlag_FextendoLowWindow) == 0x3fff);

    /* Debug types. */''')
    process = tree/'libraries/libmesosphere/source/svc/kern_svc_process.cpp'
    replace(process, '            /* Validate that 64-bit process is okay. */', '''            /* Validate the descriptor independently of the userland loader. */
            if (ams::svc::fextendo::Requested(params.flags)) {
                R_UNLESS(ams::svc::fextendo::CompatibleFlags(params.flags), svc::ResultInvalidCombination());
                R_UNLESS(params.code_address >= ams::svc::fextendo::NativeStart, svc::ResultInvalidAddress());
            }

            /* Validate that 64-bit process is okay. */''')
    page = tree/'libraries/libmesosphere/source/kern_k_page_table_base.cpp'
    replace(page, '            process_code_start                    = util::AlignDown(GetInteger(code_address), RegionAlignment);', '''            if (ams::svc::fextendo::Requested(flags)) {
                R_UNLESS(m_address_space_width == 39 && ams::svc::fextendo::CompatibleFlags(flags), svc::ResultInvalidCombination());
                R_UNLESS(code_address >= ams::svc::fextendo::NativeStart, svc::ResultInvalidAddress());
                m_code_region_start       = ams::svc::fextendo::NativeStart;
                m_alias_code_region_start = ams::svc::AddressSmallMap32Start;
            }

            process_code_start                    = util::AlignDown(GetInteger(code_address), RegionAlignment);''')
    loader = tree/'stratosphere/loader/source'
    shutil.copy2(abi/'ldr_fextendo_memory.inc', loader/'ldr_fextendo_memory.inc')
    path = loader/'ldr_process_creation.cpp'
    replace(path, '        /* Convenience defines. */',
            '        #include "ldr_fextendo_memory.inc"\n\n        /* Convenience defines. */')
    replace(path, '            R_TRY(GetCreateProcessParameter(std::addressof(param), meta, flags, resource_limit));',
            '            R_TRY(GetCreateProcessParameter(std::addressof(param), meta, flags, resource_limit));\n'
            '            R_TRY(ApplyFextendoMemoryDescriptor(std::addressof(param)));')
    replace(path, '                        aslr_size  = svc::AddressMap39Size;\n                        break;',
            '                        aslr_size  = svc::AddressMap39Size;\n'
            '                        if (svc::fextendo::Requested(out_param->flags)) {\n'
            '                            aslr_start = svc::fextendo::NativeStart;\n'
            '                            aslr_size  = svc::AddressMap39End - aslr_start;\n'
            '                        }\n                        break;')
    # libnx now declares this raw SVC output as DebugEventInfo* instead of void*.
    # Backport the upstream pointer cast, with explicit ABI layout checks.
    shim=tree/'libraries/libstratosphere/include/stratosphere/svc/svc_stratosphere_shims.hpp'
    replace(shim, '                    R_RETURN(::svcGetDebugEvent(out_info.GetPointerUnsafe(), debug_handle));',
            '                    static_assert(sizeof(::ams::svc::lp64::DebugEventInfo) == sizeof(::DebugEventInfo));\n'
            '                    static_assert(alignof(::ams::svc::lp64::DebugEventInfo) == alignof(::DebugEventInfo));\n'
            '                    static_assert(offsetof(::ams::svc::lp64::DebugEventInfo, info) == offsetof(::DebugEventInfo, info));\n'
            '                    R_RETURN(::svcGetDebugEvent(reinterpret_cast<::DebugEventInfo *>(out_info.GetPointerUnsafe()), debug_handle));')
    # Newer upstream explicitly initializes this output before the retry loop.
    # Backport that fix so GCC 16 LTO keeps maybe-uninitialized checks enabled.
    replace(tree/'libraries/libstratosphere/source/hos/hos_version_api.cpp',
            '            exosphere::ApiInfo info;',
            '            exosphere::ApiInfo info = exosphere::ApiInfo{ util::BitPack64{0} };')


def adapt_hoc_results(tree):
    # R_DISCARD was introduced after 1.9.5; preserve its exact upstream expansion.
    for name, count in [('pcv/pcv.cpp', 1), ('ptm/ptm.cpp', 2), ('oc_log.cpp', 4)]:
        path=tree/'stratosphere/loader/source/oc'/name
        text=path.read_text()
        assert text.count('R_DISCARD(')==count
        path.write_text(text.replace('R_DISCARD(', 'static_cast<void>('))


def add_hoc(tree):
    patch = OLD/'source/atmosphere-hoc-fxtauto.patch'
    assert sha(patch) == OLD_PATCH_SHA
    run('git', '-C', tree, 'apply', '--include=stratosphere/loader/source/oc/*',
        '--include=stratosphere/loader/loader.json', patch)
    adapt_hoc_results(tree)
    path = tree/'stratosphere/loader/source/ldr_process_creation.cpp'
    replace(path, '#include "ldr_ro_manager.hpp"', '#include "ldr_ro_manager.hpp"\n#include "oc/oc_loader.hpp"')
    replace(path, '        NsoHeader g_nso_headers[Nso_Count];',
            '        NsoHeader g_nso_headers[Nso_Count];\n\n        bool g_is_pcv;\n        bool g_is_ptm;')
    replace(path, '            /* If we have data to validate, validate it. */',
            '            g_is_pcv = meta->aci->program_id == ncm::SystemProgramId::Pcv;\n'
            '            g_is_ptm = meta->aci->program_id == ncm::SystemProgramId::Ptm;\n\n'
            '            /* If we have data to validate, validate it. */')
    replace(path, '                LocateAndApplyIpsPatchesToModule(nso_header->module_id, map_address, nso_size);',
            '                LocateAndApplyIpsPatchesToModule(nso_header->module_id, map_address, nso_size);\n'
            '                if (g_is_pcv) hoc::pcv::Patch(map_address, nso_size);\n'
            '                if (g_is_ptm) hoc::ptm::Patch(map_address, nso_size);')


def artifact(tree, target, name):
    paths = list((tree/target/'out').glob('*/release/'+name))
    assert len(paths) == 1, (target, name, paths)
    return paths[0]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['tree', 'output', 'libnx', 'hactool']:
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--jobs', type=int, default=4)
    p.add_argument('--resume-prepared', action='store_true', help='Resume a hash-verified prepared tree after build-script-only changes')
    a = p.parse_args(); tree=a.tree.resolve(); out=a.output.resolve(); nx=a.libnx.resolve()
    assert git(nx, 'rev-parse', 'HEAD').decode().strip() == LIBNX_REVISION
    assert not git(nx, 'status', '--porcelain').strip()
    assert git(a.hactool.parent, '-c', 'safe.directory='+str(a.hactool.parent), 'rev-parse', 'HEAD').decode().strip() == HAC_REVISION
    out.mkdir(parents=True, exist_ok=True)
    stamp=out/'prepared.json'
    if not stamp.exists():
        prepare(tree)
        run('git', '-C', tree, 'add', '-N', '.')
        patch=git(tree, 'diff', '--binary', 'HEAD')
        (out/'atmosphere-1.9.5-standard.patch').write_bytes(patch)
        stamp.write_text(json.dumps(dict(revision=REVISION, builder_sha256=sha(Path(__file__)),
            patch_sha256=hashlib.sha256(patch).hexdigest()), indent=2)+'\n')
    prepared=json.loads(stamp.read_text())
    assert prepared['builder_sha256'] == sha(Path(__file__)) or a.resume_prepared, 'Builder changed; use a fresh checkout or --resume-prepared'
    assert git(tree, 'rev-parse', 'HEAD').decode().strip() == REVISION
    hoc_stamp=out/'hoc-prepared.json'
    expected=json.loads(hoc_stamp.read_text())['patch_sha256'] if hoc_stamp.exists() else prepared['patch_sha256']
    assert hashlib.sha256(git(tree, 'diff', '--binary', 'HEAD')).hexdigest() == expected
    env=dict(os.environ, DEVKITPRO='/opt/devkitpro', DEVKITA64='/opt/devkitpro/devkitA64',
             DEVKITARM='/opt/devkitpro/devkitARM', LIBNX=str(nx/'nx'), TMPDIR=str(out))
    env['CPLUS_INCLUDE_PATH']=env['C_INCLUDE_PATH']=str(nx/'nx/external/bsd/include')
    base_cxx=next(line.split(':=',1)[1].strip() for line in
                  (tree/'libraries/config/common.mk').read_text().splitlines()
                  if line.startswith('export ATMOSPHERE_CXXFLAGS :='))
    def build(target, log_name):
        print('Building '+log_name, flush=True)
        with (out/(log_name+'.log')).open('w') as log:
            run('make', '-s', '-C', tree/target, '-j'+str(a.jobs),
                'ATMOSPHERE_CXXFLAGS='+base_cxx+' '+COMPILER_COMPAT,
                env=env, stdout=log, stderr=subprocess.STDOUT)
    if not hoc_stamp.exists():
        build('mesosphere', 'kernel')
        shutil.copy2(artifact(tree, 'mesosphere', 'mesosphere.bin'), out/'mesosphere.bin')
        build('stratosphere/loader', 'loader-standard')
        kip=artifact(tree, 'stratosphere/loader', 'loader.kip')
        symbols=subprocess.check_output(['/opt/devkitpro/devkitA64/bin/aarch64-none-elf-nm', '-C',
                                        str(kip.with_suffix('.elf'))]).decode()
        assert 'ams::ldr::hoc::' not in symbols
        assert not git(tree, 'diff', '--', 'stratosphere/loader/loader.json').strip()
        shutil.copy2(kip, out/'loader-stock.kip')
        add_hoc(tree)
        run('git', '-C', tree, 'add', '-N', '.')
        patch=git(tree, 'diff', '--binary', 'HEAD')
        (out/'atmosphere-1.9.5-hoc.patch').write_bytes(patch)
        hoc_stamp.write_text(json.dumps(dict(patch_sha256=hashlib.sha256(patch).hexdigest()), indent=2)+'\n')
    build('stratosphere/loader', 'loader-hoc')
    run(a.hactool, '-t', 'kip1', '--uncompressed='+str(out/'loader-hoc.kip'),
        artifact(tree, 'stratosphere/loader', 'loader.kip'), stdout=subprocess.DEVNULL)
    old=json.loads((OLD/'build.json').read_text())
    data=(out/'loader-hoc.kip').read_bytes(); at=data.index(b'CUST', 256)
    assert data.find(b'CUST', at+4) == -1 and not data[31]&7
    size=old['hoc_settings_bytes']; defaults=(OLD/'loader-hoc.kip').read_bytes()
    assert data[at:at+size] == defaults[old['hoc_settings_output_offset']:old['hoc_settings_output_offset']+size]
    assert hashlib.sha256(data[at:at+size]).hexdigest() == old['hoc_settings_sha256']
    for name in ['loader-stock.kip', 'loader-hoc.kip']:
        d=(out/name).read_bytes()
        assert d[:4] == b'KIP1' and int.from_bytes(d[16:24], 'little') == 0x0100000000000001
    receipt=dict(version='1.3.0', atmosphere='1.9.5', revision=REVISION,
        abi='fxtmem-v1', extension='fxtauto-v1', reference_hos='20.5.0',
        hoc='2.5.1', hoc_port=True, hoc_configuration='official-release-default',
        hardware_tested=False, title_id_allowlist=None, stock_hoc_symbols=False,
        hoc_settings_bytes=size, hoc_settings_output_offset=at, hoc_settings_sha256=old['hoc_settings_sha256'],
        builder_sha256=sha(Path(__file__)), libnx_revision=LIBNX_REVISION,
        compiler_compat_flags=COMPILER_COMPAT,
        libnx_archive_sha256=sha(nx/'nx/lib/libnx.a'),
        files={n:sha(out/n) for n in ['mesosphere.bin','loader-stock.kip','loader-hoc.kip']},
        patches={n:sha(out/n) for n in ['atmosphere-1.9.5-standard.patch','atmosphere-1.9.5-hoc.patch']})
    (out/'build.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print('Built 1.9.5 kernel and both loaders; HOC defaults unchanged. Hardware validation pending.', flush=True)


if __name__ == '__main__': main()
