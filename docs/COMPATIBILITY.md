# Compatibility in 1.3.0

One installer chooses a kernel/loader pair using the running Atmosphere version,
the version in SD `atmosphere/package3`, and the selected loader. It verifies both
payload hashes before publishing the boot entry. No Title ID whitelist is used.

Supported versions and the source revisions used to build their payloads:

- Atmosphere 1.9.5, `de9b0200`: new kernel and Standard/HOC 1.3.0 bundles from that upstream version; device validation pending.
- Atmosphere 1.11.2, `5388824b`: HOC bundle 1.1.0 is unchanged; Standard 1.3.0 reuses the sealed Standard loader.
- Atmosphere 1.12.0, `28d6a2e1`: HOC bundle 1.2.0 is unchanged; Standard 1.3.0 excludes all HOC hooks, sources and added capabilities.

Standard is the default for a fresh installation and requires no HOC. Users may
keep using sys-clk with their existing settings. HOC is an explicit alternative.
The installed variant is remembered through its verified bundle metadata.
Changing variants stages an independent directory and publishes the boot entry last;
the previous entry and files remain recoverable.

Revision matching is informational in 1.3.0. A custom build reporting the same
Atmosphere version may install either variant. Unsupported versions and mismatches
between running Atmosphere and SD package3 remain blocked. Payload hashes, KIP
identity, complete package3 header and HOC-default checks remain mandatory.

HOS/FW 17–23 numbers are not Atmosphere versions. HOS is displayed but is not
used as an exact-version gate. Matching an Atmosphere build in the installer is
not proof that every HOS/HOC/device combination has passed a boot test. Substantial
custom Atmosphere ABI changes can still need a separate port despite sharing the
same version label. Both 1.9.5 variants, Standard 1.12.0 and version-based acceptance need hardware testing.

## Atmosphere 1.9.5

The supplied 8 MiB `package3` matches the official 1.9.5 release byte-for-byte:
SHA-256 `b7d595469a681218c34adde1c355253babf86b34d29e2f411d2235f690f65076`.
The source is pinned to `de9b02007bbfc62f2f9ee2abf4a96bc337f5f86a`.
The catalog's HOS reference is 20.5.0, the firmware added in that upstream release;
it is not a claim that Atmosphere 1.9.5 supports newer HOS versions.

The new port keeps the upstream 32/36/39-bit layouts. Descriptor handling runs
before ASLR and process creation; only marked applications move native code above
4 GiB and expose the guest low window. The kernel independently validates the
flags and native address. Standard has no HOC hooks or added HOC capabilities;
the optional HOC loader uses the same reviewed OC sources and official settings
block as the previously distributed bundles. This is a FEXTendo integration.
HOC's seven uses of the later `R_DISCARD` macro are expanded to the equivalent
`static_cast<void>` expression for the 1.9.5 headers.

The build uses libnx v4.12.0, pinned to `7644c9b26099aa2d2145bc72a21ee24190e92085`, with
an upstream-style GetDebugEvent pointer cast, guarded by size, alignment and
payload-offset assertions. The later upstream explicit ApiInfo initialization
is also backported so GCC 16 LTO's maybe-uninitialized checks remain enabled.
GCC 16's unused-set and array-bounds warnings on the
unchanged old code remain visible but are not promoted to errors. The latter
comes from inlining the DebuggerAttached case into other unreachable switch arms.
All other warning classes remain fatal. No memory checks are disabled by these
compiler compatibility settings. Receipts and both complete source patches are
in `provenance/ams-1.9.5`.

## What changed in the 1.12.0 source port

The submitted 1.12.0 package with revision `085dde46` is recorded in
`provenance/ams-1.12.0/submitted-package3-audit.json`. Its PK31/FSS0 structure,
component ranges and internal KIP hashes passed offline inspection. It differs
from the official `28d6a2e1` package, including boot and ams_mitm payloads; the
distribution/source of these differences is not established. Its real header
is covered by both Standard and HOC installation tests. Revision differences
do not block selection, but this is not proof of boot compatibility. The
installer retains the user's package3 and uses the verified 1.12.0 boot pair.

- Build against upstream commit `28d6a2e11f2640077bbb8a9fbd463d3fa12b6984`.
- Use the renamed process-parameter flags, preserving the upstream 42-bit and
  ShadowStack handling and the newer loader decompression implementation.
- Read `/fxtmem` or `/fxtauto` before ASLR placement and process creation.
  `/fxtauto` promotes only a compatible 32-bit no-alias application to 39-bit,
  adding the 16 MiB system-resource pool. Missing descriptors retain stock behavior.
