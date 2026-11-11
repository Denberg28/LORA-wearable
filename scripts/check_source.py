from pathlib import Path
import re
import subprocess

root=Path(__file__).resolve().parents[1]
tracked=subprocess.check_output(['git','ls-files','-z'],cwd=root,text=True).split('\0')
for name in filter(None,tracked):
    if name=='firmware/LoRaWearable/Config.h' or name.startswith('private/') or '.sqlite3' in name:
        raise SystemExit('Private material is tracked: '+name)
    text=(root/name).read_text(encoding='utf-8')
    pattern=r'gh[pousr]_[A-Za-z0-9]{30,}|' + '-----BEGIN ' + r'.*PRIVATE KEY' + '-----'
    if re.search(pattern,text):
        raise SystemExit('Possible secret in '+name)
print('PASS: tracked file/secret checks')
