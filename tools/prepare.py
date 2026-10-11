"""Prepare reproducible UI assets; import a verified Memory package only on request."""
from pathlib import Path
import argparse, hashlib, json, re, shutil, struct, urllib.request
from PIL import Image, ImageFont, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPOSITORY = 'Ibnuard/fextendo-core'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def import_package(package):
    manifest = json.loads((package / 'manifest.json').read_text())
    for name, spec in manifest['files'].items():
        path = package / name
        if path.stat().st_size != spec['bytes'] or sha(path.read_bytes()) != spec['sha256']:
            raise ValueError(f'Package verification failed: {name}')
    lock = json.loads((package / 'provenance/boot-lock.json').read_text())
    for folder in ['assets', 'romfs/boot', 'provenance/memory', 'third_party', 'include']:
        (ROOT / folder).mkdir(parents=True, exist_ok=True)
    for name in ['gamepad-flat.png', 'wordmark.png']:
        shutil.copy2(package / 'source/assets/fextendo-v2' / name, ROOT / 'assets' / name)
    shutil.copy2(package / 'source/assets/fonts/Inter/Inter.ttf', ROOT / 'assets/Inter.ttf')
    shutil.copy2(package / 'artwork/icon-preview.png', ROOT / 'assets/boot-icon.png')
    # Keep the complete build instructions, patches, receipts and licenses with the project.
    for name in ['source', 'provenance', 'licenses']:
        shutil.copytree(package / name, ROOT / 'provenance/memory' / name, dirs_exist_ok=True)
    pairs = [('kernel', 'SD/atmosphere/fextendo/memory-v1/mesosphere.bin', 'mesosphere-1.11.2.bin'),
             ('loader', 'SD/atmosphere/fextendo/memory-v1/loader.kip', 'loader-hoc-1.11.2.kip')]
    bundle = dict(version=lock['version'], atmosphere=lock['atmosphere_version'],
                  revision=lock['atmosphere_revision'][:8], hoc=lock['hoc_version'],
                  hoc_configuration='official-release-default', tested_hos=lock['hos_reference'])
    for key, source, dest in pairs:
        data = (package / source).read_bytes()
        (ROOT / 'romfs/boot' / dest).write_bytes(data)
        bundle[key] = dict(asset=dest, bytes=len(data), sha256=sha(data))
    catalog = dict(schema=1, application='fextendo-patch', abi='fxtmem-v1',
                   min_app_version='1.0.0', catalog_version='1.0.0', bundles=[bundle])
    (ROOT / 'romfs/catalog.json').write_text(json.dumps(catalog, indent=2) + '\n')
    for name in ['fextendo-memory.bmp', 'fextendo-boot.bmp']:
        shutil.copy2(package / 'SD/bootloader/res' / name, ROOT / 'romfs/boot' / name)
    # Vendored, pinned JSON parser. No network is used by subsequent builds.
    url = 'https://raw.githubusercontent.com/nlohmann/json/v3.12.0/single_include/nlohmann/json.hpp'
    data = urllib.request.urlopen(url, timeout=30).read()
    (ROOT / 'third_party/json.hpp').write_bytes(data)
    (ROOT / 'third_party/json-provenance.json').write_text(json.dumps(dict(url=url, sha256=sha(data)), indent=2)+'\n')
    shutil.copy2(package / 'licenses/LICENSE.Atmosphere', ROOT / 'LICENSE')

def assets(repository=DEFAULT_REPOSITORY):
    out = ROOT / 'romfs/ui'
    out.mkdir(parents=True, exist_ok=True)
    for filename, size, dest in [('gamepad-flat.png', (88, 64), 'gamepad.rgba'),
                                  ('wordmark.png', (260, 68), 'wordmark.rgba')]:
        im = Image.open(ROOT / 'assets' / filename).convert('RGBA')
        im = ImageOps.contain(im.crop(im.getbbox()), size, Image.Resampling.LANCZOS)
        tile = Image.new('RGBA', size)
        tile.alpha_composite(im, ((size[0]-im.width)//2, (size[1]-im.height)//2))
        (out / dest).write_bytes(tile.tobytes())
    records, pixels = [], bytearray()
    for size, weight in [(18, 400), (24, 600), (40, 600), (14, 500)]:
        font = ImageFont.truetype(str(ROOT / 'assets/Inter.ttf'), size*4)
        font.set_variation_by_axes([18, weight])
        for code in range(32, 127):
            ch = chr(code)
            box = font.getbbox(ch, anchor='ls')
            x, y = box[0]//4, box[1]//4
            w, h = (box[2]+3)//4-x, (box[3]+3)//4-y
            tile = Image.new('L', (max(1,w*4), max(1,h*4)))
            ImageDraw.Draw(tile).text((-x*4, -y*4), ch, font=font, fill=255, anchor='ls')
            records.append(struct.pack('<IhhhhHH', len(pixels), x, y, w, h, round(font.getlength(ch)/4), 0))
            if w*h:
                pixels.extend(tile.resize((w,h),Image.Resampling.LANCZOS).tobytes())
    (out/'font.bin').write_bytes(b'FXF2'+struct.pack('<I',len(pixels))+b''.join(records)+pixels)
    icon = Image.open(ROOT/'assets/boot-icon.png').convert('RGB').resize((256,256), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(icon)
    font = ImageFont.truetype(str(ROOT/'assets/Inter.ttf'), 18)
    font.set_variation_by_axes([18, 600])
    draw.rounded_rectangle((89,215,167,244), radius=7, fill=(21,102,233))
    draw.text((128,229),'PATCH',font=font,anchor='mm',fill='white')
    icon.save(ROOT/'assets/icon.jpg', quality=95, subsampling=0)
    generated = ['romfs/boot/fextendo-memory.bmp','romfs/boot/fextendo-boot.bmp','romfs/catalog.json']
    header = '// Generated by tools/prepare.py\n#pragma once\n'
    if repository and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*',repository):
        raise ValueError('Repository must be owner/repo')
    if '..' in repository:
        raise ValueError('Invalid repository')
    header += f'#define FXP_DEFAULT_REPOSITORY "{repository}"\n'
    for key, path in zip(['ICON_HASH','BOOT_HASH','CATALOG_HASH'], generated):
        header += f'#define FXP_{key} "{sha((ROOT/path).read_bytes())}"\n'
    (ROOT/'include/generated.hpp').write_text(header)

if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--import-package',type=Path)
    p.add_argument('--repository',default=DEFAULT_REPOSITORY)
    a=p.parse_args()
    if a.import_package:
        import_package(a.import_package)
    assets(a.repository)
    print('Prepared FEXTendo Patch assets and verified bundle')
