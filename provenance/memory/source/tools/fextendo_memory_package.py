"""Build a copy-ready FEXTendo boot environment from the hardware-tested pair.

The published HOC archive is mandatory: never distribute somebody's CUST tuning
by assuming that a local hoc.kip is the official default. No SD writes, downloads,
kernel rebuild, game runtime changes, or installer side effects occur here.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import struct
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'release/memory'
SD_KERNEL = 'atmosphere/fextendo/memory-v1/mesosphere.bin'
SD_LOADER = 'atmosphere/fextendo/memory-v1/loader.kip'
SD_INI = 'bootloader/ini/fextendo-memory.ini'
SD_ICON = 'bootloader/res/fextendo-memory.bmp'
SD_LOGO = 'bootloader/res/fextendo-boot.bmp'
SD_FILES = {SD_KERNEL, SD_LOADER, SD_INI, SD_ICON, SD_LOGO}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def checked_file(path, expected):
    data = path.read_bytes()
    require(digest(data) == expected, f'SHA256 mismatch: {path.name}')
    return data


def parse_entry(text):
    section = None
    entries = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('[') and line.endswith(']'):
            require(section is None, 'Only the FEXTendo boot entry is allowed')
            section = line[1:-1]
            continue
        require(section is not None and '=' in line, 'Invalid boot configuration line')
        key, value = line.split('=', 1)
        require(key not in entries, f'Duplicate boot key: {key}')
        entries[key] = value
    expected = {'id': 'fxtmem1', 'pkg3': 'atmosphere/package3',
                'kernel': SD_KERNEL, 'kip1': SD_LOADER, 'emummcforce': '1',
                'icon': SD_ICON, 'logopath': SD_LOGO}
    require(section == 'FEXTendo (emuMMC)' and entries == expected,
            'Unexpected boot entry (MMC/loader/payload overrides are not allowed)')
    keys = list(entries)
    require(keys.index('pkg3') < keys.index('kernel') < keys.index('kip1'),
            'Load package3 before overriding its kernel and Loader')
    return entries


def validate_bmp(data, size, opaque=False):
    require(len(data) >= 54 and data[:2] == b'BM', 'Invalid BMP header')
    total, _, _, offset = struct.unpack_from('<IHHI', data, 2)
    info, width, height, planes, bpp, compression, length = struct.unpack_from('<IiiHHII', data, 14)
    require((info, planes, bpp, compression, offset) == (40, 1, 32, 0, 54),
            'Hekate needs uncompressed 32-bit BMP with BGRA pixels')
    require((width, height) == size and total == len(data) == 54 + width * height * 4
            and length == width * height * 4, 'Incorrect BMP dimensions or payload length')
    alpha = data[57::4]
    require(max(alpha) == 255, 'Invisible BMP alpha')
    if opaque:
        require(min(alpha) == 255, 'Boot logo must be opaque')


def validate_kip(data):
    require(len(data) >= 256 and data[:4] == b'KIP1', 'Invalid KIP')
    require(data[4:16].rstrip(b'\0') == b'Loader', 'Expected Loader KIP')
    require(struct.unpack_from('<Q', data, 16)[0] == 0x0100000000000001,
            'Loader program ID mismatch')
    require(data[31] & 7 == 0, 'Expected the tested uncompressed HOC Loader')
    payload_length = sum(struct.unpack_from('<I', data, 0x20 + index * 16 + 8)[0] for index in range(6))
    require(len(data) == 256 + payload_length, 'Truncated KIP segments')


def validate_hoc(patched, official, lock):
    validate_kip(patched)
    validate_kip(official)
    start = lock['hoc_patched_settings_offset']
    old = lock['hoc_official_settings_offset']
    size = lock['hoc_settings_length']
    require(patched.find(b'CUST', 256) == start and official.find(b'CUST', 256) == old,
            'HOC settings layout changed')
    settings = official[old:old + size]
    require(len(settings) == size and digest(settings) == lock['hoc_settings_sha256'],
            'Unexpected official HOC settings')
    require(patched[start:start + size] == settings,
            'Private OC settings detected; distribute only the pinned official defaults')


def evidence_receipt(folder, lock):
    results = {}
    for tag, expected in lock['hardware_probe_sha256'].items():
        data = checked_file(folder / (tag + '.log'), expected)
        text = data.decode('utf-8')
        require('probe-r2' in text and '[SUMMARY] PASS' in text, f'{tag}: device probe did not PASS')
        floor = '0x8000000' if tag == 'control' else '0x200000'
        require('aslr_base=' + floor + ' ' in text and 'execute_and_backpatch=PASS' in text,
                f'{tag}: missing layout/JIT evidence')
        results[tag] = {'sha256': expected, 'result': 'PASS'}
    return results


def relative_file(root, rel):
    p = PurePosixPath(rel)
    require(not p.is_absolute() and '\\' not in rel and ':' not in rel
            and all(part not in ('', '.', '..') for part in p.parts), 'Unsafe manifest path')
    path = (root / rel).resolve()
    require(path.is_relative_to(root.resolve()), 'Manifest path leaves package')
    return path


def verify(output):
    manifest = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
    require(manifest['schema'] == 1 and manifest['abi'] == 'fxtmem-v1', 'Unknown manifest')
    declared = manifest['files']
    actual = {p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()}
    require(actual == set(declared) | {'manifest.json', 'SHA256SUMS.txt'}, 'Missing or undeclared package file')
    for rel, item in declared.items():
        data = checked_file(relative_file(output, rel), item['sha256'])
        require(len(data) == item['bytes'], f'Wrong size: {rel}')
    sums = (output / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines()
    require(len(sums) == len(actual) - 1, 'Incomplete checksum list')
    summed = set()
    for line in sums:
        expected, rel = line.split('  ', 1)
        require(rel not in summed and rel != 'SHA256SUMS.txt', 'Duplicate checksum')
        summed.add(rel)
        checked_file(relative_file(output, rel), expected)
    require(summed == actual - {'SHA256SUMS.txt'}, 'Incomplete checksum coverage')
    sd = output / 'SD'
    require({p.relative_to(sd).as_posix() for p in sd.rglob('*') if p.is_file()} == SD_FILES,
            'SD payload must contain only the five owned boot files')
    parse_entry((sd / SD_INI).read_text(encoding='ascii'))
    validate_kip((sd / SD_LOADER).read_bytes())
    lock = json.loads((output / 'provenance/boot-lock.json').read_text())
    checked_file(sd / SD_KERNEL, lock['boot_files']['mesosphere.bin'])
    checked_file(sd / SD_LOADER, lock['boot_files']['loader-hoc.kip'])
    validate_bmp((sd / SD_ICON).read_bytes(), (192, 192))
    validate_bmp((sd / SD_LOGO).read_bytes(), (400, 960), opaque=True)
    return manifest


def assemble(baseline, archive, evidence, output):
    from fextendo_boot_art import render
    lock = json.loads((CONFIG / 'boot-lock.json').read_text())
    build = json.loads((baseline / 'boot/build.json').read_text())
    tests = json.loads((baseline / 'validation.json').read_text())
    require(build['abi'] == lock['abi'] and build['ams_revision'] == lock['atmosphere_revision']
            and build['hoc_revision'] == lock['hoc_revision'] and build['title_id_allowlist'] is None,
            'Baseline is not the pinned generic memory build')
    require(tests['status'] == 'PASS' and tests['boot_files'] == build['files'], 'Missing boot validation')
    for name, expected in build['files'].items():
        checked_file(baseline / 'boot' / name, expected)
    for rel, expected in build['prepared']['inputs'].items():
        checked_file(baseline / 'source' / rel, expected)
    boot = {name: checked_file(baseline / 'boot' / name, expected)
            for name, expected in lock['boot_files'].items()}
    checked_file(archive, lock['hoc_archive_sha256'])
    with zipfile.ZipFile(archive) as z:
        official = z.read('atmosphere/kips/hoc.kip')
    require(digest(official) == lock['hoc_official_kip_sha256'], 'Official HOC KIP differs')
    validate_hoc(boot['loader-hoc.kip'], official, lock)
    hardware = evidence_receipt(evidence, lock)
    entry = (CONFIG / 'fextendo-memory.ini').read_text(encoding='ascii')
    parse_entry(entry)
    output = output.resolve()
    require(not output.exists(), 'Output already exists; use a fresh directory (no automatic delete)')
    output.mkdir(parents=True)
    sd = output / 'SD'
    for rel, data in ((SD_KERNEL, boot['mesosphere.bin']), (SD_LOADER, boot['loader-hoc.kip']),
                      (SD_INI, entry.encode('ascii'))):
        dest = sd / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    art = output / 'artwork'
    render(art)
    (sd / SD_ICON).parent.mkdir(parents=True, exist_ok=True)
    for name in ('fextendo-memory.bmp', 'fextendo-boot.bmp'):
        shutil.copy2(art / name, sd / 'bootloader/res' / name)
        (art / name).unlink()  # generated duplicate only; keep SD payload + previews
    # Retain the exact source diffs that produced these binaries, not a diff of
    # the currently checked-out game branch. No local paths or custom INIs copied.
    provenance = output / 'provenance'
    provenance.mkdir()
    shutil.copy2(CONFIG / 'boot-lock.json', provenance / 'boot-lock.json')
    shutil.copy2(baseline / 'boot/build.json', provenance / 'original-build.json')
    shutil.copy2(baseline / 'validation.json', provenance / 'original-validation.json')
    (provenance / 'device-results.json').write_text(json.dumps(hardware, indent=2) + '\n')
    source = output / 'source'
    source.mkdir()
    for name in ('atmosphere-fextendo.patch', 'atmosphere-hoc-fextendo.patch', 'hoc-2.5.1-version.patch'):
        shutil.copy2(baseline / 'boot' / name, source / name)
    for rel in build['prepared']['inputs']:
        dest = source / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(baseline / 'source' / rel, dest)
    for rel in ('tools/fextendo_memory_package.py', 'tools/fextendo_boot_art.py',
                'tests/test_fextendo_memory_package.py', 'docs/FEXTENDO-MEMORY-PACKAGE.md',
                'assets/fextendo-memory/README.md', 'assets/fextendo-memory/icon.svg',
                'assets/fextendo-v2/gamepad-flat.png', 'assets/fextendo-v2/wordmark.png',
                'assets/fextendo-v2/GENERATION.md',
                'assets/fonts/Inter/Inter.ttf', 'release/memory/fextendo-memory.ini',
                'release/memory/boot-lock.json', 'release/memory/Check-Package.ps1',
                'release/memory/INSTALL.txt'):
        dest = source / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dest)
    licenses = output / 'licenses'
    licenses.mkdir()
    for name in ('LICENSE.Atmosphere', 'LICENSE.HOC'):
        shutil.copy2(baseline / 'boot' / name, licenses / name)
    shutil.copy2(ROOT / 'assets/fonts/Inter/OFL.txt', licenses / 'Inter-OFL.txt')
    shutil.copy2(ROOT / 'assets/fextendo-memory/README.md', licenses / 'Artwork.txt')
    shutil.copy2(CONFIG / 'INSTALL.txt', output / 'INSTALL.txt')
    shutil.copy2(CONFIG / 'Check-Package.ps1', output / 'Check-Package.ps1')
    shutil.copy2(ROOT / 'docs/FEXTENDO-MEMORY-PACKAGE.md', output / 'README.md')
    manifest = {'schema': 1, 'name': 'FEXTendo Memory', 'version': lock['version'], 'abi': lock['abi'],
        'atmosphere': lock['atmosphere_version'], 'hos_reference': lock['hos_reference'],
        'hoc': lock['hoc_version'], 'hoc_configuration': 'official-release-default',
        'boot_entry': 'FEXTendo (emuMMC)', 'boot_id': 'fxtmem1', 'initial_reboot_required': True,
        'artwork': 'Original FEXTendo launcher gamepad and wordmark',
        'per_game_kernel_updates': False, 'physical_heap_claim': 'No physical RAM increase',
        'hardware_validation': {'kernel_loader_pair': 'PASS probe-r2',
            'repackaged_entry_and_artwork': 'Pending on-device check',
            'game_compatibility': 'Test each runtime separately'},
        'external_requirements': ['atmosphere/package3 (1.11.2)', 'enabled emuMMC',
                                  'Hekate/Nyx supporting this HOS and pkg3='],
        'files': {p.relative_to(output).as_posix(): {'bytes': p.stat().st_size, 'sha256': digest(p.read_bytes())}
                  for p in sorted(output.rglob('*')) if p.is_file()}}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    (output / 'SHA256SUMS.txt').write_text(''.join(
        f'{digest(p.read_bytes())}  {p.relative_to(output).as_posix()}\n'
        for p in sorted(output.rglob('*')) if p.is_file()), encoding='ascii')
    verify(output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', type=Path)
    parser.add_argument('--baseline', type=Path, default=ROOT / 'dist/fextendo-low-window-v1')
    parser.add_argument('--hoc-archive', type=Path)
    parser.add_argument('--device-evidence', type=Path,
                        default=ROOT / 'local/fextendo-memory-probe-r2/device-pass')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.verify:
        info = verify(args.verify)
        print(f'PASS: {len(info["files"])} checked package files; five owned SD files')
    else:
        if not (args.hoc_archive and args.output):
            parser.error('--hoc-archive and --output are required')
        print('Created and verified:', assemble(args.baseline, args.hoc_archive, args.device_evidence, args.output))


if __name__ == '__main__':
    main()
