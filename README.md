# FEXTendo Patch

[![Build and release](https://github.com/Ibnuard/fextendo-core/actions/workflows/build.yml/badge.svg)](https://github.com/Ibnuard/fextendo-core/actions/workflows/build.yml)

Source repository: **[Ibnuard/fextendo-core](https://github.com/Ibnuard/fextendo-core)**.
Download the NRO from **[Releases](https://github.com/Ibnuard/fextendo-core/releases/latest)**.
The app name remains **FEXTendo Patch**.

A standalone Nintendo Switch homebrew installer for **FEXTendo Memory ABI v1**.
One NRO contains the UI and the verified offline kernel/loader pair. No game,
Wine prefix, NSP or forwarder is included. This project is independent of PES13.

## Use

Copy `FEXTendo-Patch.nro` into `SD:/switch/fextendo-patch/` and open it in hbmenu.
The installer does not itself require a low-window forwarder. Controller and touch
input are supported; use **A** to select, **B** to go back/cancel, **+** to exit,
and **X** for help. Long operations run on a worker while the UI remains responsive.

1. Read **System status**. Both the running Atmosphere and the SD `package3`
   version must match, with the exact supported `package3` source revision.
2. Choose **Install patch** and review the version/boot-entry confirmation.
3. After installation, reboot to **Hekate > More configs > FEXTendo Patch (emuMMC)**.
   Nyx's **All configs** home-screen option can put this entry with other entries.

The bundled pair is **Atmosphere 1.11.2 / 5388824b**, **HOC 2.5.1 official defaults**,
patch version **1.1.0**. The kernel is byte-identical to the earlier successful
CONTROL, OPTIN-A and OPTIN-B device probes. The updated loader adds `fxtauto-v1`
and still accepts existing `fxtmem-v1` forwarders. Official HOC settings are
unchanged. Reference HOS: **22.5.0**. The new loader/installer still require
on-console validation; the older probe results do not certify this new path.
An unsupported Atmosphere build is blocked, not substituted with a different pair.
An enabled emuMMC and a Hekate/Nyx version supporting the console's HOS are required.

**Installed** means the files and entry match their hashes. It is not proof that
the currently running kernel has the patch. The initial boot into the new entry
requires a reboot. Compatible games then share this environment with independent
folders and Wine profiles; no per-game Title ID kernel list is used.

An adaptive game NSP can now default to **32-bit no-alias** on ordinary
Atmosphere or FEXTendo Patch 1.0.0, and automatically receive **39-bit low-window**
on this 1.1.0 boot. It declares the optional `/fxtauto` ExeFS descriptor. The
loader selects the mode before ASLR and process creation; the game does not
change address width while running. Installing this update requires one reboot
through the patched entry, not a different NSP or kernel for each game.

## SD layout and recovery

```text
switch/fextendo-patch/
  FEXTendo-Patch.nro
  update.ini                       # optional repository configuration
  backup-<hash>.ini                 # previous managed entries, if replaced
  transaction.json                 # only during an unfinished installation
atmosphere/fextendo/patch/<bundle-id>/
  mesosphere.bin
  loader.kip
  icon.bmp
  boot.bmp
  bundle.json
bootloader/ini/fextendo-patch.ini
```

Boot payloads are immutable: a repair stages into a fresh `-rN` directory, then
publishes the entry last. Every write is flushed and verified. If interrupted,
reopen the NRO and select **Recover installation**. Recovery either preserves the
fully published new entry or restores the old one. An invalid journal or externally
modified entry stops recovery for manual inspection. Retain these files in that case.
Filesystem corruption or SD hardware failure cannot be made power-loss-proof by
application code; existing independent Hekate entries remain the fallback.

The installer does not edit `hekate_ipl.ini`, `nyx.ini`, autoboot, `package3`,
`atmosphere/kips/hoc.kip`, sys-clk profiles or game files. It installs a dedicated
HOC copy; tools that edit the global `hoc.kip` do **not** change this dedicated copy.
The new entry deliberately loads only one loader. Existing Autorun entries can
coexist, but this release does not claim a combined Autorun/FEXTendo kernel.

Status checks and update checks write no logs or catalogs to the SD. Cancel is
honored before the entry transaction; after that, the short commit/recovery phase
finishes before returning. Old payload directories are retained for rollback.
To uninstall, first boot another CFW entry, remove `bootloader/ini/fextendo-patch.ini`,
then remove only `atmosphere/fextendo/patch/` and this app's folder.

## Updates

Official builds use **Ibnuard/fextendo-core** automatically. **Check update**
reads the latest stable release; no configuration file is needed. Offline
installation remains usable. An optional override can be placed in
`SD:/switch/fextendo-patch/update.ini`:

```ini
[updates]
repository=Ibnuard/fextendo-core
```

A build can also embed that repository using `tools/prepare.py --repository`.
Updates use the public GitHub Releases API over certificate-verified HTTPS.
The catalog and each payload must match the SHA-256 digest reported by GitHub,
and every catalog payload must match the corresponding release asset.
Release URLs are restricted to the configured repository. Unknown schemas,
missing digests, oversized downloads, unsafe asset names, duplicate entries and
same-version payload changes are rejected. Trust is in the configured repository
and GitHub TLS; hashes are integrity checks, not an independent signing authority.

**Check update** only refreshes candidates in memory. **Install patch** performs
the selected compatible download and installation. This updates boot patches;
it does not replace the running NRO. If a future catalog requires a newer app,
the app tells the user to download the new NRO. See [release instructions](docs/RELEASING.md).

## Build and test

Linux/WSL prerequisites: devkitPro devkitA64, libnx, switch-curl, switch-zlib;
Python 3 with Pillow for UI assets. Host tests use g++, OpenSSL and libcurl.

```sh
python3 tools/prepare.py
bash tools/build-host.sh
bash tools/build-switch.sh
python3 tools/release.py
```

Generated NRO: `FEXTendo-Patch.nro`. Copy-ready distribution:
`dist/FEXTendo-Patch-v1.1.0/`. Local distribution is a folder, not a ZIP.
`dist/release-assets/` contains the raw files used by GitHub Releases and the updater.
The pipeline runs host tests, builds the NRO and uploads artifacts on each PR or
push to `main`. A new app version on `main` publishes a stable `vX.Y.Z` release
after verifying GitHub's uploaded asset digests. Re-running an already published
version never overwrites its assets. The boot kernel/loader are pinned, verified
inputs; the pipeline does not silently rebuild or substitute them.

Tests compile the same installer, updater validator and renderer as the Switch
build, simulate interruption at each mutation boundary, verify rollback, and
check incompatible environments/corrupt payloads without booting a console.
These tests do not substitute for a real console boot/network test.

## Credits and licenses

App source: GPL-2.0-or-later. Original FEXTendo launcher branding is reused.
Inter: SIL OFL 1.1. nlohmann/json: MIT. libnx, curl and zlib retain their upstream
licenses. Bundled Atmosphere/HOC patches: GPL-2.0, with original source revisions,
patches, build tools and hardware receipts in `provenance/memory/`.
See [third-party notices](THIRD_PARTY.md).
