"""Exercise production C++ code, including interrupted FAT-style publication."""
from pathlib import Path
import hashlib, json, os, re, shutil, struct, subprocess, tempfile, unittest

ROOT=Path(__file__).resolve().parents[1]
DRIVER=ROOT/'build-host/driver'
ROMFS=ROOT/'romfs'

def fixture(root):
    for name in ['atmosphere','bootloader/sys','bootloader/ini','emuMMC']:
        (root/name).mkdir(parents=True,exist_ok=True)
    pkg=bytearray(64)
    pkg[:4]=b'PK31';pkg[32:36]=b'FSS0';struct.pack_into('<I',pkg,36,len(pkg))
    pkg[57:60]=bytes([2,11,1]);struct.pack_into('<I',pkg,60,0x5388824b)
    (root/'atmosphere/package3').write_bytes(pkg)
    (root/'bootloader/sys/nyx.bin').write_bytes(b'fixture')
    (root/'bootloader/sys/emummc.kipm').write_bytes(b'fixture')
    (root/'emuMMC/emummc.ini').write_text('[emummc]\nenabled=1\n')
    (root/'bootloader/hekate_ipl.ini').write_text('[config]\nautoboot=1\n[My entry]\npkg3=atmosphere/package3\n')

def snapshot(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}

class Fixtures(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name);self.sd=self.base/'sd';fixture(self.sd)
        self.romfs=ROMFS
    def tearDown(self):self.tmp.cleanup()
    def run_driver(self,command,*args,env=None,ok=True):
        r=subprocess.run([str(DRIVER),command,str(self.sd),str(self.romfs),*map(str,args)],text=True,capture_output=True,env={**os.environ,**(env or {})})
        if ok:self.assertEqual(r.returncode,0,r.stderr)
        return r
    def status(self,**kw):return json.loads(self.run_driver('status',**kw).stdout)

