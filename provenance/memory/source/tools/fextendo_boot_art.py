"""Reuse the launcher's original brand assets in Hekate's exact BMP layout.

PNG inputs are preserved, with the same transparent-padding crop as the
launcher asset builder. No logo is redrawn. The PNG outputs are previews;
Hekate reads the uncompressed 32-bit BGRA BMPs.
"""
import base64
import hashlib
import io
import json
from pathlib import Path
import struct

import cairosvg
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def bmp32(image):
    image = image.convert('RGBA')
    width, height = image.size
    pixels = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes('raw', 'BGRA')
    # BITMAPINFOHEADER / BI_RGB. Preserve alpha for Nyx (Pillow's BMP decoder
    # deliberately ignores BI_RGB alpha, so validation reads the bytes itself).
    return (struct.pack('<2sIHHI', b'BM', 54 + len(pixels), 0, 0, 54)
            + struct.pack('<IiiHHIIIIII', 40, width, height, 1, 32, 0,
                          len(pixels), 2835, 2835, 0, 0) + pixels)


def text_path(font, text, x, y, size, color):
    glyphs = font.getGlyphSet()
    cmap = font.getBestCmap()
    scale = size / font['head'].unitsPerEm
    cursor = 0
    paths = []
    for char in text:
        name = cmap[ord(char)]
        pen = SVGPathPen(glyphs)
        glyphs[name].draw(pen)
        paths.append(f'<path transform="translate({cursor},0)" d="{pen.getCommands()}"/>')
        cursor += font['hmtx'][name][0]
    return (f'<g fill="{color}" transform="translate({x},{y}) scale({scale},-{scale})">'
            + ''.join(paths) + '</g>')


def render(output):
    output.mkdir(parents=True, exist_ok=True)
    icon = (ROOT / 'assets/fextendo-memory/icon.svg').read_text(encoding='utf-8')
    embedded = {}
    inputs = {}
    for name in ('gamepad-flat.png', 'wordmark.png'):
        source = ROOT / 'assets/fextendo-v2' / name
        inputs[source.relative_to(ROOT).as_posix()] = hashlib.sha256(source.read_bytes()).hexdigest()
        original = Image.open(source).convert('RGBA')
        original = original.crop(original.getbbox())
        stream = io.BytesIO()
        original.save(stream, format='PNG')
        embedded[name] = 'data:image/png;base64,' + base64.b64encode(stream.getvalue()).decode('ascii')
        icon = icon.replace('../fextendo-v2/' + name, embedded[name])
    (output / 'icon.svg').write_text(icon, encoding='utf-8', newline='\n')
    (output / 'launcher-assets.json').write_text(json.dumps(inputs, indent=2) + '\n')
    png = cairosvg.svg2png(bytestring=icon.encode(), output_width=768, output_height=768)
    image = Image.open(io.BytesIO(png)).convert('RGBA').resize((192, 192), Image.Resampling.LANCZOS)
    (output / 'fextendo-memory.bmp').write_bytes(bmp32(image))
    image.save(output / 'icon-preview.png')
    with TTFont(ROOT / 'assets/fonts/Inter/Inter.ttf') as font:
        logo = ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="960" height="400" viewBox="0 0 960 400">'
                '<rect width="960" height="400" fill="#0b1320"/>'
                f'<image x="161" y="126" width="188" height="140" preserveAspectRatio="xMidYMid meet" xlink:href="{embedded["gamepad-flat.png"]}"/>'
                f'<image x="392" y="143" width="392" height="86" preserveAspectRatio="xMidYMid meet" xlink:href="{embedded["wordmark.png"]}"/>'
                + text_path(font, 'Memory environment', 397, 260, 24, '#a7b8c9')
                + '</svg>')
    (output / 'boot-logo.svg').write_text(logo, encoding='utf-8', newline='\n')
    png = cairosvg.svg2png(bytestring=logo.encode(), output_width=960, output_height=400)
    landscape = Image.open(io.BytesIO(png)).convert('RGBA')
    landscape.save(output / 'boot-preview.png')
    # Hekate's framebuffer is portrait; official README_BOOTLOGO requires CCW90.
    rotated = landscape.transpose(Image.Transpose.ROTATE_90)
    (output / 'fextendo-boot.bmp').write_bytes(bmp32(rotated))
    return image.size, rotated.size


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    print(render(parser.parse_args().output))