- The kernel separately validates opt-in flags and the native-code address.
  Only that opt-in 39-bit layout opens the guest low window. The ordinary
  32/36/39/42-bit layouts and unrelated processes keep their upstream behavior.
- Port only the reviewed HOC 2.5.1 OC sources, PCV capability and loader hooks.
  Do not replace the new loader with an older whole-file copy. Verify the entire
  CUST settings block against the previously distributed official defaults.

The 1.12.0 build is not an upstream HOC release. Its OC matching behavior on
each firmware still needs hardware testing. No clock/voltage values are increased
by this port. Do not advertise all FW 17–23 combinations as device-tested.

## Reproduce

For 1.9.5, use a clean checkout of its pinned revision, prebuild libnx v4.12.0
at `7644c9b26099aa2d2145bc72a21ee24190e92085`, and use the hactool revision
documented below. Its legacy PGL APIs differ from the libnx needed by 1.12.0.
Builds must be kept on the Linux filesystem:

```sh
python3 tools/build_ams195.py --tree /path/to/clean-atmosphere-1.9.5 \
  --output /path/to/ams195-output --libnx /path/to/libnx --hactool /path/to/hactool
python3 tools/check_ams195.py --tree /path/to/clean-atmosphere-1.9.5 \
  --output /path/to/ams195-output
python3 tools/import_ams195.py /path/to/ams195-output \
  --package-audit provenance/ams-1.9.5/package3-audit.json
```

The builder first saves the Standard loader and shared kernel, then adds only
the optional HOC sources/hooks and builds the second loader. The host checker
exercises production code under UBSan, including descriptor mutations, allocator
failure and the actual upstream ASLR switch and kernel validation blocks.

For Standard 1.12.0, use a fresh checkout of the same pinned Atmosphere revision:

```sh
python3 tools/build_stock_112.py --tree /path/to/fresh-atmosphere-1.12.0 \
  --output /path/to/standard-output --libnx /path/to/libnx
python3 tools/check_ams112.py --tree /path/to/fresh-atmosphere-1.12.0 \
  --output /path/to/standard-output
python3 tools/import_standard_loaders.py /path/to/standard-output
```

This derives the Standard port from the sealed 1.12.0 patch, removes HOC-only
source changes, verifies the descriptor ordering and absence of HOC ELF symbols,
then runs the production-source host checks. The 1.11.2 Standard loader is imported
byte-for-byte from `provenance/memory-auto-v1.1.0`, with its original source and receipt.

The following procedure reproduces the existing HOC 1.12.0 pair:

Use a fresh checkout of the pinned Atmosphere commit, devkitPro devkitA64 and
devkitARM, Python, g++, and hactool (`3121a5bf08cd81d3a99719feb2cab3b60767afd5`).
Build libnx commit `feebd026ca0f5dcc2119f46ad8e0d16ad3dd4973` separately with
`DEVKITPRO=/opt/devkitpro make -C /path/to/libnx -j4`, without `make install`.
Older packaged libnx lacks PGL APIs required by Atmosphere 1.12.0.
Keep build/output directories on the Linux filesystem under WSL:

```sh
python3 tools/build_ams112.py --tree /path/to/clean-atmosphere-1.12.0 \
  --output /path/to/boot-output --hactool /path/to/hactool --libnx /path/to/libnx
python3 tools/check_ams112.py --tree /path/to/clean-atmosphere-1.12.0 \
  --output /path/to/boot-output
```

The builder rejects unpinned/dirty inputs, writes the complete source diff and
source hashes, builds kernel and loader, and checks HOC defaults. Tests exercise
the production descriptor reader and forwarder allocator on the host. These are
not a substitute for booting the kernel on a Switch.

## Device test for the new bundle

1. Open the new NRO on the target Atmosphere (1.9.5 or 1.12.0) and confirm running/SD versions match.
2. Install and reboot through Hekate > More configs > FEXTendo Patch (emuMMC).
3. Confirm HOME and an ordinary application still work.
4. Launch the adaptive PES forwarder. Confirm the launcher detects low-window
   mode, then test HIGH through kick-off, replay, half-time and full-time.
5. Repeat with the other loader variant. Boot the ordinary CFW entry and confirm the same forwarder falls back to
   32-bit no-alias. Retest the old 1.11.2 combination separately when available.

Record Atmosphere, HOS, Switch model, Hekate and clocks with the result. If the
patched boot fails, use the existing ordinary CFW entry; the installer leaves it
and global HOC settings untouched.
