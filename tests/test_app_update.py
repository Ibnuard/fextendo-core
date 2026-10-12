"""Exercise real NRO validation and FAT-compatible update/recovery boundaries."""
import hashlib
import json
import struct
from test_installer import Fixtures, snapshot, ROOT

CURRENT='1.3.0'
NEXT='1.4.0'
REL='switch/fextendo-patch/FEXTendo-Patch.nro'

def nro(version=CURRENT, title='FEXTendo Patch'):
    body=0x1000;icon=56;nacp=icon+16;romfs=nacp+0x4000
    d=bytearray(body+romfs+0x50)
    d[16:20]=b'NRO0';struct.pack_into('<I',d,24,body)
    struct.pack_into('<IIIIII',d,0x20,0,0x800,0x800,0x400,0xc00,0x400)
    d[body:body+4]=b'ASET'
    struct.pack_into('<QQQQQQ',d,body+8,icon,16,nacp,0x4000,romfs,0x50)
    d[body+icon:body+icon+2]=b'\xff\xd8'
    d[body+nacp:body+nacp+len(title)]=title.encode()
    d[body+nacp+0x3060:body+nacp+0x3060+len(version)]=version.encode()
    return d

class AppUpdate(Fixtures):
    def setUp(self):
        super().setUp();self.target=self.sd/REL;self.target.parent.mkdir(parents=True)
        self.old=nro();self.new=nro(NEXT);self.target.write_bytes(self.old)
        self.payload=self.base/'update.nro';self.payload.write_bytes(self.new)
    def update(self,command='app-install',**kwargs):
        return self.run_driver(command,REL,self.payload,NEXT,**kwargs)
    def recover(self,**kwargs):return self.run_driver('app-recover',REL,**kwargs)
    def test_update_keeps_settings_and_boot_files(self):
        before=snapshot(self.sd);self.update()
        self.assertEqual(self.target.read_bytes(),self.new)
        after=snapshot(self.sd);self.assertEqual(set(before),set(after))
        for path,digest in before.items():
            if path!=REL:self.assertEqual(after[path],digest)
        self.assertEqual(self.recover().stdout.strip(),'0')
    def test_nro_checks_identity_version_and_ranges(self):
        bad=[]
        d=nro(NEXT);d[16]=0;bad.append(d)
        bad.extend([nro(NEXT,'Other App'),nro('1.3.0'),nro('1.2.0'),nro('1.4.1')])
        d=nro(NEXT);struct.pack_into('<I',d,24,0xffffffff);bad.append(d)
        d=nro(NEXT);struct.pack_into('<QQ',d,0x1000+24,0xfffffffffffffff0,0x4000);bad.append(d)
        d=nro(NEXT);struct.pack_into('<I',d,0x2c,0xffffffff);bad.append(d)
        bad.append(nro(NEXT)[:-1])
        before=snapshot(self.sd)
        for data in bad:
            with self.subTest(size=len(data)):
                self.payload.write_bytes(data);self.assertNotEqual(self.update(ok=False).returncode,0)
                self.assertEqual(before,snapshot(self.sd))
    def test_hash_failure_keeps_old_app(self):
        before=snapshot(self.sd);self.assertNotEqual(self.update(env={'FXP_NRO_HASH':'0'*64},ok=False).returncode,0)
        self.assertEqual(before,snapshot(self.sd))
    def test_wrong_running_file_is_refused(self):
        self.target.write_bytes(nro('1.2.0'));before=snapshot(self.sd)
        self.assertNotEqual(self.update(ok=False).returncode,0);self.assertEqual(before,snapshot(self.sd))
    def test_safe_actual_launch_path(self):
        for value in ['sdmc:/'+REL,'/'+REL,REL,'sdmc:/'+REL+'.recovery.nro']:
            self.assertEqual(self.run_driver('app-target',value).stdout.strip(),REL)
        for value in ['', 'nxlink', 'romfs:/'+REL, '/switch/../other.nro', 'sdmc:/atmosphere/a.nro','switch//a.nro']:
            self.assertNotEqual(self.run_driver('app-target',value,ok=False).returncode,0)
    def test_cancel_before_and_after_staging(self):
        before=snapshot(self.sd)
        for count in [0,2]:
            self.assertNotEqual(self.update('app-stage',env={'FXP_CANCEL_AFTER':str(count)},ok=False).returncode,0)
            self.recover();self.assertEqual(before,snapshot(self.sd))
    def test_staged_file_change_refuses_publication(self):
        self.update('app-stage');stage=self.sd/(REL+'.download');stage.write_bytes(b'partial transfer')
        self.assertNotEqual(self.run_driver('app-publish',REL,ok=False).returncode,0)
        self.assertEqual(self.target.read_bytes(),self.old);self.recover();self.assertFalse(stage.exists())
    def test_unrelated_target_and_backup_are_not_overwritten(self):
        self.update('app-stage');self.target.write_bytes(b'user changed file');before=snapshot(self.sd)
        self.assertNotEqual(self.run_driver('app-publish',REL,ok=False).returncode,0)
        self.assertNotEqual(self.recover(ok=False).returncode,0);self.assertEqual(before,snapshot(self.sd))
    def test_journal_tampering_is_refused(self):
        self.update('app-stage');p=self.sd/(REL+'.update.json');j=json.loads(p.read_text());j['next']['hash']='0'*64;p.write_text(json.dumps(j))
        before=snapshot(self.sd);self.assertNotEqual(self.recover(ok=False).returncode,0);self.assertEqual(before,snapshot(self.sd))
    def test_symlink_target_is_refused(self):
        outside=self.base/'outside.nro';outside.write_bytes(self.old);self.target.unlink();self.target.symlink_to(outside)
        self.assertNotEqual(self.update(ok=False).returncode,0);self.assertEqual(outside.read_bytes(),self.old)
    def test_every_mutation_keeps_a_launchable_app_and_recovers(self):
        expected={bytes(self.old),bytes(self.new)}
        for step in range(1,40):
            for suffix in ['', '.download', '.recovery.nro', '.update.json']:
                (self.sd/(REL+suffix)).unlink(missing_ok=True)
            self.target.write_bytes(self.old)
            r=self.update(env={'FXP_FAIL_AFTER':str(step)},ok=False)
            candidates=[p for p in [self.target,self.sd/(REL+'.recovery.nro')] if p.exists()]
            self.assertTrue(any(p.read_bytes() in expected for p in candidates),f'no launchable app at boundary {step}')
            self.recover();self.assertIn(self.target.read_bytes(),expected)
            self.assertEqual(list(self.target.parent.iterdir()),[self.target])
            if r.returncode==0:break
            self.assertEqual(r.returncode,99)
        else:self.fail('Did not reach successful publication')
        self.assertGreater(step,10)
        (ROOT/'build-host/app-update-failure-sweep.json').write_text(json.dumps({'mutation_boundaries':step-1,'passed':True})+'\n')
    def test_recovery_can_itself_be_interrupted(self):
        for step in range(1,24):
            for suffix in ['', '.download', '.recovery.nro', '.update.json']:
                (self.sd/(REL+suffix)).unlink(missing_ok=True)
            self.target.write_bytes(self.old);self.update('app-stage')
            backup=self.sd/(REL+'.recovery.nro');self.target.rename(backup)
            r=self.recover(env={'FXP_FAIL_AFTER':str(step)},ok=False)
            self.assertTrue(any(p.exists() and p.read_bytes()==self.old for p in [self.target,backup]))
            self.recover();self.assertEqual(self.target.read_bytes(),self.old)
            self.assertEqual(list(self.target.parent.iterdir()),[self.target])
            if r.returncode==0:break
            self.assertEqual(r.returncode,99)
        else:self.fail('Did not complete recovery')
    def metadata(self,version=NEXT,minimum=CURRENT,has_nro=True):
        c=json.loads((self.romfs/'catalog.json').read_text());c['min_app_version']=minimum
        data=json.dumps(c).encode();manifest=self.base/'manifest.json';manifest.write_bytes(data)
        def asset(name,data):return {'name':name,'size':len(data),'digest':'sha256:'+hashlib.sha256(data).hexdigest(),'browser_download_url':'https://github.com/owner/repo/releases/download/v'+version+'/'+name}
        assets=[asset('fextendo-patch.json',data)]
        if has_nro:assets.append(asset('FEXTendo-Patch.nro',self.new))
        names=set()
        for b in c['bundles']:
            for kind in ['kernel','loader']:
                name=b[kind]['asset']
                if name not in names:assets.append(asset(name,(self.romfs/'boot'/name).read_bytes()));names.add(name)
        release=self.base/'release.json';release.write_text(json.dumps({'tag_name':'v'+version,'draft':False,'prerelease':False,'assets':assets}))
        return release,manifest
    def test_newer_app_can_be_offered_before_catalog_upgrade(self):
        for minimum,required in [(CURRENT,False),(NEXT,True)]:
            paths=self.metadata(minimum=minimum);u=json.loads(self.run_driver('update-metadata',*paths).stdout)
            self.assertTrue(u['available']);self.assertEqual(u['required'],required);self.assertEqual(u['has_catalog'],not required)
    def test_no_app_downgrade_and_missing_digest_rejected(self):
        paths=self.metadata(version=CURRENT,has_nro=False)
        self.assertFalse(json.loads(self.run_driver('update-metadata',*paths).stdout)['available'])
        paths=self.metadata(has_nro=False);self.assertNotEqual(self.run_driver('update-metadata',*paths,ok=False).returncode,0)
        paths=self.metadata();j=json.loads(paths[0].read_text());j['assets'][1]['digest']=None;paths[0].write_text(json.dumps(j))
        self.assertNotEqual(self.run_driver('update-metadata',*paths,ok=False).returncode,0)
