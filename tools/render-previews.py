"""Render UI states using the very same software renderer as the Switch NRO."""
from pathlib import Path
import importlib.util, subprocess, tempfile
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
    def draw(name, mode=''):
        p=out/(name+'.ppm')
        args=[str(ROOT/'build-host/driver'),'render',str(sd),str(ROOT/'romfs'),str(p)]
        if mode:args.append(mode)
        subprocess.run(args,check=True)
        if Image:
            Image.open(p).save(p.with_suffix('.png'));p.unlink()
    draw('ready');draw('confirmation','confirm');draw('progress','progress');draw('update-unconfigured','error')
    subprocess.run([str(ROOT/'build-host/driver'),'install',str(sd),str(ROOT/'romfs')],check=True)
    draw('installed')
    pkg=sd/'atmosphere/package3';data=bytearray(pkg.read_bytes());data[58]=12;pkg.write_bytes(data)
    draw('unsupported')
print(out)
