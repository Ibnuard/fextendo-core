"""Boot-package failure checks; never access an actual SD or invoke Horizon."""
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import fextendo_memory_package as package


class EntryChecks(unittest.TestCase):
    def setUp(self):
        self.text = (package.CONFIG / 'fextendo-memory.ini').read_text()

    def test_single_emummc_entry(self):
        entry = package.parse_entry(self.text)
        self.assertEqual(entry['emummcforce'], '1')
        self.assertEqual(entry['kip1'], package.SD_LOADER)

    def test_reject_conflicting_loader_and_mmc_paths(self):
        for extra in ('kip1=atmosphere/kips/hoc.kip', 'kip1=atmosphere/kips/*',
                      'emummc_force_disable=1', 'payload=bootloader/payloads/fusee.bin',
                      '[config]\nautoboot=1', 'secmon=atmosphere/exosphere.bin'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                package.parse_entry(self.text + '\n' + extra + '\n')

    def test_reject_overrides_before_package3(self):
        lines = self.text.splitlines()
        pkg = lines.index('pkg3=atmosphere/package3')
        loader = lines.index('kip1=' + package.SD_LOADER)
        lines[pkg], lines[loader] = lines[loader], lines[pkg]
        with self.assertRaisesRegex(ValueError, 'Load package3'):
            package.parse_entry('\n'.join(lines))

    def test_reject_missing_force_or_wrong_kernel(self):
        for old, new in (('emummcforce=1', ''), ('mesosphere.bin', 'other.bin')):
            with self.subTest(old=old), self.assertRaises(ValueError):
                package.parse_entry(self.text.replace(old, new))

    def test_reject_escape_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            for rel in ('../outside', '/absolute', 'C:/outside', 'SD/../../outside', 'SD\\file'):
                with self.subTest(rel=rel), self.assertRaises(ValueError):
                    package.relative_file(Path(folder), rel)


class BinaryChecks(unittest.TestCase):
    def test_exact_tested_pair_and_default_cust(self):
        boot = ROOT / 'dist/fextendo-low-window-v1/boot'
        if not boot.exists():
            self.skipTest('Preserved boot artifact is a local build input')
        lock = json.loads((package.CONFIG / 'boot-lock.json').read_text())
        for name, expected in lock['boot_files'].items():
            package.checked_file(boot / name, expected)
        data = (boot / 'loader-hoc.kip').read_bytes()
        package.validate_kip(data)
        offset = lock['hoc_patched_settings_offset']
        length = lock['hoc_settings_length']
        self.assertEqual(package.digest(data[offset:offset + length]), lock['hoc_settings_sha256'])
        with self.assertRaises(ValueError):
            package.validate_kip(data[:-1])
        # Wrong process identity must never ship as the boot Loader.
        wrong = bytearray(data)
        struct.pack_into('<Q', wrong, 16, 0x100000000000002)
        with self.assertRaises(ValueError):
            package.validate_kip(wrong)

    def test_reject_personal_hoc_settings(self):
        # A compact stand-in with real KIP segment/header structure isolates the
        # packaging gate from source builds; source artifact tested above.
        data = bytearray(272)
        data[:4] = b'KIP1'
        data[4:10] = b'Loader'
        struct.pack_into('<Q', data, 16, 0x100000000000001)
        struct.pack_into('<IIII', data, 0x20, 0, 16, 16, 0)
        data[256:260] = b'CUST'
        lock = {'hoc_patched_settings_offset': 256, 'hoc_official_settings_offset': 256,
                'hoc_settings_length': 16, 'hoc_settings_sha256': package.digest(data[256:])}
        package.validate_hoc(bytes(data), bytes(data), lock)
        changed = bytearray(data)
        changed[268] = 1
        with self.assertRaisesRegex(ValueError, 'Private OC settings'):
            package.validate_hoc(bytes(changed), bytes(data), lock)

    def test_bmp_pixel_orientation_and_alpha(self):
        from fextendo_boot_art import bmp32
        from PIL import Image
        pic = Image.new('RGBA', (192, 192), (11, 19, 32, 255))
        pic.putpixel((0, 0), (95, 224, 195, 0))
        data = bmp32(pic)
        package.validate_bmp(data, (192, 192))
        # First stored row is the bottom; the transparent mint pixel is top-left.
        self.assertEqual(data[54:58], bytes((32, 19, 11, 255)))
        last_row = 54 + 191 * 192 * 4
        self.assertEqual(data[last_row:last_row + 4], bytes((195, 224, 95, 0)))
        with self.assertRaises(ValueError):
            package.validate_bmp(data, (192, 192), opaque=True)
        bad = bytearray(data)
        struct.pack_into('<H', bad, 28, 24)
        with self.assertRaises(ValueError):
            package.validate_bmp(bad, (192, 192))


class PowerShellCopyChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shell = shutil.which('pwsh') or shutil.which('powershell')
        if not cls.shell:
            raise unittest.SkipTest('PowerShell is not installed')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.kit = self.root / 'package'
        self.sd = self.root / 'sd'
        self.kit.mkdir()
        self.sd.mkdir()
        self.script = self.kit / 'Check-Package.ps1'
        shutil.copy2(package.CONFIG / 'Check-Package.ps1', self.script)
        lock = json.loads((package.CONFIG / 'boot-lock.json').read_text())
        (self.kit / 'provenance').mkdir()
        (self.kit / 'provenance/boot-lock.json').write_text(json.dumps(lock))
        for rel in package.SD_FILES:
            for target in (self.kit / 'SD' / rel, self.sd / rel):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'fixture-copy-test')
        files = {p.relative_to(self.kit).as_posix(): {'bytes': p.stat().st_size,
                 'sha256': package.digest(p.read_bytes())} for p in self.kit.rglob('*') if p.is_file()}
        (self.kit / 'manifest.json').write_text(json.dumps({'schema': 1, 'abi': 'fxtmem-v1',
            'version': '1.0.0', 'hoc': '2.5.1', 'atmosphere': '1.11.2', 'hos_reference': '22.5.0', 'files': files}))
        (self.kit / 'SHA256SUMS.txt').write_text(''.join(
            f'{package.digest(p.read_bytes())}  {p.relative_to(self.kit).as_posix()}\n'
            for p in sorted(self.kit.rglob('*')) if p.is_file()))
        pkg3 = bytearray(128)
        pkg3[:4] = b'PK31'
        pkg3[32:36] = b'FSS0'
        struct.pack_into('<I', pkg3, 36, len(pkg3))
        pkg3[56:60] = bytes((0, 2, 11, 1))
        struct.pack_into('<I', pkg3, 60, int(lock['atmosphere_revision'][:8], 16))
        (self.sd / 'atmosphere/package3').write_bytes(pkg3)
        (self.sd / 'emuMMC').mkdir()
        (self.sd / 'emuMMC/emummc.ini').write_text('[emummc]\nenabled=1\n')
        (self.sd / 'bootloader/sys').mkdir()
        for name in ('nyx.bin', 'emummc.kipm'):
            (self.sd / 'bootloader/sys' / name).write_bytes(b'fixture')

    def run_check(self):
        return subprocess.run([self.shell, '-NoProfile', '-NonInteractive', '-File', str(self.script),
                               '-SdRoot', str(self.sd)], capture_output=True, text=True)

    def test_matching_copy_is_read_only(self):
        before = {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS SD copy', result.stdout)
        after = {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_damaged_loader_copy_is_rejected(self):
        (self.sd / package.SD_LOADER).write_bytes(b'bad')
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('SD copy mismatch', result.stderr)

    def test_different_atmosphere_is_rejected(self):
        path = self.sd / 'atmosphere/package3'
        data = bytearray(path.read_bytes())
        data[58] = 12
        path.write_bytes(data)
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('requires 1.11.2', result.stderr)

    def test_disabled_emummc_is_rejected(self):
        (self.sd / 'emuMMC/emummc.ini').write_text('[emummc]\nenabled=0\n')
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('emuMMC is missing/disabled', result.stderr)

    def test_same_version_other_revision_is_rejected(self):
        path = self.sd / 'atmosphere/package3'
        data = bytearray(path.read_bytes())
        data[60] ^= 1
        path.write_bytes(data)
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('differs from the pinned build', result.stderr)

    def test_unexpected_main_config_in_copy_payload_is_rejected(self):
        (self.kit / 'SD/bootloader/hekate_ipl.ini').write_text('[config]\nautoboot=1\n')
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Undeclared package file', result.stderr)


if __name__ == '__main__':
    unittest.main()
