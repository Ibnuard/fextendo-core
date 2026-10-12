"""Render UI states using the very same software renderer as the Switch NRO."""
from pathlib import Path
import importlib.util, subprocess, tempfile, os, struct, json
try:
    from PIL import Image
except ImportError:
    Image=None
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('fixtures',ROOT/'tests/test_installer.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
out=ROOT/'build-host/previews';out.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory() as tmp:
    sd=Path(tmp);module.fixture(sd)
    def draw(name, mode='', env=None):
        p=out/(name+'.ppm')
        args=[str(ROOT/'build-host/driver'),'render',str(sd),str(ROOT/'romfs'),str(p)]
        if mode:args.append(mode)
        subprocess.run(args,check=True,env={**os.environ,**(env or {})})
        if Image:
            Image.open(p).save(p.with_suffix('.png'));p.unlink()
    draw('ready');draw('confirmation','confirm');draw('progress','progress');draw('update-unconfigured','error')
    draw('app-update-confirmation','app-confirm');draw('app-update-completed','app-complete')
    draw('hoc-choice',env={'FXP_LOADER':'hoc'})
    subprocess.run([str(ROOT/'build-host/driver'),'install',str(sd),str(ROOT/'romfs')],check=True)
    draw('installed')
    pkg=sd/'atmosphere/package3';data=bytearray(pkg.read_bytes());data[58]=12;pkg.write_bytes(data)
    draw('unsupported')
    data[57:60]=bytes([0,12,1]);struct.pack_into('<I',data,60,0x28d6a2e1);pkg.write_bytes(data)
    draw('ready-1.12.0',env={'FXP_RUNNING_AMS':'1.12.0','FXP_RUNNING_HOS':'23.0.0'})
    audit=json.loads((ROOT/'provenance/ams-1.12.0/submitted-package3-audit.json').read_text())
    data=bytearray.fromhex(audit['header_hex']);pkg.write_bytes(data)
    with pkg.open('r+b') as f:f.truncate(audit['bytes'])
    draw('custom-1.12.0',env={'FXP_RUNNING_AMS':'1.12.0','FXP_RUNNING_HOS':'23.0.0'})
    struct.pack_into('<I',data,36,len(data))
    data[57:60]=bytes([5,9,1]);struct.pack_into('<I',data,60,0xde9b0200);pkg.write_bytes(data)
    draw('ready-1.9.5',env={'FXP_RUNNING_AMS':'1.9.5','FXP_RUNNING_HOS':'20.5.0'})
print(out)
