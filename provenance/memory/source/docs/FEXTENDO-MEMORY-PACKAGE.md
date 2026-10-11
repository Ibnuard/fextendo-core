# FEXTendo Memory 1.0.0

This is the boot environment for games ported to **FEXTendo Memory ABI v1**.
It packages the tested generic low-window Mesosphere and HOC Loader with a
dedicated Hekate entry, launcher-matched icon/boot logo, version lock and copy verification.
No game assets, Wine prefix or game forwarder are included.

## Installation

Copy the contents of **SD/** to the microSD root, then reboot once into
**Hekate > More configs > FEXTendo (emuMMC)**. The destination must already have
Atmosphere **1.11.2**, a working enabled emuMMC, and Hekate/Nyx compatible with
the console's firmware. The reference HOS is **22.5.0**. Other combinations
are not certified by this package. The HOC configuration is the official
**2.5.1 default**, byte for byte. Existing clock-manager profiles remain active.

For a single Hekate menu, choose **All configs** in Nyx's Home Screen setting.
The package leaves `hekate_ipl.ini`, `nyx.ini`, autoboot and boot wait unchanged.

Only these five files go on the SD:

```text
atmosphere/
  fextendo/memory-v1/
    mesosphere.bin
    loader.kip
bootloader/
  ini/fextendo-memory.ini
  res/fextendo-memory.bmp
  res/fextendo-boot.bmp
```

`manifest.json`, checksums, instructions, artwork previews, source and licenses
stay on the PC. No ZIP is required for local installation. The files do not
add per-game logging or diagnostic SD writes.

## Configuration

The entry reads `atmosphere/package3` first, then replaces its kernel and
Loader with the matching FEXTendo pair. Exosphere and other base components
come from that same package3; there is no dependency on a loose, potentially
outdated `atmosphere/exosphere.bin`. Only one Loader is selected: no wildcard
`kip1` and no second `hoc.kip`. `emummcforce=1` requires enabled emuMMC and
prevents an accidental fallback to sysMMC. `id=fxtmem1` identifies the entry.
These keys and the **More configs** location follow the
[Hekate configuration documentation](https://github.com/CTCaer/hekate#bootloader-configuration).

The icon is a 192 x 192 32-bit BMP, per the
[Nyx format](https://github.com/CTCaer/hekate/blob/master/nyx/README_RES.md).
The boot logo follows the
[Hekate orientation/format](https://github.com/CTCaer/hekate/blob/master/README_BOOTLOGO.md).
It appears when Hekate's existing boot-logo policy permits; no extra boot delay
is imposed merely to show the branding.

## Checking a copy and reverting

`Check-Package.ps1` checks package checksums without writing anything. Optional
`-SdRoot E:\` checks all five copied files, package3's size/version/source
revision, enabled emuMMC and Hekate modules. It needs an actual drive, such as
an SD reader or Hekate UMS, not Windows MTP. It cannot inspect encrypted HOS
version, prove SD health or boot the console; those remain device checks.
Checksums detect incomplete/changed copies, not a maliciously replaced package.

The old test entry remains available. After the new entry works, remove only
`bootloader/ini/fextendo-memory-v1.ini` and `atmosphere/fextendo-memory-v1/` to
retire the old package. To revert, boot the previous CFW entry. To uninstall
this package, remove its five owned SD files. The original package3, HOC KIP,
main Hekate config, emuMMC and game files are preserved.

## What has been validated

- Kernel and HOC Loader hashes exactly match the pair used for the successful
  CONTROL, OPTIN-A and OPTIN-B probe-r2 runs. Each opt-in title uses its ExeFS
  descriptor, without a Title ID allowlist or a kernel rebuild per game.
- The supplied HOC archive, its original KIP and the entire 26,824-byte CUST
  block are checked against pinned SHA256 values. In this baseline, the tested
  KIP already contains official defaults, so no binary modification is needed.
- Host checks validate loader identity/segments, boot key ordering, exclusive
  emuMMC selection, exact payload paths, BMP layout/alpha, copy hashes and the
  associated source/previous device evidence.
- **The new entry and artwork still need an on-console boot check.** Existing
  game runtime bugs are separate from these packaging changes. This does not
  claim compatibility with every firmware or that every game is stable.

Low guest virtual addresses and native backing above 4 GiB do not add physical
RAM. Previous probes measured about **3.09 GiB supplied heap** under a 3285 MiB
process quota. Descriptor-bearing runtimes can share this boot environment,
while their game folders, Wine profiles, saves and installed Title IDs stay
independent. Older Title-ID-specific low-window forwarders need their old
kernel or a compatible descriptor-bearing replacement. Adding a descriptor
alone does not port a runtime.

## Reproduction and credits

The packager consumes the preserved `fextendo-low-window-v1` build plus the
original HOC release and the verified device logs. It rejects mismatched
inputs and nonempty output paths. It never touches an installed SD or builds
a kernel implicitly. Python dependencies for artwork: Pillow, CairoSVG,
fontTools. On Windows, CairoSVG additionally needs its native Cairo library.

```sh
python tools/fextendo_memory_package.py \
  --baseline dist/fextendo-low-window-v1 \
  --hoc-archive /path/to/hoc-2.5.1.zip \
  --device-evidence local/fextendo-memory-probe-r2/device-pass \
  --output dist/FEXTendo-Memory-v1.0.0
python tools/fextendo_memory_package.py --verify dist/FEXTendo-Memory-v1.0.0
python -m unittest discover -s tests -p test_fextendo_memory_package.py
```

The package retains the original build receipt, complete patch files against
the pinned upstream source, ABI overlays, build helper and licenses. Rebuild
the original pair with `tools/build-fextendo-low-window.py` and the default
HOC 2.5.1 KIP, using fresh WSL/Linux work directories and devkitPro. The build
helper's `--hoc` selects that input explicitly. The packaging tool itself is
also included under `source/`, with the vector asset and font to reproduce it.

- Atmosphere/Mesosphere: [source commit 5388824](https://github.com/Atmosphere-NX/Atmosphere/tree/5388824be146a89619e8d641acd64599cf1c5f62), GPL-2.0.
- Horizon-OC: [loader source d9906a7](https://github.com/Horizon-OC/Horizon-OC/tree/d9906a794c6015a892c60744d520faf793d22549), [release 2.5.1](https://github.com/Horizon-OC/Horizon-OC/releases/tag/2.5.1), GPL-2.0.
- Autorun: [original low-window work](https://github.com/autorunhq/autorun/blob/cbb0e4e6e7fa7f47f328d92441f51bfb507f266f/horizon-wine/mesosphere/low-window.patch).
- Hekate/Nyx: CTCaer and contributors; required separately, not bundled.
- FEXTendo: generic opt-in ABI, validation, packaging and original launcher branding.
- Inter: SIL OFL 1.1, license included.

This is an independent FEXTendo package, not an official Atmosphere, HOC or
Hekate release.
