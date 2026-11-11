"""Source + disabled-radio firmware package, with commit provenance and hashes."""
from pathlib import Path
import hashlib
import json
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
VERSION=(ROOT/'VERSION').read_text().strip()

def main():
    out=ROOT/'dist';out.mkdir(exist_ok=True)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    tracked=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    sources=[ROOT/p for p in tracked if p and not p.startswith('.github/')]
    binary=list((ROOT/'build'/'firmware').glob('*/*'))
    required={'base','wearable','relay'}
    if {p.parent.name for p in binary if p.suffix=='.hex'}!=required:
        raise SystemExit('Required real firmware builds missing')
    if any((ROOT/'build'/'sketches').rglob('Config.h')):
        for p in (ROOT/'build'/'sketches').rglob('Config.h'):
            if 'KEY_PROVISIONED true' in p.read_text():
                raise SystemExit('Refusing to distribute provisioned firmware/config')
    manifest={'version':VERSION,'commit':commit,'tier':'TEST CANDIDATE','hardware_validation':'BLOCKED',
              'radio':'disabled until privately provisioned','files':{}}
    target=out/f'LORA-wearable-{VERSION}-test-candidate.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        for f in sources+binary:
            if not f.is_file():continue
            relative=f.relative_to(ROOT).as_posix()
            if f.name=='Config.h' or relative.startswith('private/') or f.suffix in ('.sqlite3','.pyc'):
                raise SystemExit(f'Unsafe package file: {relative}')
            data=f.read_bytes();manifest['files'][relative]=hashlib.sha256(data).hexdigest();z.writestr(relative,data)
        z.writestr('MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
    (out/'SHA256SUMS.txt').write_text(hashlib.sha256(target.read_bytes()).hexdigest()+'  '+target.name+'\n')
    print(target)

if __name__=='__main__':main()
