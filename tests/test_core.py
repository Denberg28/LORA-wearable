import json
import math
from pathlib import Path
import random
import tempfile
import unittest
from monitor.location import estimate
from monitor.model import Store,load_anchors
from monitor.protocol import decode
from monitor.simulate import packet

class ProtocolTests(unittest.TestCase):
    def test_roundtrip_negative_coordinates(self):
        p=decode(json.loads(packet(lat=-13.5,lon=-123.25))['hex'],2761)
        self.assertEqual((p.lat,p.lon),(-13.5,-123.25))
    def test_invalid_packets(self):
        valid=bytearray.fromhex(json.loads(packet())['hex'])
        for offset,value in ((0,0),(2,9),(3,9),(4,0),(10,4),(11,8),(46,1)):
            b=valid.copy();b[offset]=value
            with self.assertRaises(ValueError):decode(b.hex(),2761)
        for b in ('','00','x'*128):
            with self.assertRaises(ValueError):decode(b,2761)
    def test_fuzz(self):
        r=random.Random(7)
        for _ in range(2000):
            b=bytes(r.randrange(256) for _ in range(r.randrange(80)))
            try:decode(b.hex(),2761)
            except ValueError:pass

class StateTests(unittest.TestCase):
    def test_sos_stale_replay_cancel_restart(self):
        with tempfile.TemporaryDirectory() as d:
            db=Path(d)/'state.db';s=Store(db)
            self.assertTrue(s.ingest(packet(active=True,seq=2),100))
            self.assertFalse(s.ingest(packet(active=False,seq=1),200))
            self.assertEqual(s.rows()[0][1],1)
            s.review(100);self.assertEqual(s.rows()[0][-1],1)
            s.db.close();s=Store(db)
            self.assertFalse(s.ingest(packet(active=False,seq=1),300))
            self.assertTrue(s.ingest(packet(active=False,seq=1,boot=2),300))
            self.assertEqual(s.rows()[0][1],0)
            self.assertEqual(s.rows()[0][-1],0)
            s.db.close()
    def test_gps_last_known(self):
        s=Store(':memory:');s.ingest(packet(lat=13,lon=123),100)
        s.ingest(packet(seq=2),200)
        row=s.rows()[0];self.assertEqual(row[3:7],(13,123,100,'GPS'))
    def test_out_of_order_observations_and_allowlist(self):
        anchors={'10':{'lat':13,'lon':123},'11':{'lat':13.001,'lon':123},'12':{'lat':13,'lon':123.001}}
        s=Store(':memory:',anchors=anchors)
        for ident,a in anchors.items():
            s.ingest(packet(origin=int(ident),kind=3,target=100,ref_boot=1,ref_seq=1,rssi=-85,lat=a['lat'],lon=a['lon']),100)
        self.assertEqual(s.rows(),[])
        s.ingest(packet(),101)
        self.assertEqual(s.rows()[0][6],'RSSI estimate')
        self.assertFalse(s.ingest(packet(origin=99,kind=3,target=100,ref_boot=1,ref_seq=1,rssi=-70),102))
        # Different beacons must never mix into a location solution.
        s.ingest(packet(seq=2),103)
        self.assertLess(s.rows()[0][5],103)
    def test_receiver_coverage_is_current_direct_sighting_not_location(self):
        anchors={'10':{'lat':13,'lon':123},'11':{'lat':13.001,'lon':123},
                 '12':{'lat':13,'lon':123.001}}
        s=Store(':memory:',anchors=anchors)
        # Observation may arrive before the referenced status packet.
        self.assertTrue(s.ingest(packet(origin=10,kind=3,seq=1,target=100,
                                        ref_boot=1,ref_seq=1,rssi=-79,lat=0,lon=0),100))
        self.assertEqual(s.receiver_coverage(100,100),[])
        s.ingest(packet(seq=1,lat=None,lon=None),101)
        self.assertEqual(s.rows()[0][3:5],(None,None))
        self.assertEqual([(x[0],x[1]) for x in s.receiver_coverage(100,101)],[(10,-79)])
        self.assertTrue(s.ingest(packet(origin=11,kind=3,seq=1,target=100,
                                        ref_boot=1,ref_seq=1,rssi=-65,lat=90,lon=180),102))
        self.assertEqual([x[0] for x in s.receiver_coverage(100,103)],[11,10])
        self.assertEqual(s.rows()[0][3:5],(None,None))
        # A new status must never display an observation from a previous beacon.
        s.ingest(packet(seq=2,lat=None,lon=None),104)
        self.assertEqual(s.receiver_coverage(100,104),[])
        self.assertTrue(s.ingest(packet(origin=12,kind=3,seq=1,target=100,
                                        ref_boot=1,ref_seq=2,rssi=-82),105))
        self.assertEqual([x[0] for x in s.receiver_coverage(100,105)],[12])
        self.assertEqual(s.receiver_coverage(100,136),[])
        self.assertEqual(s.rows()[0][3:5],(None,None))
        # Receiver identity/coordinate must be allowlisted and observed directly.
        self.assertFalse(s.ingest(packet(origin=99,kind=3,target=100,ref_boot=1,
                                         ref_seq=2,rssi=-60),137))
        s.db.close()

    def test_input_bounds(self):
        s=Store(':memory:')
        for text in ('x'*1025,'[]','null','{"type":"packet"}'):
            with self.assertRaises((ValueError,TypeError)):s.ingest(text)

class LocationTests(unittest.TestCase):
    def test_geometry_and_synthetic_accuracy(self):
        self.assertIsNone(estimate([]))
        self.assertIsNone(estimate([(13,123,-70)]*3))
        samples=[];true_lat,true_lon=13.0003,123.0004
        for lat,lon in ((13,123),(13.001,123),(13,123.001),(13.001,123.001)):
            distance=math.hypot((lat-true_lat)*111320,(lon-true_lon)*111320*math.cos(math.radians(lat)))
            samples.append((lat,lon,-40-27*math.log10(distance)))
        e=estimate(samples)
        self.assertIsNotNone(e);self.assertAlmostEqual(e.lat,true_lat,places=5)
        self.assertAlmostEqual(e.lon,true_lon,places=5);self.assertGreaterEqual(e.uncertainty_m,100)
    def test_collinear_and_invalid(self):
        self.assertIsNone(estimate([(13,123,-70),(13.001,123,-75),(13.002,123,-80)]))
        self.assertIsNone(estimate([(13,123,0),(13.001,123,-80),(13,123.001,-80)]))

if __name__=='__main__':unittest.main()
