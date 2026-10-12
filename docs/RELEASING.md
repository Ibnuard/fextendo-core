# Publishing FEXTendo Core

The official source and update repository is **Ibnuard/fextendo-core**. Its
name is embedded by default. The optional runtime override is
`SD:/switch/fextendo-patch/update.ini`:

```ini
[updates]
repository=Ibnuard/fextendo-core
```

For builds distributed to users, embed the repository at build time:

```sh
python3 tools/prepare.py
bash tools/build-host.sh
bash tools/build-switch.sh
python3 tools/release.py
```

Publish the contents of `dist/release-assets/` in a **public, stable GitHub Release**.
Do not mark it draft or prerelease; the app uses `/repos/{owner}/{repo}/releases/latest`.
The workflow runs tests and builds on PRs, pushes to `main`, and manual runs.
Only `main` in the official repository may publish. For a new release, update
`APP_VERSION` in the Makefile, `AppVersion` in `include/core.hpp`, and `VERSION`
in `tools/release.py` together, then merge/push to `main`. CI requires them to
agree, creates `vX.Y.Z`, uploads assets into a draft, validates every uploaded
digest, then publishes the completed stable release. Existing published versions
are left unchanged; increase the app version to publish changed NROs.

Actions and the devkitPro image are pinned. Toolchain versions and the exact
source commit accompany each build. Kernel/loader bytes come from the validated
catalog and provenance; an app build never silently changes the boot pair.

Required patch assets:

```text
fextendo-patch.json
mesosphere-1.9.5.bin
loader-stock-1.9.5-auto-v1.3.0.kip
loader-hoc-1.9.5-auto-v1.3.0.kip
mesosphere-1.11.2.bin
loader-hoc-1.11.2-auto-v1.1.0.kip
mesosphere-1.12.0.bin
loader-hoc-1.12.0-auto-v1.2.0.kip
loader-stock-1.11.2-auto-v1.3.0.kip
loader-stock-1.12.0-auto-v1.3.0.kip
```

For bundle 1.1.0, the loader asset is
`loader-hoc-1.11.2-auto-v1.1.0.kip`. Follow the current catalog's exact filenames;
do not replace a published immutable asset in place. Its provenance and source
patches are in `provenance/memory-auto-v1.1.0`. The kernel remains the verified v1
binary. The new automatic selection is not covered by the old device-probe PASS.

For the historical 1.11.2-only automatic-loader import, run
`python3 tools/import_auto_loader.py /path/to/verified/build`, then `prepare.py`
and the normal tests/build. Import validates the pair, source hashes, official
HOC settings and identical kernel. This does not modify any mounted SD card.
Do not run that historical importer over the multi-version catalog. For 1.12.0,
use `build_ams112.py`, `check_ams112.py`, then `import_ams112.py`; see
[compatibility](COMPATIBILITY.md). That import retains the complete 1.11.2 bundle.
For 1.9.5, use `build_ams195.py`, `check_ams195.py`, then `import_ams195.py`;
the importer preserves all existing versions and adds both loader variants.

Also distribute `FEXTendo-Patch.nro`, `FEXTendo-Patch-source.tar.gz`,
`SHA256SUMS.txt`, `build-receipt.json`, `toolchain.txt`, and the README.
The NRO is a raw download; users do not need to extract a ZIP. GitHub's API supplies each uploaded asset's
`digest: sha256:...`; releases without these digests are refused. Do not upload
an archive in place of a kernel or loader: the NRO downloads these exact raw assets.

## Catalog contract

`romfs/catalog.json` is the offline source catalog, with schema 1, application
`fextendo-patch`, ABI `fxtmem-v1`, and `min_app_version`. Each bundle declares:

- patch version, exact Atmosphere semantic version and eight-digit source revision;
- loader kind: missing means legacy `hoc`; `stock` uses an empty HOC version and `hoc_configuration=not-applicable`;
- for HOC: version and `hoc_configuration=official-release-default`; reference HOS (`tested_hos` is a legacy field name, not a tested firmware range);
- kernel and loader asset name, byte length and SHA-256.

Adding a new Atmosphere version means **rebuilding and testing its matching
kernel/loader pair**, adding both binaries, documenting source/provenance, and
adding its bundle to the catalog. Do not add unsupported versions as aliases of
an existing binary. Different games using ABI v1 do not require different bundles.

Increase the bundle version whenever its metadata or binary contents change.
Same-version replacements and duplicates for an Atmosphere version/loader kind are
rejected. Raise `min_app_version` only for a real installer/schema requirement;
From app 1.3.0, Check update offers an in-app NRO upgrade using the stable release
tag (`vX.Y.Z`) and `FEXTendo-Patch.nro` asset. The asset must have a GitHub SHA-256
digest and matching NACP title/version. App upgrades are checked before rejecting
a catalog that needs a newer parser. Users on pre-1.3.0 NROs need one manual copy.
Catalogs with Standard/HOC alternatives require `min_app_version=1.3.0` so old
installers cannot select the wrong variant. Legacy HOC bundle IDs and payloads
are unchanged. Commit revisions are provenance, not an install gate in 1.3.0.

The NRO transaction writes a verified download next to the actual launched app.
RomFS is unmounted before publication. FAT cannot atomically replace an existing
file with rename, so a checksummed journal and launchable `.recovery.nro` preserve
the previous executable across the two renames. No cancellation is accepted once
publication begins. Startup recovery validates old/new hashes before cleanup;
unexpected target or backup changes stop recovery without overwriting them.
The app exits after publication and does not read the new RomFS while old code runs.

## Trust and release operations

Configure only a repository controlled by the FEXTendo maintainer. GitHub TLS
and the configured repository are the trust root; API digests detect changed or
truncated downloads, not a compromised repository. The installer accepts no
arbitrary destination paths, command execution, ZIP extraction or remote scripts.

Release checking stays in RAM. Installation downloads the selected supported
pair, verifies it, writes an isolated immutable directory, then publishes a
journaled boot entry. Prior boot files remain available. No automatic reboot,
Atmosphere upgrade, HOC global overwrite or per-game runtime replacement occurs.

## Hardware acceptance checklist

Host tests cover logic and interrupted writes, but the following still need a
Switch test before describing the new installer as production-validated:

1. Open the NRO in hbmenu on each supported Atmosphere build. Check running/SD versions and the selected bundle.
2. Install, reopen the app, confirm `Patch installed`, boot the new Hekate entry.
3. Run existing CONTROL/OPTIN memory probes and a descriptor-bearing game.
4. Check handheld Joy-Con, Pro Controller, touch and HOME behavior during work.
5. Publish a staging stable release in the chosen repo, configure it, verify a
   successful HTTPS check and download on hardware.
6. Check wrong Atmosphere, disabled emuMMC, disconnected Wi-Fi and damaged payload.

Do not simulate SD removal or power failure on a user's live boot card. Those
failure boundaries are exercised by the disposable host fixtures.
