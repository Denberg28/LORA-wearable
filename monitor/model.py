import json
import hashlib
import math
import sqlite3
import time
from .protocol import decode
from .location import estimate, valid_calibration

class Store:
    def __init__(self, path, network=2761, anchors=None):
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS devices(id INTEGER PRIMARY KEY, boot INTEGER, seq INTEGER,
          active INTEGER, seen REAL, lat REAL, lon REAL, fix_time REAL, method TEXT, uncertainty REAL,
          reviewed INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS events(at REAL, device INTEGER, active INTEGER, boot INTEGER, seq INTEGER);
        CREATE TABLE IF NOT EXISTS ordering(id INTEGER PRIMARY KEY, boot INTEGER, seq INTEGER);
        CREATE TABLE IF NOT EXISTS observations(target INTEGER,boot INTEGER,seq INTEGER,anchor INTEGER,
          rssi REAL,at REAL,PRIMARY KEY(target,boot,seq,anchor));
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT);
        ''')
        self.network = network
        self.configure_anchors(anchors or {})

    def configure_anchors(self, anchors):
        fingerprint=hashlib.sha256(json.dumps(anchors,sort_keys=True,allow_nan=False).encode()).hexdigest()
        old=self.db.execute("SELECT value FROM metadata WHERE key='anchors'").fetchone()
        with self.db:
            if old is None or old[0]!=fingerprint:
                # A different survey/model invalidates derived positions, not GPS or SOS.
                self.db.execute('DELETE FROM observations')
                self.db.execute("UPDATE devices SET lat=NULL,lon=NULL,fix_time=NULL,method='unknown',uncertainty=NULL WHERE method='RSSI estimate'")
                self.db.execute("INSERT OR REPLACE INTO metadata VALUES('anchors',?)",(fingerprint,))
        self.anchors=json.loads(json.dumps(anchors))

    def ingest(self, line, now=None):
        now = time.time() if now is None else now
        if len(line) > 1024:
            raise ValueError('serial line too long')
        event = json.loads(line)
        if not isinstance(event, dict):
            raise ValueError('serial object required')
        if event.get('type') != 'packet':
            return False
        p = decode(event.get('hex'), self.network)
        if p.kind == 2:
            return False
        with self.db:
            old = self.db.execute('SELECT boot,seq FROM ordering WHERE id=?', (p.origin,)).fetchone()
            if old and (p.boot, p.seq) <= old:
                return False
            if p.kind == 3:
                # Trust only surveyed allowlisted coordinates, never a packet's self-reported position.
                anchor = self.anchors.get(str(p.origin))
                if not anchor or p.observer != p.origin or not -140 <= p.rssi <= -10:
                    return False
                self.db.execute('INSERT OR REPLACE INTO observations VALUES(?,?,?,?,?,?)',
                                (p.target,p.ref_boot,p.ref_seq,p.origin,p.rssi,now))
                self.db.execute('DELETE FROM observations WHERE at<?', (now-60,))
                self.db.execute('INSERT OR REPLACE INTO ordering VALUES(?,?,?)', (p.origin,p.boot,p.seq))
                self._locate(p.target, p.ref_boot, p.ref_seq, now)
                return True
            existing = self.db.execute('SELECT active FROM devices WHERE id=?',(p.origin,)).fetchone()
            changed = existing is None or existing[0] != bool(p.flags & 1)
            lat, lon, fixed, method = (p.lat,p.lon,now-p.age,'GPS') if p.flags & 2 else (None,None,None,'unknown')
            self.db.execute('''INSERT INTO devices(id,boot,seq,active,seen,lat,lon,fix_time,method,uncertainty,reviewed)
              VALUES(?,?,?,?,?,?,?,?,?,NULL,0) ON CONFLICT(id) DO UPDATE SET boot=excluded.boot,
              seq=excluded.seq,active=excluded.active,seen=excluded.seen,
              lat=COALESCE(excluded.lat,devices.lat),lon=COALESCE(excluded.lon,devices.lon),
              fix_time=COALESCE(excluded.fix_time,devices.fix_time),
              method=CASE WHEN excluded.lat IS NULL THEN devices.method ELSE excluded.method END,
              uncertainty=CASE WHEN excluded.lat IS NULL THEN devices.uncertainty ELSE NULL END,
              reviewed=CASE WHEN devices.active!=excluded.active THEN 0 ELSE devices.reviewed END''',
              (p.origin,p.boot,p.seq,bool(p.flags&1),now,lat,lon,fixed,method))
            self.db.execute('INSERT OR REPLACE INTO ordering VALUES(?,?,?)',(p.origin,p.boot,p.seq))
            if changed:
                self.db.execute('INSERT INTO events VALUES(?,?,?,?,?)',(now,p.origin,bool(p.flags&1),p.boot,p.seq))
            self._locate(p.origin,p.boot,p.seq,now)
            return True

    def _locate(self, device, boot, seq, now):
        row = self.db.execute('SELECT boot,seq,method,fix_time,seen FROM devices WHERE id=?',(device,)).fetchone()
        if not row or row[:2] != (boot,seq) or not 0<=now-row[4]<=30 or (row[2]=='GPS' and row[3] is not None and now-row[3]<=30):
            return
        samples=[];models=[]
        for anchor,rssi in self.db.execute('SELECT anchor,rssi FROM observations WHERE target=? AND boot=? AND seq=? AND at BETWEEN ? AND ? ORDER BY anchor',(device,boot,seq,now-30,now)):
            a=self.anchors.get(str(anchor))
            if a is None:continue
            samples.append((float(a['lat']),float(a['lon']),rssi))
            models.append(a.get('calibration',{'rssi_at_1m':-40,'exponent':2.7,'sigma_db':6}))
        result=estimate(samples,calibrations=models)
        if result:
            self.db.execute('UPDATE devices SET lat=?,lon=?,fix_time=?,method=?,uncertainty=? WHERE id=?',
                (result.lat,result.lon,row[4],'RSSI estimate',result.uncertainty_m,device))

    def receiver_coverage(self, device, now=None):
        """Direct receiver sightings for the latest wearable beacon, not a position.

        One or two receivers can guide a search but do not establish range,
        bearing, or a wearable coordinate. No sightings from older beacons mix.
        """
        now = time.time() if now is None else now
        state = self.db.execute('SELECT boot,seq FROM devices WHERE id=?', (device,)).fetchone()
        if not state:
            return []
        heard = self.db.execute(
            '''SELECT anchor,rssi,at FROM observations
               WHERE target=? AND boot=? AND seq=? AND at BETWEEN ? AND ?
               ORDER BY rssi DESC,anchor ASC''',
            (device,state[0],state[1],now-30,now)).fetchall()
        result = []
        for ident, rssi, received in heard:
            anchor = self.anchors.get(str(ident))
            if anchor:
                result.append((ident, float(rssi), max(0.0, now-received),
                               float(anchor['lat']), float(anchor['lon'])))
        return result

    def rows(self):
        return self.db.execute('SELECT id,active,seen,lat,lon,fix_time,method,uncertainty,reviewed FROM devices ORDER BY active DESC,id').fetchall()

    def review(self, device):
        with self.db:
            self.db.execute('UPDATE devices SET reviewed=1 WHERE id=?',(device,))

def load_anchors(path):
    data=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data,dict) or len(data)>64:
        raise ValueError('anchors must be an object with at most 64 entries')
    for key,a in data.items():
        if not 1<=int(key)<=65534 or str(int(key))!=key or not isinstance(a,dict):
            raise ValueError('anchor ID')
        lat,lon=float(a['lat']),float(a['lon'])
        if not math.isfinite(lat) or not math.isfinite(lon) or abs(lat)>90 or abs(lon)>180:
            raise ValueError('anchor coordinates')
        if 'calibration' in a and not valid_calibration(a['calibration']):
            raise ValueError('invalid anchor calibration')
    return data

