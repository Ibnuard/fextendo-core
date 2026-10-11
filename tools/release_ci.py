"""Validate and publish immutable installer releases consumed by Check update."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

import release

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'Ibnuard/fextendo-core'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def semver(value):
    require(re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', value), 'Invalid version: '+value)
    return tuple(map(int, value.split('.')))


def metadata():
    version = release.VERSION
    semver(version)
    make = re.search(r'^export APP_VERSION := (\S+)$', (ROOT/'Makefile').read_text(), re.M)
    header = re.search(r'AppVersion = "([^"]+)"', (ROOT/'include/core.hpp').read_text())
    require(make and header and make[1] == header[1] == version, 'Makefile, AppVersion and release.VERSION must agree.')
    generated = (ROOT/'include/generated.hpp').read_text()
    require(f'#define FXP_DEFAULT_REPOSITORY "{REPOSITORY}"' in generated, 'Run prepare.py with the official update repository.')
    catalog_path = ROOT/'romfs/catalog.json'
    require(f'#define FXP_CATALOG_HASH "{sha(catalog_path)}"' in generated, 'Stale embedded catalog hash. Run prepare.py.')
    catalog = json.loads(catalog_path.read_text())
    for bundle in catalog['bundles']:
        for kind in ['kernel', 'loader']:
            asset = bundle[kind]
            require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', asset['asset']), 'Unsafe asset name.')
            path = ROOT/'romfs/boot'/asset['asset']
            require(path.stat().st_size == asset['bytes'] and sha(path) == asset['sha256'], 'Boot payload differs from catalog: '+asset['asset'])
    return {'version': version, 'tag': 'v'+version}


def checksums(directory):
    result = {}
    for line in (directory/'SHA256SUMS.txt').read_text().splitlines():
        match = re.fullmatch(r'([a-f0-9]{64})  ([A-Za-z0-9][A-Za-z0-9._-]*)', line)
        require(match is not None, 'Unsafe or malformed checksum entry.')
        digest, name = match.groups()
        path = directory/name
        require(name not in result and not path.is_symlink() and path.is_file(), 'Duplicate or missing release asset: '+name)
        require(sha(path) == digest, 'Release checksum mismatch: '+name)
        result[name] = {'size': path.stat().st_size, 'digest': 'sha256:'+digest}
    result['SHA256SUMS.txt'] = {'size': (directory/'SHA256SUMS.txt').stat().st_size, 'digest': 'sha256:'+sha(directory/'SHA256SUMS.txt')}
    require(set(result) == {p.name for p in directory.iterdir()}, 'Unlisted files in release directory.')
    return result


def verify(directory):
    meta = metadata()
    assets = checksums(directory)
    catalog = json.loads((directory/'fextendo-patch.json').read_text())
    require(catalog == json.loads((ROOT/'romfs/catalog.json').read_text()), 'Release catalog differs from approved source.')
    required = {'FEXTendo-Patch.nro', 'FEXTendo-Patch-source.tar.gz', 'fextendo-patch.json',
                'README.md', 'SHA256SUMS.txt', 'build-receipt.json', 'toolchain.txt'}
    for bundle in catalog['bundles']:
        for kind in ['kernel', 'loader']:
            asset = bundle[kind]
            required.add(asset['asset'])
            require(assets.get(asset['asset']) == {'size': asset['bytes'], 'digest': 'sha256:'+asset['sha256']}, 'Payload is missing or changed: '+asset['asset'])
    require(set(assets) == required, 'Release must contain exactly the catalog payloads, NRO, source, receipts and checksums.')
    receipt = json.loads((directory/'build-receipt.json').read_text())
    require(receipt['version'] == meta['version'] and receipt['update_repository'] == REPOSITORY, 'Wrong installer release identity.')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    require(receipt['source_commit'] == head, 'Artifact was built from a different source commit.')
    info = release.inspect_nro(directory/'FEXTendo-Patch.nro', full_romfs=False)
    require(info['nro_sha256'] == receipt['nro_sha256'], 'NRO differs from its build receipt.')
    return meta, assets, head


def verify_remote(remote, expected):
    uploaded = remote['assets']
    require(len(uploaded) == len(expected), 'Release assets are incomplete or duplicated.')
    require({a['name'] for a in uploaded} == set(expected), 'Release asset names differ from the verified package.')
    for asset in uploaded:
        spec = expected[asset['name']]
        require(asset['size'] == spec['size'] and asset.get('digest') == spec['digest'], 'GitHub asset digest mismatch: '+asset['name'])


def gh(*args):
    return subprocess.check_output(['gh', *args], cwd=ROOT, text=True)


def api(path, missing=False):
    run = subprocess.run(['gh', 'api', f'repos/{REPOSITORY}/{path}'], cwd=ROOT, text=True, capture_output=True)
    if run.returncode:
        try:
            not_found = str(json.loads(run.stdout).get('status')) == '404'
        except (ValueError, AttributeError):
            not_found = False
        if missing and not_found:
            return None
        raise RuntimeError(run.stderr.strip() or 'GitHub API failed.')
    return json.loads(run.stdout)


def publish(directory):
    require(os.environ.get('GH_REPO') == REPOSITORY, 'Publishing requires the official GH_REPO.')
    require(os.environ.get('GITHUB_REF') == 'refs/heads/main', 'Only main may publish.')
    meta, assets, head = verify(directory)
    tag = meta['tag']
    remote = api('releases/tags/'+tag, missing=True)
    if remote and not remote['draft']:
        # A later docs/maintenance commit can build without replacing released binaries.
        print(f'{tag} is already published. Increase the app version to publish new assets; existing release unchanged.')
        return
    latest = api('releases/latest', missing=True)
    if latest:
        require(semver(meta['version']) > semver(latest['tag_name'].removeprefix('v')), 'Refusing to replace latest with an older version.')
    notes = directory.parent/'release-notes.md'
    notes.write_text(
        f'FEXTendo Patch {tag}\n\n'
        'Download **FEXTendo-Patch.nro** and copy it to `SD:/switch/fextendo-patch/`. '
        'Check update uses this repository automatically.\n\n'
        'The bundled boot patch supports Atmosphere **1.11.2 / 5388824b**, with '
        'HOC **2.5.1 official defaults**. Install it, then reboot through '
        '**Hekate > More configs > FEXTendo Patch (emuMMC)**. Other Atmosphere '
        'versions require a matching bundle.\n\n'
        'The fxtauto-v1 loader supports one compatible game NSP: ordinary boot '
        'uses 32-bit no-alias; the patched boot selects 39-bit low-window. '
        'Existing fxtmem-v1 forwarders remain supported.\n\n'
        'Host tests and NRO/package validation passed. The new automatic loader '
        'still needs Switch validation; earlier kernel probe results do not '
        'certify this new path. No game data is included.\n\n'
        f'Source commit: `{head}`. Raw catalog/kernel/loader assets are used by '
        'the installer; source and SHA256SUMS are provided alongside the NRO.\n')
    if remote is None:
        existing_tag = api('git/ref/tags/'+tag, missing=True)
        if existing_tag:
            require(api('commits/'+tag)['sha'] == head, 'Existing tag points to another commit.')
        gh('release', 'create', tag, '--repo', REPOSITORY, '--target', head,
           '--draft', '--title', 'FEXTendo Patch '+tag, '--notes-file', str(notes))
        remote = api('releases/tags/'+tag)
    if api('git/ref/tags/'+tag, missing=True):
        require(api('commits/'+tag)['sha'] == head, 'Draft tag points to another commit.')
    else:
        require(remote['target_commitish'] == head, 'Draft targets another commit.')
    # Resume an interrupted draft without overwriting assets or exposing an incomplete release.
    present = {a['name']: a for a in remote['assets']}
    require(len(present) == len(remote['assets']) and set(present) <= set(assets), 'Unexpected draft assets.')
    for name, asset in present.items():
        require(asset['size'] == assets[name]['size'] and asset.get('digest') == assets[name]['digest'], 'Draft asset differs: '+name)
    missing = [str(directory/name) for name in sorted(assets) if name not in present]
    if missing:
        gh('release', 'upload', tag, *missing, '--repo', REPOSITORY)
    for attempt in range(3):
        remote = api('releases/tags/'+tag)
        try:
            verify_remote(remote, assets)
            break
        except ValueError:
            if attempt == 2:
                raise
            time.sleep(3)
    gh('release', 'edit', tag, '--repo', REPOSITORY, '--draft=false', '--latest', '--notes-file', str(notes))
    published = api('releases/tags/'+tag)
    require(not published['draft'] and not published['prerelease'], 'Release did not become public and stable.')
    require(api('commits/'+tag)['sha'] == head, 'Published tag points to another commit.')
    verify_remote(published, assets)
    print(published['html_url'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['metadata', 'verify', 'publish'])
    parser.add_argument('--input', type=Path, default=ROOT/'dist/release-assets')
    args = parser.parse_args()
    if args.command == 'metadata':
        result = metadata()
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
                for key, value in result.items():
                    out.write(f'{key}={value}\n')
        print(json.dumps(result))
    elif args.command == 'verify':
        result, assets, head = verify(args.input)
        print(json.dumps(result | {'assets': len(assets), 'commit': head, 'passed': True}))
    else:
        publish(args.input)


if __name__ == '__main__':
    main()
