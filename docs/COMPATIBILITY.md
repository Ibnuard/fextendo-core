# Compatibility in 1.2.0

One installer chooses a kernel/loader pair using the running Atmosphere version
and the exact source revision in SD `atmosphere/package3`. It verifies both
payload hashes before publishing the boot entry. No Title ID whitelist is used.

Supported source identities:

- Atmosphere 1.11.2, `5388824b`: existing bundle 1.1.0 is unchanged.
- Atmosphere 1.12.0, `28d6a2e1`: new bundle 1.2.0, device validation pending.

HOS/FW 17–23 numbers are not Atmosphere versions. HOS is displayed but is not
used as an exact-version gate. Matching an Atmosphere build in the installer is
not proof that every HOS/HOC/device combination has passed a boot test. Custom
Atmosphere source revisions need their own build and are not guessed compatible.

## What changed in the 1.12.0 source port

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

1. Open the new NRO on Atmosphere 1.12.0 and confirm running/SD versions match.
2. Install and reboot through Hekate > More configs > FEXTendo Patch (emuMMC).
3. Confirm HOME and an ordinary application still work.
4. Launch the adaptive PES forwarder. Confirm the launcher detects low-window
   mode, then test HIGH through kick-off, replay, half-time and full-time.
5. Boot the ordinary CFW entry and confirm the same forwarder falls back to
   32-bit no-alias. Retest the old 1.11.2 combination separately when available.

Record Atmosphere, HOS, Switch model, Hekate and clocks with the result. If the
patched boot fails, use the existing ordinary CFW entry; the installer leaves it
and global HOC settings untouched.
