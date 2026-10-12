# FEXTendo Patch

[![Build and release](https://github.com/Ibnuard/fextendo-core/actions/workflows/build.yml/badge.svg)](https://github.com/Ibnuard/fextendo-core/actions/workflows/build.yml)

Source repository: **[Ibnuard/fextendo-core](https://github.com/Ibnuard/fextendo-core)**.
Download the NRO from **[Releases](https://github.com/Ibnuard/fextendo-core/releases/latest)**.
The app name remains **FEXTendo Patch**.

A standalone Nintendo Switch homebrew installer for **FEXTendo Memory ABI v1**.
One NRO contains the UI and multiple verified offline kernel/loader pairs. No game,
Wine prefix, NSP or forwarder is included. This project is independent of PES13.

## Use

Copy `FEXTendo-Patch.nro` into `SD:/switch/fextendo-patch/` and open it in hbmenu.
The installer does not itself require a low-window forwarder. Controller and touch
input are supported; use **A** to select, **B** to go back/cancel, **+** to exit,
**Y** to change loader, and **X** for help. Long operations run on a worker while the UI remains responsive.

1. Read **System status**. Both the running Atmosphere and the SD `package3`
   version must match a supported version. The source revision is displayed;
   a different revision does not block a matching version by itself.
2. Choose **Standard / sys-clk** (default) or **HOC / official defaults**,
   then **Install patch** and review the confirmation.
3. After installation, reboot to **Hekate > More configs > FEXTendo Patch (emuMMC)**.
   Nyx's **All configs** home-screen option can put this entry with other entries.

The installer selects the matching pair for the selected loader automatically.
Standard is the Atmosphere loader with FEXTendo memory support and no HOC code.
It works with or without sys-clk; it does not install sys-clk or change its profiles.
HOC is optional. Existing installations retain their loader selection when reopened;
choosing the other loader replaces only the managed FEXTendo entry after verification.

| Atmosphere / source revision | Standard bundle | HOC bundle | HOS reference |
| --- | --- | --- | --- |
| 1.9.5 / de9b0200 | 1.3.0 | 1.3.0 | 20.5.0 |
| 1.11.2 / 5388824b | 1.3.0 | 1.1.0 (unchanged) | 22.5.0 |
| 1.12.0 / 28d6a2e1 | 1.3.0 | 1.2.0 (unchanged) | 23.0.0 |

Both loader options support `fxtauto-v1` and `fxtmem-v1`. Only HOC bundles include
**HOC 2.5.1 official defaults**. The 1.12.0 HOC pair retains that version's upstream kernel/loader changes and ports
the reviewed HOC OC code onto it. This is a FEXTendo integration, not an official
HOC release or a claim of tested HOC compatibility with every firmware.

The 1.9.5 pair is built from upstream `de9b02007bbfc62f2f9ee2abf4a96bc337f5f86a`,
with its own kernel and both loader variants. The submitted `package3` was verified
byte-for-byte against the [official 1.9.5 release](https://github.com/Atmosphere-NX/Atmosphere/releases/tag/1.9.5).
Boot and gameplay validation of the new 1.9.5 pair is still required on a Switch.

**Switch firmware (HOS) and Atmosphere are different versions.** A user on FW 17,
18, etc. is not rejected merely because the reference firmware is newer. The
installer matches Atmosphere and package3; it does not impose a single HOS version.
Users on older Atmosphere must update Atmosphere/Hekate to a supported combination
or wait for a separately built bundle. The HOS references above (the legacy
catalog key is `tested_hos`) are not a device-tested firmware compatibility range.
See [compatibility and test details](docs/COMPATIBILITY.md).

An unsupported Atmosphere version is blocked, not substituted with a different pair.
Different commit revisions of a supported version are allowed, as in Autorun's
version-based setup, but acceptance is not a hardware-compatibility certification.
An enabled emuMMC and a Hekate/Nyx version supporting the console's HOS are required.

After updating Atmosphere, boot your ordinary CFW entry first, reopen this NRO,
and install the pair matching the new version before using the patched entry again.

**Installed** means the files and entry match their hashes. It is not proof that
the currently running kernel has the patch. The initial boot into the new entry
requires a reboot. Compatible games then share this environment with independent
folders and Wine profiles; no per-game Title ID kernel list is used.

An adaptive game NSP can now default to **32-bit no-alias** on ordinary
Atmosphere or FEXTendo Patch 1.0.0, and automatically receive **39-bit low-window**
on either bundled patched boot. It declares the optional `/fxtauto` ExeFS descriptor. The
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
HOC copy only if selected; tools that edit the global `hoc.kip` do **not** change this dedicated copy.
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

**Check update** also checks the app version. When a newer NRO is available,
choose **Update app**, wait for verification and installation, then exit and
reopen FEXTendo Patch. The app checks the GitHub SHA-256 digest, NRO structure,
application title and release version before replacing the actual launched SD
file. A newer app can be offered even when its catalog requires a newer parser.
Boot patches still use **Install patch** and require a reboot through Hekate;
updating the NRO alone does not change the installed boot pair or user settings.

Users on releases **before 1.3.0 must copy the new NRO once** to gain this feature.
The new updater cannot be added to an already installed old NRO through a catalog.
NRO updating requires a file launched from the SD `switch/` directory (hbmenu),
not nxlink or an embedded executable.

Downloads and staged writes leave the old app in place. During publication,
RomFS is closed and the old executable becomes `<app>.nro.recovery.nro` until
the replacement is verified. Successful updates remove temporary files. After
an interrupted update, reopening the normal NRO recovers automatically. If the
normal entry is missing, launch the recovery NRO in the same folder once, then
reopen the normal app. Modified or invalid recovery files are left intact.
See [release instructions](docs/RELEASING.md).

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
`dist/FEXTendo-Patch-v1.3.0/`. Local distribution is a folder, not a ZIP.
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
