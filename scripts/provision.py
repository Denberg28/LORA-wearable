"""Generate private deployment configs; RF settings must be deliberately selected."""
import argparse
import json
from pathlib import Path
import secrets
import os

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--frequency',type=float,required=True)
    p.add_argument('--power',type=int,default=10)
    p.add_argument('--confirm-region',action='store_true',required=True)
    p.add_argument('--wearables',type=int,default=1)
    p.add_argument('--relays',type=int,default=3)
    p.add_argument('--network',type=int,default=2761)
    p.add_argument('--out',type=Path,default=Path('private'))
    a=p.parse_args()
    if not 862<=a.frequency<=930 or not -9<=a.power<=22 or not 1<=a.network<=65534 or not 1<=a.wearables<=20 or not 0<=a.relays<=20:
        p.error('unsupported frequency, power, network or device count')
    a.out.mkdir(parents=True,exist_ok=True)
    if any(a.out.iterdir()):p.error('output must be empty; preserve existing keys/configs')
    os.chmod(a.out,0o700)
    key=secrets.token_bytes(32)
    example=(Path(__file__).resolve().parents[1]/'firmware/LoRaWearable/Config.example.h').read_text()
    devices=[('base',3,1)]+[(f'wearable-{100+i}',1,100+i) for i in range(a.wearables)]+[(f'relay-{10+i}',2,10+i) for i in range(a.relays)]
    for name,role,ident in devices:
        text=example.replace('#define DEVICE_ROLE 1',f'#define DEVICE_ROLE {role}').replace('#define DEVICE_ID 100',f'#define DEVICE_ID {ident}')
        text=text.replace('#define NETWORK_ID 2761',f'#define NETWORK_ID {a.network}')
        text=text.replace('REGION_CONFIRMED false','REGION_CONFIRMED true').replace('KEY_PROVISIONED false','KEY_PROVISIONED true')
        text=text.replace('RADIO_MHZ 915.0f',f'RADIO_MHZ {a.frequency:.3f}f').replace('RADIO_DBM 10',f'RADIO_DBM {a.power}')
        text=text.replace('NETWORK_KEY[32] = {0}', 'NETWORK_KEY[32] = {'+','.join(f'0x{x:02x}' for x in key)+'}')
        path=a.out/f'{name}.h';path.write_text(text);os.chmod(path,0o600)
    (a.out/'anchors.json').write_text('{}\n')
    print(f'Created {len(devices)} private configurations. Survey relays; edit their ANCHOR settings and anchors.json before location testing.')

if __name__=='__main__':main()
