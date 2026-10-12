"""Rebuild the 1.12.0 kernel/loader pair from pinned sources under Linux/WSL.

Keep the 1.11.2 artifacts immutable. Reuse its reviewed HOC 2.5.1 OC code and
official default settings, but retain the NEW upstream loader and kernel.
This is a FEXTendo port, not an upstream HOC certification for new firmware.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REVISION = '28d6a2e11f2640077bbb8a9fbd463d3fa12b6984'
LIBNX_REVISION = 'feebd026ca0f5dcc2119f46ad8e0d16ad3dd4973'
OLD = ROOT / 'provenance/memory-auto-v1.1.0'
OLD_PATCH_SHA = 'b75bcaa73aea01fa442f64c702528efc1a2f26628f66bcb9b379d045f17899e3'
BUILD = Path('out/nintendo_nx_arm64_armv8a/release')


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def replace(path, old, new):
    text = path.read_text()
    if text.count(old) != 1:
        raise ValueError('Upstream anchor changed: ' + str(path) + ': ' + old[:100])
    path.write_text(text.replace(old, new, 1))


def run(*args, **kwargs):
    return subprocess.run(list(map(str, args)), check=True, **kwargs)


def git(tree, *args):
    return subprocess.check_output(['git', '-C', str(tree), *args])


def prepare(tree):
    assert git(tree, 'rev-parse', 'HEAD').decode().strip() == REVISION
    assert not git(tree, 'status', '--porcelain').strip(), 'Use a clean, pinned source tree'
    svc = tree / 'libraries/libvapours/include/vapours/svc'
    abi = OLD / 'source/src/experimental/low_window'
    shutil.copy2(abi / 'fextendo_memory_abi.hpp', svc / 'svc_fextendo_memory.hpp')
    header = svc / 'svc_types_common.hpp'
    replace(header, '#include <vapours/svc/svc_common.hpp>',
            '#include <vapours/svc/svc_common.hpp>\n#include <vapours/svc/svc_fextendo_memory.hpp>')
    replace(header, '        /* Mask of all flags. */\n        CreateProcessParameterFlag_All',
            '        /* Private FEXTendo ABI; never an NPDM flag. */\n'
            '        CreateProcessParameterFlag_FextendoLowWindow = fextendo::RequestFlag,\n\n'
            '        /* Mask of all flags. */\n        CreateProcessParameterFlag_All')
    replace(header, '                                CreateProcessParameterFlag_EnableShadowStack,',
            '                                CreateProcessParameterFlag_EnableShadowStack |\n'
            '                                CreateProcessParameterFlag_FextendoLowWindow,')
    replace(header, '    /* Debug types. */', '''    static_assert(CreateProcessParameterFlag_64Bit == 1);
    static_assert(CreateProcessParameterFlag_AddressSpaceMask == 0x0e);
    static_assert(CreateProcessParameterFlag_AddressSpace32BitNoReserved == 4);
    static_assert(CreateProcessParameterFlag_AddressSpace64Bit39 == 6);
    static_assert(CreateProcessParameterFlag_AddressSpace64Bit42 == 8);
    static_assert(CreateProcessParameterFlag_IsApplication == 0x40);
    static_assert(CreateProcessParameterFlag_PoolPartitionMask == 0x780);
    static_assert(CreateProcessParameterFlag_PoolPartitionApplication == 0);
    static_assert(CreateProcessParameterFlag_EnableAddressSanitizer == 0x2000);
    static_assert(CreateProcessParameterFlag_EnableShadowStack == 0x20000);
    static_assert((CreateProcessParameterFlag_All & ~CreateProcessParameterFlag_FextendoLowWindow) == 0x23fff);

    /* Debug types. */''')
    kernel = tree / 'libraries/libmesosphere/source/svc/kern_svc_process.cpp'
    replace(kernel, '            /* Validate that 64-bit process is okay. */', '''            /* Enforce the descriptor contract independently of the loader. */
            if (ams::svc::fextendo::Requested(params.flags)) {
                R_UNLESS(ams::svc::fextendo::CompatibleFlags(params.flags), svc::ResultInvalidCombination());
                R_UNLESS(params.code_address >= ams::svc::fextendo::NativeStart, svc::ResultInvalidAddress());
            }

            /* Validate that 64-bit process is okay. */''')
    # Flags already reach the page table. Do not change all internal function
    # signatures or the ordinary 32/36/39/42-bit layouts to pass another bool.
    page = tree / 'libraries/libmesosphere/source/kern_k_page_table_base.cpp'
    replace(page, '            process_code_start                    = util::AlignDown(GetInteger(code_address), RegionAlignment);', '''            if (ams::svc::fextendo::Requested(flags)) {
                R_UNLESS(address_space_width == 39 && ams::svc::fextendo::CompatibleFlags(flags), svc::ResultInvalidCombination());
                R_UNLESS(code_address >= ams::svc::fextendo::NativeStart, svc::ResultInvalidAddress());
                m_code_region_start       = ams::svc::fextendo::NativeStart;
                m_alias_code_region_start = ams::svc::AddressSmallMap32Start;
            }

            process_code_start                    = util::AlignDown(GetInteger(code_address), RegionAlignment);''')
    loader = tree / 'stratosphere/loader/source'
    (loader / 'ldr_fextendo_memory.inc').write_text((abi / 'ldr_fextendo_memory.inc').read_text().replace(
        'CreateProcessFlag_FextendoLowWindow', 'CreateProcessParameterFlag_FextendoLowWindow'))
    path = loader / 'ldr_process_creation.cpp'
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

    patch = OLD / 'source/atmosphere-hoc-fxtauto.patch'
    assert sha(patch) == OLD_PATCH_SHA, 'Historical HOC source changed'
    # Only bring over OC sources and the PCV register mapping capability.
    # In particular, NEVER overlay the old ldr_process_creation.cpp.
    run('git', '-C', tree, 'apply', '--include=stratosphere/loader/source/oc/*',
        '--include=stratosphere/loader/loader.json', patch)
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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tree', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--hactool', type=Path, required=True)
    p.add_argument('--libnx', type=Path, required=True, help='Built libnx source checkout, installed globally nowhere')
    p.add_argument('--jobs', type=int, default=4)
    p.add_argument('--prepare-only', action='store_true')
    p.add_argument('--resume-prepared', action='store_true', help='Resume build/report fixes only if the saved prepare() source is identical')
    args = p.parse_args()
    tree, out = args.tree.resolve(), args.output.resolve()
    libnx=args.libnx.resolve()
    assert git(libnx,'rev-parse','HEAD').decode().strip()==LIBNX_REVISION
    assert not git(libnx,'status','--porcelain').strip(), 'libnx source must be unmodified'
    assert (libnx/'nx/lib/libnx.a').is_file(), 'Build the pinned libnx first'
    out.mkdir(parents=True, exist_ok=True)
    stamp = out / 'prepared.json'
    if not stamp.exists():
        prepare(tree)
        run('git', '-C', tree, 'add', '-N', '.')
        patch = out / 'atmosphere-1.12.0-fextendo-hoc.patch'
        patch.write_bytes(git(tree, 'diff', '--binary', 'HEAD'))
        paths = git(tree, 'diff', '--name-only', 'HEAD').decode().splitlines()
        stamp.write_text(json.dumps({'revision': REVISION, 'builder_sha256': sha(Path(__file__)),
            'patch_sha256': sha(patch), 'files': {n: sha(tree/n) for n in paths}}, indent=2)+'\n')
        shutil.copy2(Path(__file__),out/'preparation-builder.py')
    prepared = json.loads(stamp.read_text())
    if prepared['builder_sha256'] != sha(Path(__file__)):
        assert args.resume_prepared, 'Builder changed; use a fresh tree or explicitly resume unchanged preparation'
        saved=out/'preparation-builder.py'
        assert sha(saved)==prepared['builder_sha256']
        def preparation(path):
            text=path.read_text()
            return ast.get_source_segment(text,next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='prepare'))
        assert preparation(saved)==preparation(Path(__file__)), 'Overlay changed; use a fresh tree'
    assert git(tree, 'rev-parse', 'HEAD').decode().strip() == REVISION
    for name, digest in prepared['files'].items():
        assert sha(tree / name) == digest, 'Prepared source changed: '+name
    assert hashlib.sha256(git(tree,'diff','--binary','HEAD')).hexdigest()==prepared['patch_sha256']
    if args.prepare_only:
        print('Prepared pinned Atmosphere 1.12.0 + fxtmem/fxtauto + HOC defaults.', flush=True)
        return
    env = dict(os.environ, DEVKITPRO='/opt/devkitpro', DEVKITA64='/opt/devkitpro/devkitA64',
               DEVKITARM='/opt/devkitpro/devkitARM', LIBNX=str(libnx/'nx'), TMPDIR=str(out), TMP=str(out), TEMP=str(out))
    # A source libnx checkout keeps BSD headers separate from nx/include.
    # Retain installed portlibs (e.g. JPEG) while supplying that pinned header set.
    env['CPLUS_INCLUDE_PATH']=env['C_INCLUDE_PATH']=str(libnx/'nx/external/bsd/include')
    for target in ['mesosphere', 'stratosphere/loader']:
        print('Building '+target, flush=True)
        with (out / (target.replace('/', '-')+'.log')).open('w') as log:
            run('make', '-s', '-C', tree / target, '-j'+str(args.jobs), env=env, stdout=log, stderr=subprocess.STDOUT)
    kip = tree / 'stratosphere/loader' / BUILD / 'loader.kip'
    run(args.hactool, '-t', 'kip1', '--uncompressed='+str(out/'loader-hoc.kip'), kip, stdout=subprocess.DEVNULL)
    data = (out/'loader-hoc.kip').read_bytes()
    assert data[:4] == b'KIP1' and not data[31] & 7
    receipt = json.loads((OLD/'build.json').read_text())
    old = (ROOT/'romfs/boot/loader-hoc-1.11.2-auto-v1.1.0.kip').read_bytes()
    assert hashlib.sha256(old).hexdigest() == receipt['files']['loader-hoc.kip']
    at = data.index(b'CUST', 256)
    assert data.find(b'CUST', at+4) == -1
    size, offset = receipt['hoc_settings_bytes'], receipt['hoc_settings_output_offset']
    settings = data[at:at+size]
    assert settings == old[offset:offset+size]
    assert hashlib.sha256(settings).hexdigest() == receipt['hoc_settings_sha256']
    shutil.copy2(tree/'mesosphere'/BUILD/'mesosphere.bin', out/'mesosphere.bin')
    report = dict(version='1.2.0', abi='fxtmem-v1', extension='fxtauto-v1',
        atmosphere='1.12.0', revision=REVISION, hoc='2.5.1', hoc_port=True,
        hoc_configuration='official-release-default', hardware_tested=False,
        reference_hos='23.0.0', title_id_allowlist=None,
        hoc_settings_sha256=receipt['hoc_settings_sha256'], hoc_settings_bytes=size,
        hoc_settings_output_offset=at, prepared=prepared, build_builder_sha256=sha(Path(__file__)),
        libnx_revision=LIBNX_REVISION, libnx_archive_sha256=sha(libnx/'nx/lib/libnx.a'),
        files={n:sha(out/n) for n in ['mesosphere.bin','loader-hoc.kip']},
        elfs={'kernel':sha(tree/'mesosphere/kernel'/BUILD/'kernel.elf'),
              'loader':sha(tree/'stratosphere/loader'/BUILD/'loader.elf')})
    (out/'build.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Built 1.12.0 pair; official HOC settings byte-identical. Device validation pending.', flush=True)


if __name__ == '__main__':
    main()
