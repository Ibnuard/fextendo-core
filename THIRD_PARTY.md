# Third-party notices

- **Atmosphere / Mesosphere**: GPL-2.0, pinned source
  https://github.com/Atmosphere-NX/Atmosphere/tree/5388824be146a89619e8d641acd64599cf1c5f62
  Additional 1.12.0 source:
  https://github.com/Atmosphere-NX/Atmosphere/tree/28d6a2e11f2640077bbb8a9fbd463d3fa12b6984
  Corresponding port patch and receipt: `provenance/ams-1.12.0/`.
  Additional 1.9.5 source:
  https://github.com/Atmosphere-NX/Atmosphere/tree/de9b02007bbfc62f2f9ee2abf4a96bc337f5f86a
  Standard/HOC source patches, build and test receipts: `provenance/ams-1.9.5/`.
- **Horizon-OC**: GPL-2.0, loader source
  https://github.com/Horizon-OC/Horizon-OC/tree/d9906a794c6015a892c60744d520faf793d22549
  Official release 2.5.1 defaults, unchanged CUST block.
  The 1.9.5 and 1.12.0 loaders port this reviewed OC code to their upstream loaders;
  these are FEXTendo builds, not upstream HOC certifications for those pairs.
- **Autorun**: reference low-window work and Atmosphere detection pattern.
  https://github.com/autorunhq/autorun/tree/cbb0e4e6e7fa7f47f328d92441f51bfb507f266f
  Original patches are included in `provenance/memory/source/`.
- **FEXTendo**: original launcher gamepad/wordmark and low-window ABI integration.
  Artwork provenance: `provenance/memory/source/assets/fextendo-v2/GENERATION.md`.
- **Inter**: Rasmus Andersson and contributors, SIL Open Font License 1.1.
  License: `provenance/memory/licenses/Inter-OFL.txt`.
- **nlohmann/json 3.12.0**: Niels Lohmann and contributors, MIT.
  Copyright/license embedded at the head and end of `third_party/json.hpp`.
  Upstream URL and SHA-256 are recorded in `third_party/json-provenance.json`.
- **libnx**: libnx authors, ISC. https://github.com/switchbrew/libnx
  The 1.12.0 boot loader uses `feebd026ca0f5dcc2119f46ad8e0d16ad3dd4973`;
  its license is included in `provenance/ams-1.12.0/LICENSE.libnx`.
  The 1.9.5 loaders use v4.12.0 (`7644c9b26099aa2d2145bc72a21ee24190e92085`),
  preserving the legacy PGL API; license in `provenance/ams-1.9.5/LICENSE.libnx`.
- **curl**: Daniel Stenberg and contributors, curl license. https://curl.se/docs/copyright.html
- **zlib**: Jean-loup Gailly and Mark Adler, zlib license. https://zlib.net/zlib_license.html
- **devkitPro Switch application template**: Makefile derived from
  `/opt/devkitpro/examples/switch/templates/application/Makefile`.

The Standard 1.12.0 loader removes the HOC-only sources, hooks and capability
from the sealed 1.12.0 port. Its exact source diff and build/test receipts are in
`provenance/standard-1.12.0`; reproduce with `tools/build_stock_112.py`. The Standard
1.11.2 loader is byte-identical to `provenance/memory-auto-v1.1.0/loader-stock.kip`.

Complete Atmosphere/HOC license texts, upstream source locks, patch files,
build helpers, and binary verification receipts are bundled under
`provenance/memory/`. Preserve these materials with binary distributions.
The release source archive includes all of this project's corresponding source.
