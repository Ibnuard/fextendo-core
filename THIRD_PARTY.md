# Third-party notices

- **Atmosphere / Mesosphere**: GPL-2.0, pinned source
  https://github.com/Atmosphere-NX/Atmosphere/tree/5388824be146a89619e8d641acd64599cf1c5f62
  Additional 1.12.0 source:
  https://github.com/Atmosphere-NX/Atmosphere/tree/28d6a2e11f2640077bbb8a9fbd463d3fa12b6984
  Corresponding port patch and receipt: `provenance/ams-1.12.0/`.
- **Horizon-OC**: GPL-2.0, loader source
  https://github.com/Horizon-OC/Horizon-OC/tree/d9906a794c6015a892c60744d520faf793d22549
  Official release 2.5.1 defaults, unchanged CUST block.
  The 1.12.0 loader ports this reviewed OC code to the new Atmosphere loader;
  it is a FEXTendo build, not an upstream HOC 1.12.0 certification.
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
- **curl**: Daniel Stenberg and contributors, curl license. https://curl.se/docs/copyright.html
- **zlib**: Jean-loup Gailly and Mark Adler, zlib license. https://zlib.net/zlib_license.html
- **devkitPro Switch application template**: Makefile derived from
  `/opt/devkitpro/examples/switch/templates/application/Makefile`.

Complete Atmosphere/HOC license texts, upstream source locks, patch files,
build helpers, and binary verification receipts are bundled under
`provenance/memory/`. Preserve these materials with binary distributions.
The release source archive includes all of this project's corresponding source.
