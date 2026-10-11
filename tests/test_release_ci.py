"""Exercise publication integrity guards without contacting GitHub."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import release_ci as ci


class ReleaseGuards(unittest.TestCase):
    def test_versions_and_pinned_bundle(self):
        self.assertEqual(ci.metadata()['version'], ci.release.VERSION)

    def test_strict_numeric_version_order(self):
        self.assertGreater(ci.semver('1.10.0'), ci.semver('1.9.9'))
        for value in ['v1.1.0', '1.01.0', '1.1', '1.1.0-rc1', '1.1.0\n']:
            with self.assertRaises(ValueError):
                ci.semver(value)

    def test_checksums_reject_changes_unlisted_files_and_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            payload = path/'loader.kip'
            payload.write_bytes(b'fixture')
            digest = hashlib.sha256(b'fixture').hexdigest()
            sums = path/'SHA256SUMS.txt'
            valid = digest+'  loader.kip\n'
            sums.write_text(valid)
            self.assertEqual(len(ci.checksums(path)), 2)
            payload.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                ci.checksums(path)
            payload.write_bytes(b'fixture')
            for content in [valid*2, digest+'  ../loader.kip\n', digest+'  /loader.kip\n']:
                sums.write_text(content)
                with self.assertRaises(ValueError):
                    ci.checksums(path)
            sums.write_text(valid)
            (path/'extra.kip').write_bytes(b'unlisted')
            with self.assertRaises(ValueError):
                ci.checksums(path)

    def test_remote_requires_complete_digest_verified_assets(self):
        expected = {'loader.kip': {'size': 10, 'digest': 'sha256:'+'a'*64}}
        good = {'name': 'loader.kip', **expected['loader.kip']}
        ci.verify_remote({'assets': [good]}, expected)
        for items in [[], [good, good], [{**good, 'digest': None}],
                      [{**good, 'size': 9}], [{**good, 'name': 'other.kip'}]]:
            with self.assertRaises(ValueError):
                ci.verify_remote({'assets': items}, expected)


if __name__ == '__main__':
    unittest.main()