class Installer(Fixtures):
    def test_status_is_read_only(self):
        before=snapshot(self.sd);self.assertTrue(self.status()['ready']);self.assertEqual(before,snapshot(self.sd))
    def test_installs_verified_pair_and_preserves_global_config(self):
        before=snapshot(self.sd);self.run_driver('install');s=self.status();self.assertTrue(s['installed']);self.assertTrue(s['ready'])
        for path,digest in before.items():self.assertEqual(snapshot(self.sd)[path],digest)
        ini=(self.sd/'bootloader/ini/fextendo-patch.ini').read_text();self.assertEqual(ini.count('kip1='),1);self.assertIn('emummcforce=1',ini)
        self.assertNotIn('transaction.json',str(list(self.sd.rglob('*'))))
        again=snapshot(self.sd);self.assertNotEqual(self.run_driver('install',ok=False).returncode,0);self.assertEqual(again,snapshot(self.sd))
    def test_unknown_or_mismatched_running_version(self):
        before=snapshot(self.sd)
        for version in ['unknown','1.12.0','1.10.0']:
            self.assertFalse(self.status(env={'FXP_RUNNING_AMS':version})['ready'])
            self.assertNotEqual(self.run_driver('install',env={'FXP_RUNNING_AMS':version},ok=False).returncode,0)
        self.assertEqual(before,snapshot(self.sd))
    def test_package3_wrong_revision_and_truncation(self):
        p=self.sd/'atmosphere/package3';data=p.read_bytes()
        for content in [data[:48],data[:60]+bytes(4),b'BAD!'+data[4:]]:
            p.write_bytes(content);self.assertFalse(self.status()['ready'])
    def test_disabled_emummc_and_missing_hekate(self):
        p=self.sd/'emuMMC/emummc.ini';p.write_text('[emummc]\nenabled=0\n');self.assertFalse(self.status()['ready'])
        p.write_text('[emummc]\nenabled=1\n');(self.sd/'bootloader/sys/nyx.bin').unlink();self.assertFalse(self.status()['ready'])
    def test_cancel_does_not_write(self):
        before=snapshot(self.sd);self.assertNotEqual(self.run_driver('cancel',ok=False).returncode,0);self.assertEqual(before,snapshot(self.sd))
    def test_bad_payload_does_not_publish(self):
        self.romfs=self.base/'romfs';shutil.copytree(ROMFS,self.romfs)
        loader=json.loads((self.romfs/'catalog.json').read_text())['bundles'][0]['loader']['asset']
        p=self.romfs/'boot'/loader;data=bytearray(p.read_bytes());data[-1]^=1;p.write_bytes(data)
        before=snapshot(self.sd);r=self.run_driver('install',ok=False);self.assertNotEqual(r.returncode,0);self.assertIn('SHA-256',r.stderr);self.assertEqual(before,snapshot(self.sd))
    def test_changed_catalog_is_rejected(self):
        self.romfs=self.base/'romfs';shutil.copytree(ROMFS,self.romfs);p=self.romfs/'catalog.json';p.write_bytes(p.read_bytes()+b' ')
        self.assertNotEqual(self.run_driver('install',ok=False).returncode,0)
    def test_corrupt_install_repairs_to_fresh_directory(self):
        self.run_driver('install');p=next(self.sd.glob('atmosphere/fextendo/patch/*/loader.kip'));p.write_bytes(b'bad')
        self.assertFalse(self.status()['installed']);self.run_driver('install');self.assertTrue(self.status()['installed']);self.assertEqual(p.read_bytes(),b'bad')
        self.assertTrue(list(self.sd.glob('switch/fextendo-patch/backup-*.ini')))
    def test_catalog_update_and_reopen_recognition(self):
        self.run_driver('install');old=(self.sd/'bootloader/ini/fextendo-patch.ini').read_text()
        c=json.loads((ROMFS/'catalog.json').read_text());c['bundles'][0]['version']='1.1.1';c['catalog_version']='1.1.1'
        path=self.base/'new-catalog.json';path.write_text(json.dumps(c));self.run_driver('install-catalog',path)
        self.assertTrue(self.status()['installed']);self.assertNotEqual((self.sd/'bootloader/ini/fextendo-patch.ini').read_text(),old)
        self.assertEqual(next(self.sd.glob('switch/fextendo-patch/backup-*.ini')).read_text(),old)
    def test_upgrade_v1_loader_retains_previous_pair(self):
        c=json.loads((ROMFS/'catalog.json').read_text());b=c['bundles'][0]
        oldloader=ROMFS/'boot/loader-hoc-1.11.2.kip'
        b['version']='1.0.0';c['catalog_version']='1.0.0'
        b['loader']={'asset':oldloader.name,'bytes':oldloader.stat().st_size,'sha256':hashlib.sha256(oldloader.read_bytes()).hexdigest()}
        path=self.base/'v1.json';path.write_text(json.dumps(c));self.run_driver('install-catalog',path)
        entry=self.sd/'bootloader/ini/fextendo-patch.ini';previous=entry.read_text()
        payloads=snapshot(self.sd/'atmosphere/fextendo/patch')
        self.run_driver('install');self.assertTrue(self.status()['installed'])
        self.assertNotEqual(entry.read_text(),previous);self.assertIn('Bundle 1.1.0',entry.read_text())
        self.assertEqual(next(self.sd.glob('switch/fextendo-patch/backup-*.ini')).read_text(),previous)
        new=snapshot(self.sd/'atmosphere/fextendo/patch')
        for name,digest in payloads.items():self.assertEqual(new[name],digest)
    def test_future_atmosphere_requires_a_matching_catalog(self):
        # Synthetic fixture: not a claim that these binaries support 1.13.0.
        p=self.sd/'atmosphere/package3';data=bytearray(p.read_bytes());data[57]=0;data[58]=13;p.write_bytes(data)
        env={'FXP_RUNNING_AMS':'1.13.0'};self.assertFalse(self.status(env=env)['supported'])
        c=json.loads((ROMFS/'catalog.json').read_text());c['bundles'][0]['atmosphere']='1.13.0'
        path=self.base/'future.json';path.write_text(json.dumps(c));self.run_driver('install-catalog',path,env=env)
        self.assertTrue(self.status(env=env)['installed'])
    def test_112_chooses_new_pair_and_rejects_foreign_revision(self):
        p=self.sd/'atmosphere/package3';data=bytearray(p.read_bytes())
        data[57:60]=bytes([0,12,1]);struct.pack_into('<I',data,60,0x28d6a2e1);p.write_bytes(data)
        env={'FXP_RUNNING_AMS':'1.12.0','FXP_RUNNING_HOS':'23.0.0'}
        s=self.status(env=env);self.assertTrue(s['ready']);self.assertEqual(s['bundle'],'1.2.0')
        self.assertEqual(s['kernel'],'mesosphere-1.12.0.bin')
        self.assertEqual(s['loader'],'loader-hoc-1.12.0-auto-v1.2.0.kip')
        self.run_driver('install',env=env);self.assertTrue(self.status(env=env)['installed'])
        catalog=json.loads((ROMFS/'catalog.json').read_text());bundle=next(b for b in catalog['bundles'] if b['atmosphere']=='1.12.0')
        for kind,name in [('kernel','mesosphere.bin'),('loader','loader.kip')]:
            installed=next(self.sd.glob('atmosphere/fextendo/patch/*/'+name))
            self.assertEqual(hashlib.sha256(installed.read_bytes()).hexdigest(),bundle[kind]['sha256'])
        struct.pack_into('<I',data,60,0x5388824b);p.write_bytes(data)
        before=snapshot(self.sd);self.assertFalse(self.status(env=env)['supported'])
        self.assertNotEqual(self.run_driver('install',env=env,ok=False).returncode,0);self.assertEqual(before,snapshot(self.sd))
    def test_firmware_display_is_not_an_atmosphere_version_gate(self):
        # Selection test only: hardware compatibility must be validated separately.
        for version,rev in [('1.11.2',0x5388824b),('1.12.0',0x28d6a2e1)]:
            p=self.sd/'atmosphere/package3';data=bytearray(p.read_bytes())
            data[57:60]=bytes(reversed(list(map(int,version.split('.')))))
            struct.pack_into('<I',data,60,rev);p.write_bytes(data)
            for hos in ['17.0.0','18.0.0','19.0.1','20.0.0','21.0.0','22.5.0','23.0.0']:
                s=self.status(env={'FXP_RUNNING_AMS':version,'FXP_RUNNING_HOS':hos})
                self.assertTrue(s['ready']);self.assertEqual(s['hos'],hos)
    def test_1112_bundle_and_files_remain_immutable(self):
        catalog=json.loads((ROMFS/'catalog.json').read_text())
        old=next(b for b in catalog['bundles'] if b['atmosphere']=='1.11.2')
        self.assertEqual(old['version'],'1.1.0')
        for kind,digest in [('kernel','29ac80dcc6b7c909243dac1f7b1272e4eeb44882410c8c8032f7b9671a5f1d26'),
                            ('loader','aead8e1451db65572f8ca7b0e9971fed6206031b8533126cc6e2f63deaf99eb7')]:
            self.assertEqual(old[kind]['sha256'],digest)
            self.assertEqual(hashlib.sha256((ROMFS/'boot'/old[kind]['asset']).read_bytes()).hexdigest(),digest)
    def test_symlink_parent_is_refused(self):
        outside=self.base/'outside';outside.mkdir();(self.sd/'atmosphere/fextendo').symlink_to(outside,target_is_directory=True)
        self.assertNotEqual(self.run_driver('install',ok=False).returncode,0);self.assertEqual(list(outside.iterdir()),[])
    def test_journal_tampering_is_refused(self):
        d=self.sd/'switch/fextendo-patch';d.mkdir(parents=True);(d/'transaction.json').write_text('{"schema":1,"checksum":"bad","had_entry":false,"before":"","after":"oops"}')
        self.assertTrue(self.status()['recovery']);before=snapshot(self.sd);self.assertNotEqual(self.run_driver('recover',ok=False).returncode,0);self.assertEqual(before,snapshot(self.sd))
    def test_recovery_does_not_accept_a_damaged_published_pair(self):
        self.run_driver('install');entry=self.sd/'bootloader/ini/fextendo-patch.ini'
        j={'schema':1,'had_entry':False,'before':'','after':hashlib.sha256(entry.read_bytes()).hexdigest()}
        j['checksum']=hashlib.sha256(json.dumps(j,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        journal=self.sd/'switch/fextendo-patch/transaction.json';journal.write_text(json.dumps(j))
        next(self.sd.glob('atmosphere/fextendo/patch/*/loader.kip')).write_bytes(b'bad')
        before=snapshot(self.sd);self.assertNotEqual(self.run_driver('recover',ok=False).returncode,0)
        self.assertEqual(before,snapshot(self.sd));self.assertTrue(journal.exists())
    def test_interruption_at_every_mutation_boundary(self):
        # Run both a clean install and replacement of a user's existing entry.
        counts={}
        for old in [False,True]:
            for step in range(1,95):
                candidate=self.base/f'case-{old}-{step}';fixture(candidate);self.sd=candidate
                entry=self.sd/'bootloader/ini/fextendo-patch.ini';original='[Previous user entry]\npkg3=atmosphere/package3\n'
                if old:entry.write_text(original)
                r=self.run_driver('install',env={'FXP_FAIL_AFTER':str(step)},ok=False)
                self.assertIn(r.returncode,[0,99],r.stderr)
                if self.status()['recovery']:self.run_driver('recover')
                s=self.status()
                if not s['installed']:
                    if old:self.assertEqual(entry.read_text(),original)
                    else:self.assertFalse(entry.exists())
                    self.run_driver('install')
                self.assertTrue(self.status()['installed'])
                if r.returncode==0:
                    counts['replacement' if old else 'fresh']=step-1
                    break
            else:self.fail('Failure sweep did not reach the final mutation')
        (ROOT/'build-host/failure-sweep.json').write_text(json.dumps(counts,indent=2)+'\n')
    def test_update_repository_config(self):
        default=re.search(r'FXP_DEFAULT_REPOSITORY "([^"]*)"',(ROOT/'include/generated.hpp').read_text()).group(1)
        self.assertEqual(self.run_driver('repository').stdout.strip(),default);p=self.sd/'switch/fextendo-patch/update.ini';p.parent.mkdir(parents=True)
        p.write_text('[updates]\nrepository=owner/repo\n');self.assertEqual(self.run_driver('repository').stdout.strip(),'owner/repo')
        for bad in ['../repo','owner/repo/other','https://github.com/owner/repo']:
            p.write_text('[updates]\nrepository='+bad+'\n');self.assertNotEqual(self.run_driver('repository',ok=False).returncode,0)

class Manifest(Fixtures):
    def test_remote_catalog_release_validation(self):
        content=(ROMFS/'catalog.json').read_bytes();c=json.loads(content)
        assets=[{'name':'fextendo-patch.json','size':len(content),'digest':'sha256:'+hashlib.sha256(content).hexdigest(),'browser_download_url':'https://github.com/owner/repo/releases/download/v1.0.0/fextendo-patch.json'}]
        for b in c['bundles']:
            for key in ['kernel','loader']:
                a=b[key];assets.append({'name':a['asset'],'size':a['bytes'],'digest':'sha256:'+a['sha256'],'browser_download_url':'https://github.com/owner/repo/releases/download/v1.0.0/'+a['asset']})
        release={'draft':False,'prerelease':False,'tag_name':'v1.0.0','assets':assets}
        metadata=self.base/'release.json';manifest=self.base/'manifest.json';manifest.write_bytes(content)
        metadata.write_text(json.dumps(release));self.run_driver('release',metadata,manifest)
        for mutate in [lambda j:j.update(draft=True),lambda j:j['assets'][0].update(digest=None),lambda j:j['assets'][1].update(size=1),lambda j:j['assets'][0].update(browser_download_url='https://evil.example/patch')]:
            j=json.loads(json.dumps(release));mutate(j);metadata.write_text(json.dumps(j));self.assertNotEqual(self.run_driver('release',metadata,manifest,ok=False).returncode,0)
    def test_catalog_validation(self):
        original=json.loads((ROMFS/'catalog.json').read_text());path=self.base/'catalog.json'
        for mutate in [lambda j:j.update(schema=2),lambda j:j.update(min_app_version='9.0.0'),lambda j:j['bundles'][0]['kernel'].update(asset='../loader.kip'),lambda j:j['bundles'][0].update(hoc_configuration='custom'),lambda j:j['bundles'].append(j['bundles'][0]),lambda j:j['bundles'][0]['loader'].update(bytes=999999999)]:
            j=json.loads(json.dumps(original));mutate(j);path.write_text(json.dumps(j));self.assertNotEqual(self.run_driver('catalog',path,ok=False).returncode,0)
        path.write_text('{"schema":1,"schema":1}');self.assertNotEqual(self.run_driver('catalog',path,ok=False).returncode,0)

if __name__=='__main__':unittest.main()
