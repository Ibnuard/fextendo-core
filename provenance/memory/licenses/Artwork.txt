# FEXTendo Memory artwork

The icon and boot logo reuse the **same gamepad and FEXTendo wordmark PNGs as
the launcher**, from `assets/fextendo-v2/gamepad-flat.png` and `wordmark.png`.
No replacement logo or new FX monogram is used. Source images remain intact;
their original generation provenance is in `assets/fextendo-v2/GENERATION.md`.

`icon.svg` is an editable layout referencing those existing assets.
`tools/fextendo_boot_art.py` crops their transparent padding the same way as the
launcher builder, embeds them into the layout, renders at 4x, downsamples it
to a 192 x 192 Nyx icon, and writes uncompressed 32-bit BGRA BMP with alpha.
The boot logo uses those same PNGs and Inter glyph outlines for the subtitle.
Inter is under SIL OFL 1.1 (`assets/fonts/Inter/OFL.txt`). The output
is a 960 x 400 landscape design rotated 90 degrees counterclockwise for Hekate.
The packager records the exact launcher asset hashes in
`artwork/launcher-assets.json`. No screenshot or game cover is used.

Format references:
- [Nyx icon specification](https://github.com/CTCaer/hekate/blob/master/nyx/README_RES.md)
- [Hekate boot logo specification](https://github.com/CTCaer/hekate/blob/master/README_BOOTLOGO.md)
