import copy
import itertools
import json
import math
from pathlib import Path
import random
import tempfile
import unittest

from monitor.field import CaptureWriter, calibrate, distance_m, export_capture
from monitor.location import estimate
from monitor.model import Store, load_anchors
from monitor.simulate import packet


def site(x, y):
    return 13+y/111320, 123+x/(111320*math.cos(math.radians(13)))


def dataset(noise=0):
    anchors = {str(i+10): dict(zip(('lat', 'lon'), site(x, y)))
               for i, (x, y) in enumerate(((0, 0), (600, 0), (0, 600), (600, 600)))}
    train = ((15,15),(585,15),(15,585),(585,585),(20,300),(580,300),(300,20),(300,580))
    heldout = ((100,100),(200,400),(400,200),(500,500),(300,300))
    rng = random.Random(812)
    rows = []
    seq = 0
    for split, places in (('train', train), ('eval', heldout)):
        for point, (x, y) in enumerate(places):
            lat, lon = site(x, y)
            for _ in range(3):
                seq += 1
                for i, (ident, anchor) in enumerate(anchors.items()):
                    d = distance_m((lat, lon), (anchor['lat'], anchor['lon']))
                    rssi = -38-i*2-10*(2.3+i*.15)*math.log10(d)+rng.gauss(0, noise)
                    rows.append({'device':100,'boot':1,'seq':seq,'point':f'{split}-{point}',
                                 'lat':lat,'lon':lon,'split':split,'anchor_id':ident,'rssi':rssi})
    return anchors, rows


