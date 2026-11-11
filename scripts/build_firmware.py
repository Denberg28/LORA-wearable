"""Compile the real XIAO BSP. Default artifacts intentionally cannot transmit."""
import argparse
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser()
    p.add_argument('--cli',default='arduino-cli');p.add_argument('--config-file')
    p.add_argument('--device-config',type=Path,help='private Config.h; compiles one provisioned target')
    a=p.parse_args()
    for role,name,ident in [(1,'wearable',100),(2,'relay',10),(3,'base',1),(1,'storage-init',100)]:
        if a.device_config and role!=1:break
        name=a.device_config.stem if a.device_config else name
        stage=ROOT/'build'/'sketches'/name/'LoRaWearable'
        stage.mkdir(parents=True,exist_ok=True)
        for path in (ROOT/'firmware'/'LoRaWearable').glob('*'):
            if path.name!='Config.h':shutil.copy2(path,stage/path.name)
        config=a.device_config.read_text() if a.device_config else (stage/'Config.example.h').read_text().replace('DEVICE_ROLE 1',f'DEVICE_ROLE {role}').replace('DEVICE_ID 100',f'DEVICE_ID {ident}')
        if name=='storage-init':config=config.replace('INITIALIZE_NEW_STORAGE false','INITIALIZE_NEW_STORAGE true')
        (stage/'Config.h').write_text(config)
        cmd=[a.cli]
        if a.config_file:cmd+=['--config-file',a.config_file]
        cmd+=['compile','--fqbn','Seeeduino:nrf52:xiaonRF52840','--warnings','all','--output-dir',str(ROOT/'build'/'firmware'/name),str(stage)]
        subprocess.run(cmd,check=True)

if __name__=='__main__':main()

