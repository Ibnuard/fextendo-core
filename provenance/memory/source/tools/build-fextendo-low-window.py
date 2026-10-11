"""Build the experimental, descriptor-selected AMS/HOC pair in an isolated tree.

Run under WSL. Reuses pinned Git objects/downloads, never edits the reference
Sleeping Dogs workspace, installed boot files, or any game's runtime.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import zipfile
from fextendo_low_window import ROOT, SOURCE, AMS_REV, HOC_REV, apply, apply_loader

HOC_RELEASE = 'a6f1732e1d96577a8009d47c9b98e018080f3fe7'
BUILD = Path('out/nintendo_nx_arm64_armv8a/release')


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write_json(p, value): p.write_text(json.dumps(value, indent=2) + '\n')
def run(*args, **kw): return subprocess.run(list(map(str, args)), check=True, **kw)
def git(path, *args, capture=False):
    command = ['git', '-c', 'safe.directory=' + str(path), '-C', str(path), *args]
    if capture: return subprocess.check_output(command, text=True).strip()
    return run(*command)


def clone(source, dest, revision):
    if git(source, 'rev-parse', 'HEAD', capture=True) != revision:
        raise RuntimeError('Unreviewed source revision: ' + str(source))
    run('git', '-c', 'safe.directory=' + str(source), 'clone', '--no-hardlinks', source, dest,
        stdout=subprocess.DEVNULL)
    git(dest, 'checkout', '--detach', revision)


def export_patch(tree, output):
    git(tree, 'add', '-N', '.')
    output.write_bytes(subprocess.check_output(['git', '-C', str(tree), 'diff', '--binary', 'HEAD']))
    paths = git(tree, 'diff', '--name-only', 'HEAD', capture=True).splitlines()
    return {p: sha(tree / p) for p in paths if (tree / p).is_file()}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--cache', type=Path, default=Path('/home/blekjek/sleepingdogs-low-window-v1'))
    p.add_argument('--hoc', type=Path, default=Path('/mnt/d/Dev/Personal/UNDANGAN/hoc.kip'))
    p.add_argument('--output', type=Path, default=ROOT / 'dist/fextendo-low-window-v1/boot')
    p.add_argument('--jobs', type=int, default=4)
    p.add_argument('--prepare-only', action='store_true')
    a = p.parse_args()
    work, cache, out = a.work.resolve(), a.cache.resolve(), a.output.resolve()
    work.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    base_patch = ROOT / 'patches/low-window/autorun-low-window.patch'
    if sha(base_patch) != '51534dc567602d62fbfd678945d843825d5d55c984f612320a0a2683ae196b69':
        raise RuntimeError('Unreviewed Autorun low-window patch')
    inputs = {str(f.relative_to(ROOT)): sha(f) for f in [
        Path(__file__).resolve(), ROOT / 'tools/fextendo_low_window.py', base_patch,
        SOURCE / 'fextendo_memory_abi.hpp', SOURCE / 'ldr_fextendo_memory.inc']}
    stamp = work / 'prepared.json'
    ams, hocams, hoc = work / 'atmosphere', work / 'atmosphere-hoc', work / 'hoc'
    if not stamp.exists():
        if any(t.exists() for t in (ams, hocams, hoc)):
            raise RuntimeError('Incomplete preparation: choose a fresh isolated work directory')
        clone(cache / 'atmosphere', ams, AMS_REV)
        git(ams, 'apply', '--check', str(base_patch))
        git(ams, 'apply', str(base_patch))
        apply(ams)
        clone(cache / 'hoc', hoc, HOC_REV)
        version_patch = cache / 'hoc-2.5.1-version.patch'
        if sha(version_patch) != '6158023d25bd95fbb9c9979cf53b34acd1e6c9e0840e40ae94cd26b648fe55aa':
            raise RuntimeError('Unreviewed HOC version patch')
        # This same pinned version patch is bundled alongside the generated diff.
        shutil.copy2(version_patch, out / version_patch.name)
        git(hoc, 'apply', '--check', str(version_patch))
        git(hoc, 'apply', str(version_patch))
        clone(cache / 'atmosphere', hocams, AMS_REV)
        git(hocams, 'apply', str(base_patch))
        apply(hocams)
        shutil.copytree(hoc / 'Source/Atmosphere/stratosphere/loader', hocams / 'stratosphere/loader', dirs_exist_ok=True)
        apply_loader(hocams, hoc=True)
        changed = {tree.name: export_patch(tree, out / (tree.name + '-fextendo.patch')) for tree in (ams, hocams)}
        write_json(stamp, {'inputs': inputs, 'changes': changed, 'hoc_version_patch_sha256': sha(version_patch)})
    prepared = json.loads(stamp.read_text())
    if prepared['inputs'] != inputs:
        raise RuntimeError('Overlay inputs changed: choose a fresh work directory')
    for tree, files in prepared['changes'].items():
        for name, digest in files.items():
            if sha(work / tree / name) != digest: raise RuntimeError('Prepared source changed: ' + name)
    if a.prepare_only:
        print('Prepared descriptor-selected kernel and both loader sources.', flush=True)
        return
    env = dict(os.environ, DEVKITPRO='/opt/devkitpro', DEVKITA64='/opt/devkitpro/devkitA64',
               DEVKITARM='/opt/devkitpro/devkitARM', TMPDIR=str(work), TMP=str(work), TEMP=str(work))
    for tree, target in ((ams, 'mesosphere'), (ams, 'stratosphere/loader'), (hocams, 'stratosphere/loader')):
        logpath = work / ('build-' + tree.name + '-' + target.replace('/', '-') + '.log')
        print('Building', tree.name, target, '->', logpath, flush=True)
        with logpath.open('w') as log:
            run('make', '-s', '-C', tree / target, '-j' + str(a.jobs), env=env, stdout=log, stderr=subprocess.STDOUT)
    hactool = cache / 'hactool'
    if git(hactool, 'rev-parse', 'HEAD', capture=True) != '3121a5bf08cd81d3a99719feb2cab3b60767afd5':
        raise RuntimeError('Unreviewed hactool')
    kip = out / 'loader-hoc.kip'
    run(hactool / 'hactool', '-t', 'kip1', '--uncompressed=' + str(kip),
        hocams / 'stratosphere/loader' / BUILD / 'loader.kip', stdout=subprocess.DEVNULL)
    data = bytearray(kip.read_bytes())
    if data[:4] != b'KIP1' or data[31] & 7: raise RuntimeError('Expected an uncompressed HOC KIP')
    symbols = subprocess.check_output(['/opt/devkitpro/devkitA64/bin/aarch64-none-elf-nm', '-S', '--demangle',
        str(hocams / 'stratosphere/loader' / BUILD / 'loader.elf')], text=True)
    sizes = re.findall(r'^[0-9a-fA-F]+\s+([0-9a-fA-F]+)\s+\S\s+ams::ldr::hoc::C$', symbols, re.M)
    if len(sizes) != 1: raise RuntimeError('Ambiguous HOC settings ABI')
    size = int(sizes[0], 16)
    off = data.find(b'CUST', 256)
    if off < 256 or data.find(b'CUST', off + 4) != -1: raise RuntimeError('Ambiguous HOC CUST')
    release = cache / 'hoc-2.5.1.zip'
    if sha(release) != '48a57eef49032cbae615074676df4a5fb017aff40be3f45734a158d5b19ffa00':
        raise RuntimeError('Unexpected HOC release archive')
    with zipfile.ZipFile(release) as z: original = z.read('atmosphere/kips/hoc.kip')
    user = a.hoc.read_bytes()
    roff, uoff = original.find(b'CUST', 256), user.find(b'CUST', 256)
    if not (roff == uoff >= 256 and len(original) == len(user) and
            user[:uoff + 12] == original[:roff + 12] and user[uoff + size:] == original[roff + size:] and
            data[off:off + size] == original[roff:roff + size]):
        raise RuntimeError('HOC source/settings do not match the reviewed release ABI')
    data[off:off + size] = user[uoff:uoff + size]
    kip.write_bytes(data)
    shutil.copy2(ams / 'mesosphere' / BUILD / 'mesosphere.bin', out / 'mesosphere.bin')
    shutil.copy2(ams / 'stratosphere/loader' / BUILD / 'loader.kip', out / 'loader-stock.kip')
    shutil.copy2(ams / 'LICENSE', out / 'LICENSE.Atmosphere')
    shutil.copy2(hoc / 'LICENSE', out / 'LICENSE.HOC')
    write_json(out / 'build.json', {'abi': 'fxtmem-v1', 'ams_revision': AMS_REV, 'hoc_revision': HOC_REV,
        'hoc_release': HOC_RELEASE, 'title_id_allowlist': None, 'hardware_tested': False,
        'hos_reference': '22.5.0', 'ams': '1.11.2', 'hoc': '2.5.1',
        'hoc_input_sha256': sha(a.hoc), 'hoc_settings_sha256': hashlib.sha256(user[uoff:uoff + size]).hexdigest(),
        'hoc_settings_bytes': size, 'hoc_settings_original_offset': uoff, 'hoc_settings_output_offset': off,
        'prepared': prepared, 'files': {f.name: sha(f) for f in sorted(out.iterdir()) if f.is_file() and f.name != 'build.json'}})
    print('Built generic pair; preserved HOC settings byte for byte. Hardware validation pending.', flush=True)


if __name__ == '__main__': main()
