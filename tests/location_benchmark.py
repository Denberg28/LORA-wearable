"""Deterministic synthetic stress evidence, not a field accuracy measurement."""
import argparse
import json
import math
import platform
import random
from pathlib import Path

from monitor.field import calibrate, distance_m
from tests.test_field import dataset, site


def run():
    results = {}
    for name, noise, obstruction, missing in (
        ('ideal',0,0,0),('noise_3db',3,0,0),('noise_6db',6,0,0),
        ('body_shadow_15db',3,15,0),('one_receiver_missing',3,0,1),
        ('two_receivers_missing',3,0,2)):
        anchors, rows = dataset(noise=0 if name=='ideal' else 3)
        rows = [r for r in rows if r['split']=='train']
        rng = random.Random(20261111)
        for trial in range(100):
            lat, lon = site(rng.uniform(40,560),rng.uniform(40,560))
            label = {'device':100,'boot':2,'seq':trial+1,'point':f'heldout-{trial}',
                     'lat':lat,'lon':lon,'split':'eval'}
            for i,(ident,a) in enumerate(anchors.items()):
                if i >= len(anchors)-missing:
                    continue
                d=distance_m((lat,lon),(a['lat'],a['lon']))
                rssi=-38-i*2-10*(2.3+i*.15)*math.log10(d)+rng.gauss(0,noise)
                if i==0:rssi-=obstruction
                rows.append({**label,'anchor_id':ident,'rssi':rssi})
        _, results[name] = calibrate(rows,anchors,'synthetic')
    assert results['ideal']['availability']==1
    assert results['ideal']['p95_error_m']<1
    assert results['two_receivers_missing']['availability']==0
    return {'evidence':'SIMULATOR TESTED ONLY','seed':20261111,
            'python':platform.python_version(),'cases':results}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();result=run()
    text=json.dumps(result,indent=2,allow_nan=False)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(text)
    print(text)


if __name__=='__main__':main()
