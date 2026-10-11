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
mesosphere-1.11.2.bin
loader-hoc-1.11.2-auto-v1.1.0.kip
```

For bundle 1.1.0, the loader asset is
`loader-hoc-1.11.2-auto-v1.1.0.kip`. Follow the current catalog's exact filenames;
do not replace a published immutable asset in place. Its provenance and source
patches are in `provenance/memory-auto-v1.1.0`. The kernel remains the verified v1
binary. The new automatic selection is not covered by the old device-probe PASS.

To import a freshly built automatic loader locally, run
`python3 tools/import_auto_loader.py /path/to/verified/build`, then `prepare.py`
and the normal tests/build. Import validates the pair, source hashes, official
HOC settings and identical kernel. This does not modify any mounted SD card.

Also distribute `FEXTendo-Patch.nro`, `FEXTendo-Patch-source.tar.gz`,
`SHA256SUMS.txt`, `build-receipt.json`, `toolchain.txt`, and the README.
The NRO is a raw download; users do not need to extract a ZIP. GitHub's API supplies each uploaded asset's
`digest: sha256:...`; releases without these digests are refused. Do not upload
an archive in place of a kernel or loader: the NRO downloads these exact raw assets.

## Catalog contract

`romfs/catalog.json` is the offline source catalog, with schema 1, application
`fextendo-patch`, ABI `fxtmem-v1`, and `min_app_version`. Each bundle declares:

- patch version, exact Atmosphere semantic version and eight-digit source revision;
- HOC version, `hoc_configuration=official-release-default`, reference tested HOS;
- kernel and loader asset name, byte length and SHA-256.

Adding a new Atmosphere version means **rebuilding and testing its matching
kernel/loader pair**, adding both binaries, documenting source/provenance, and
adding its bundle to the catalog. Do not add unsupported versions as aliases of
an existing binary. Different games using ABI v1 do not require different bundles.

Increase the bundle version whenever its metadata or binary contents change.
Same-version replacements and duplicates for an Atmosphere version/revision are
rejected. Raise `min_app_version` only for a real installer/schema requirement;
NRO updates are manual. The UI reports when a newer app is required.

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

1. Open the NRO in hbmenu on Atmosphere 1.11.2. Check running/SD versions.
2. Install, reopen the app, confirm `Patch installed`, boot the new Hekate entry.
3. Run existing CONTROL/OPTIN memory probes and a descriptor-bearing game.
4. Check handheld Joy-Con, Pro Controller, touch and HOME behavior during work.
5. Publish a staging stable release in the chosen repo, configure it, verify a
   successful HTTPS check and download on hardware.
6. Check wrong Atmosphere, disabled emuMMC, disconnected Wi-Fi and damaged payload.

Do not simulate SD removal or power failure on a user's live boot card. Those
failure boundaries are exercised by the disposable host fixtures.