class FieldTests(unittest.TestCase):
    def test_capture_exclusive_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'capture.jsonl'
            w=CaptureWriter(p)
            w.append(json.loads(packet()))
            w.close();w.close()
            records=[json.loads(line) for line in p.read_text().splitlines()]
            self.assertEqual([r['type'] for r in records],['session','serial','end'])
            self.assertEqual(records[-1]['events'],1)
            with self.assertRaises(FileExistsError):CaptureWriter(p)

    def test_changed_survey_invalidates_only_derived_rssi(self):
        anchors={'10':{'lat':13,'lon':123},'11':{'lat':13.001,'lon':123},'12':{'lat':13,'lon':123.001}}
        s=Store(':memory:',anchors=anchors)
        s.ingest(packet(),100)
        for ident in anchors:
            s.ingest(packet(origin=int(ident),kind=3,target=100,ref_boot=1,ref_seq=1,rssi=-85),101)
        self.assertEqual(s.rows()[0][6],'RSSI estimate')
        s.ingest(packet(origin=101,lat=13,lon=123),102)
        s.configure_anchors(anchors)
        self.assertEqual(s.rows()[0][6],'RSSI estimate')
        changed=copy.deepcopy(anchors);changed['10']['lat']+=.001
        s.configure_anchors(changed)
        rows={r[0]:r for r in s.rows()}
        self.assertIsNone(rows[100][3]);self.assertEqual(rows[100][1],1)
        self.assertEqual(rows[101][6],'GPS')
        self.assertFalse(s.ingest(packet(active=False),103))
        s.db.close()

    def test_per_receiver_fit_and_unseen_points(self):
        anchors, rows = dataset()
        profiles, report = calibrate(rows, anchors, 'synthetic')
        self.assertEqual(report['reference_gate'], 'PASS')
        self.assertEqual(report['evidence'], 'SIMULATOR TESTED')
        self.assertEqual(report['expected_beacons'], 15)
        self.assertEqual(report['located_beacons'], 15)
        self.assertLess(report['p95_error_m'], 1)
        self.assertAlmostEqual(profiles['10']['calibration']['exponent'], 2.3, places=8)
        self.assertAlmostEqual(profiles['13']['calibration']['rssi_at_1m'], -44, places=8)

    def test_missed_beacons_stay_in_denominator(self):
        anchors, rows = dataset()
        rows.append({'device':100,'boot':1,'seq':1000,'point':'eval-missing',
                     'lat':site(150,150)[0],'lon':site(150,150)[1],'split':'eval',
                     'anchor_id':'','rssi':''})
        _, report = calibrate(rows, anchors, 'field')
        self.assertEqual(report['expected_beacons'], 16)
        self.assertEqual(report['located_beacons'], 15)
        self.assertEqual(report['availability'], 15/16)
        rows += [{**rows[-1], 'seq':1000+i} for i in range(1,10)]
        _, report = calibrate(rows, anchors, 'field')
        self.assertEqual(report['reference_gate'], 'FAIL')

    def test_leakage_duplicates_and_bad_model_rejected(self):
        anchors, rows = dataset()
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            calibrate(rows+[rows[0]], anchors, 'field')
        bad = copy.deepcopy(rows)
        first = next(r for r in rows if r['split'] == 'train')
        for row in bad:
            if row['point'] == 'eval-0':
                row['lat'], row['lon'] = first['lat'], first['lon']
        with self.assertRaisesRegex(ValueError, 'leakage'):
            calibrate(bad, anchors, 'field')
        bad = copy.deepcopy(rows)
        for row in bad:
            row['rssi'] = -60
        with self.assertRaisesRegex(ValueError, 'model outside'):
            calibrate(bad, anchors, 'field')

    def test_capture_exact_beacon_dedup_expiry_and_total_miss(self):
        anchors = {'10': {'lat':13,'lon':123}}
        label = {'device':100,'boot':1,'seq':1,'point':'a','lat':13.001,'lon':123,'split':'eval'}
        truth = {(100,1,1):label,(100,1,2):{**label,'seq':2},(100,1,3):{**label,'seq':3}}
        records = [(1,packet(origin=10,kind=3,target=100,ref_boot=1,ref_seq=1,rssi=-70)),
                   (2,packet(seq=1)),
                   (3,packet(origin=10,kind=3,seq=2,target=100,ref_boot=1,ref_seq=1,rssi=-90)),
                   (4,packet(seq=2)),
                   (35,packet(origin=10,kind=3,seq=3,target=100,ref_boot=1,ref_seq=2,rssi=-60))]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'capture.jsonl'
            p.write_text(''.join(json.dumps({'type':'serial','elapsed':t,'event':json.loads(line)})+'\n'
                                 for t, line in records))
            rows = export_capture(p, truth, anchors)
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[0]['rssi'],-70)
        self.assertEqual(rows[1]['anchor_id'],'')
        self.assertEqual(rows[2]['anchor_id'],'')

    def test_profile_validation(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'anchors.json'
            for value in (float('nan'), float('inf'), 0):
                p.write_text(json.dumps({'10':{'lat':13,'lon':123,'calibration':
                    {'rssi_at_1m':-40,'exponent':value,'sigma_db':6}}}))
                with self.assertRaises(ValueError):
                    load_anchors(p)
            p.write_text(json.dumps({'010': {'lat':13,'lon':123}}))
            with self.assertRaises(ValueError):
                load_anchors(p)

    def test_nonfinite_and_permutation_invariant_solver(self):
        anchors, rows = dataset()
        profiles, _ = calibrate(rows, anchors, 'synthetic')
        beacon = [r for r in rows if r['split']=='eval'][:4]
        samples = [(anchors[r['anchor_id']]['lat'],anchors[r['anchor_id']]['lon'],r['rssi']) for r in beacon]
        models = [profiles[r['anchor_id']]['calibration'] for r in beacon]
        expected = estimate(samples, calibrations=models)
        self.assertIsNotNone(expected)
        for permutation in itertools.permutations(range(4)):
            result = estimate([samples[i] for i in permutation], calibrations=[models[i] for i in permutation])
            self.assertIsNotNone(result)
            self.assertLess(distance_m((result.lat,result.lon),(expected.lat,expected.lon)),.01)
        for v in (float('nan'),float('inf'),-float('inf')):
            bad = samples.copy();bad[0] = (*bad[0][:2],v)
            self.assertIsNone(estimate(bad))

    def test_delayed_observations_cannot_refresh_old_beacon(self):
        anchors = {'10':{'lat':13,'lon':123},'11':{'lat':13.001,'lon':123},'12':{'lat':13,'lon':123.001}}
        s = Store(':memory:',anchors=anchors)
        s.ingest(packet(),100)
        for ident in anchors:
            s.ingest(packet(origin=int(ident),kind=3,target=100,ref_boot=1,ref_seq=1,rssi=-85),131)
        self.assertIsNone(s.rows()[0][3])
        s.db.close()


if __name__ == '__main__':
    unittest.main()
