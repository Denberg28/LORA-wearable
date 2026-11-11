"""Offline field capture, exact-beacon labeling, calibration and held-out evaluation.

No cloud service or numerical dependency. Capture timestamps are PC observations,
never time-of-arrival ranging data. See docs/FIELD_VALIDATION.md.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import time

from .location import estimate, valid_calibration
from .model import load_anchors
from .protocol import decode

COLUMNS = ('device', 'boot', 'seq', 'point', 'lat', 'lon', 'split', 'anchor_id', 'rssi')
MAX_ROWS = 200000


class CaptureWriter:
    """Exclusive local session file; callers surface I/O errors and close it."""
    def __init__(self, path, network=2761):
        self.network=network;self.started=time.monotonic();self.count=0
        self.file=Path(path).open('x',encoding='utf-8')
        self.file.write(json.dumps({'type':'session','at':time.time(),'network':network,
            'timestamp_kind':'PC receive time; NOT RF time-of-arrival'})+'\n');self.file.flush()

    def append(self, event):
        if self.count >= MAX_ROWS-2:
            raise OSError("session limit reached; start a new capture file")
        if not isinstance(event,dict):
            raise ValueError('serial object required')
        if event.get('type')=='packet':decode(event.get('hex'),self.network)
        self.file.write(json.dumps({'type':'serial','at':time.time(),
            'elapsed':time.monotonic()-self.started,'event':event},allow_nan=False)+'\n')
        self.file.flush();self.count+=1

    def close(self):
        if not self.file.closed:
            try:
                self.file.write(json.dumps({'type':'end','events':self.count,
                    'elapsed':time.monotonic()-self.started})+'\n')
            finally:
                self.file.close()


def ground_position(lat, lon):
    lat, lon = float(lat), float(lon)
    if not all(map(math.isfinite, (lat, lon))) or abs(lat) > 90 or abs(lon) > 180:
        raise ValueError('invalid surveyed coordinates')
    return lat, lon


def distance_m(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    v = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6371008.8 * 2 * math.asin(math.sqrt(min(1, max(0, v))))


def read_truth(path):
    """Independent surveyed labels, not a position inferred from the radio."""
    result = {}
    with Path(path).open(newline='', encoding='utf-8-sig') as f:
        for count, row in enumerate(csv.DictReader(f), 1):
            if count > MAX_ROWS:
                raise ValueError('too many ground-truth rows')
            key = tuple(int(row[k]) for k in ('device', 'boot', 'seq'))
            if not 1 <= key[0] <= 65534 or not all(1 <= v <= 0xffffffff for v in key[1:]):
                raise ValueError('invalid beacon identity')
            lat, lon = ground_position(row['lat'], row['lon'])
            if not row['point'].strip() or row['split'] not in ('train', 'eval') or key in result:
                raise ValueError('duplicate beacon, missing point or invalid train/eval split')
            result[key] = {**dict(zip(('device', 'boot', 'seq'), key)), 'point': row['point'],
                           'lat': lat, 'lon': lon, 'split': row['split']}
    if not result:
        raise ValueError('ground-truth file is empty')
    return result


def export_capture(capture, truth, anchors, network=2761):
    """Keep all labeled trials in the denominator, including total RF misses."""
    status, observations = {}, {}
    with Path(capture).open(encoding='utf-8') as f:
        for count, line in enumerate(f, 1):
            if count > MAX_ROWS or len(line) > 4096:
                raise ValueError('capture limit exceeded; split the session')
            row = json.loads(line)
            if row.get('type') != 'serial':
                continue
            elapsed = float(row['elapsed'])
            if not math.isfinite(elapsed) or elapsed < 0:
                raise ValueError('invalid capture elapsed time')
            event = row['event']
            if event.get('type') != 'packet':
                continue
            p = decode(event.get('hex'), network)
            if p.kind == 1:
                key = p.origin, p.boot, p.seq
                if key in truth:
                    status.setdefault(key, elapsed)
            elif p.kind == 3 and p.observer == p.origin and str(p.origin) in anchors and -140 <= p.rssi <= -10:
                key = p.target, p.ref_boot, p.ref_seq
                if key in truth:
                    observations.setdefault((key, p.origin), (elapsed, p.rssi))
    rows = []
    for key, label in truth.items():
        found = []
        if key in status:
            for anchor in anchors:
                observation = observations.get((key, int(anchor)))
                if observation and abs(observation[0]-status[key]) <= 30:
                    found.append({**label, 'anchor_id': anchor, 'rssi': observation[1]})
        rows.extend(found or [{**label, 'anchor_id': '', 'rssi': ''}])
    return rows


def load_samples(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as f:
        rows = []
        for count, row in enumerate(csv.DictReader(f), 1):
            if count > MAX_ROWS:
                raise ValueError('too many sample rows')
            rows.append(row)
    return rows


def calibrate(rows, anchors, data_kind):
    if len(rows) > MAX_ROWS:
        raise ValueError('too many sample rows')
    if data_kind not in ('synthetic', 'field') or len(anchors) < 3:
        raise ValueError('declare data kind and at least three surveyed anchors')
    beacons, points, used = {}, {}, set()
    for row in rows:
        key = tuple(int(row[k]) for k in ('device', 'boot', 'seq'))
        if not 1 <= key[0] <= 65534 or not all(1 <= v <= 0xffffffff for v in key[1:]):
            raise ValueError('invalid beacon identity')
        pos = ground_position(row['lat'], row['lon'])
        point, split = str(row['point']).strip(), row['split']
        if not point or split not in ('train', 'eval'):
            raise ValueError('point and explicit train/eval split required')
        label = point, split, pos
        if point in points and points[point] != (split, pos):
            raise ValueError('point reused across splits or coordinates')
        points[point] = split, pos
        if key in beacons and beacons[key]['label'] != label:
            raise ValueError('conflicting beacon labels')
        beacon = beacons.setdefault(key, {'label': label, 'samples': {}})
        if str(row['anchor_id']).strip():
            ident = str(int(row['anchor_id']))
            rssi = float(row['rssi'])
            if ident not in anchors or not math.isfinite(rssi) or not -140 <= rssi <= -10:
                raise ValueError('unknown anchor or invalid RSSI')
            if (key, ident) in used:
                raise ValueError('duplicate receiver for one beacon')
            used.add((key, ident));beacon['samples'][ident] = rssi
        elif str(row['rssi']).strip():
            raise ValueError('RSSI without a receiver')
    train_points = {p: v[1] for p, v in points.items() if v[0] == 'train'}
    eval_points = {p: v[1] for p, v in points.items() if v[0] == 'eval'}
    if len(points) > 2000:
        raise ValueError('too many surveyed points; split the session')
    if len(train_points) < 6 or len(eval_points) < 5:
        raise ValueError('need at least six training and five independent evaluation points')
    if any(distance_m(a, b) < 1 for a in train_points.values() for b in eval_points.values()):
        raise ValueError('training/evaluation location leakage within one meter')
    profiles = {}
    for ident, anchor in anchors.items():
        grouped = {}
        raw = []
        origin = ground_position(anchor['lat'], anchor['lon'])
        for beacon in beacons.values():
            point, split, pos = beacon['label']
            if split != 'train' or ident not in beacon['samples']:
                continue
            d = distance_m(origin, pos)
            if not 1 <= d <= 10000:
                raise ValueError('training distance outside 1..10000 m')
            x, y = math.log10(d), beacon['samples'][ident]
            grouped.setdefault(point, []).append((x, y));raw.append((x, y))
        if len(grouped) < 6:
            raise ValueError(f'anchor {ident}: need six distinct training points')
        # One median per surveyed point: repeated packets cannot dominate fit.
        pairs = [(v[0][0], statistics.median(y for _, y in v)) for v in grouped.values()]
        if max(x for x, _ in pairs)-min(x for x, _ in pairs) < .6:
            raise ValueError(f'anchor {ident}: training distances must span at least 4x')
        xm, ym = statistics.mean(x for x, _ in pairs), statistics.mean(y for _, y in pairs)
        slope = sum((x-xm)*(y-ym) for x, y in pairs)/sum((x-xm)**2 for x, _ in pairs)
        intercept = ym-slope*xm
        sigma = max(2, math.sqrt(statistics.mean((y-intercept-slope*x)**2 for x, y in raw)))
        model = {'rssi_at_1m': intercept, 'exponent': -slope/10, 'sigma_db': sigma,
                 'training_points': len(pairs), 'samples': len(raw), 'data_kind': data_kind,
                 'min_distance_m': 10**min(x for x, _ in pairs),
                 'max_distance_m': 10**max(x for x, _ in pairs)}
        if not valid_calibration(model):
            raise ValueError(f'anchor {ident}: model outside supported bounds')
        profiles[ident] = {**anchor, 'calibration': model}
    errors, trials, indicative_misses, extrapolated = [], 0, 0, 0
    for beacon in beacons.values():
        _, split, pos = beacon['label']
        if split != 'eval':
            continue
        trials += 1
        samples, models = [], []
        for ident, rssi in sorted(beacon['samples'].items()):
            a = profiles[ident]
            samples.append((float(a['lat']), float(a['lon']), rssi));models.append(a['calibration'])
        result = estimate(samples, calibrations=models)
        if result:
            error = distance_m(pos, (result.lat, result.lon));errors.append(error)
            indicative_misses += error > result.uncertainty_m
            extrapolated += any(not m['min_distance_m'] <= distance_m(pos, (s[0], s[1])) <= m['max_distance_m']
                                for s, m in zip(samples, models))
    ordered = sorted(errors)
    p95 = ordered[max(0, math.ceil(.95*len(ordered))-1)] if ordered else None
    median = statistics.median(errors) if errors else None
    availability = len(errors)/trials if trials else 0
    passed = availability >= .9 and median is not None and median <= 100 and p95 <= 250
    report = {'data_kind': data_kind,
              'evidence': 'SIMULATOR TESTED' if data_kind == 'synthetic' else 'FIELD DATA EVALUATED; operational HIL still required',
              'training_points': len(train_points), 'heldout_points': len(eval_points),
              'expected_beacons': trials, 'located_beacons': len(errors), 'availability': availability,
              'median_error_m': median, 'p95_error_m': p95, 'max_error_m': max(errors) if errors else None,
              'outside_indicative_radius': indicative_misses, 'extrapolated_beacons': extrapolated,
              'reference_targets': {'availability': .9, 'median_error_m': 100, 'p95_error_m': 250},
              'reference_gate': 'PASS' if passed else 'FAIL',
              'warning': 'Targets are prototype engineering criteria, not guaranteed accuracy. Indicative radii are not confidence bounds.'}
    return profiles, report


def capture(port_name, output, seconds, network):
    import serial
    if not math.isfinite(seconds) or not 0 < seconds <= 86400:
        raise ValueError('capture seconds must be within 0..86400')
    count = rejected = 0
    # Open the port first; a connection failure must not create an empty report.
    with serial.Serial(port_name, 115200, timeout=.2) as port, Path(output).open('x', encoding='utf-8') as f:
        started = time.monotonic()
        f.write(json.dumps({'type': 'session', 'at': time.time(), 'network': network,
                            'timestamp_kind': 'PC receive time; NOT RF time-of-arrival'})+'\n')
        buf = bytearray();oversized = False
        try:
            while time.monotonic()-started < seconds and count < MAX_ROWS-2:
                for byte in port.read(256):
                    if byte != 10:
                        if len(buf) < 1024:
                            buf.append(byte)
                        else:
                            oversized = True
                        continue
                    try:
                        if oversized:
                            raise ValueError('oversized serial event')
                        event = json.loads(buf.decode('ascii'))
                        if not isinstance(event, dict):
                            raise ValueError('serial object required')
                        if event.get('type') == 'packet':
                            decode(event.get('hex'), network)
                        f.write(json.dumps({'type': 'serial', 'at': time.time(),
                                            'elapsed': time.monotonic()-started, 'event': event})+'\n')
                        f.flush();count += 1
                    except (UnicodeError, ValueError, TypeError):
                        rejected += 1
                    buf.clear();oversized = False
        except KeyboardInterrupt:
            pass
        f.write(json.dumps({'type': 'end', 'events': count, 'rejected': rejected,
                            'partial_bytes': len(buf), 'elapsed': time.monotonic()-started})+'\n')
    return {'events': count, 'rejected': rejected}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    rec = commands.add_parser('record');rec.add_argument('--port', required=True)
    rec.add_argument('--output', type=Path, required=True);rec.add_argument('--seconds', type=float, default=600)
    rec.add_argument('--network', type=int, default=2761)
    exp = commands.add_parser('export');exp.add_argument('--capture', type=Path, required=True)
    exp.add_argument('--truth', type=Path, required=True);exp.add_argument('--anchors', type=Path, required=True)
    exp.add_argument('--output', type=Path, required=True);exp.add_argument('--network', type=int, default=2761)
    cal = commands.add_parser('calibrate');cal.add_argument('--samples', type=Path, required=True)
    cal.add_argument('--anchors', type=Path, required=True);cal.add_argument('--report', type=Path, required=True)
    cal.add_argument('--output-anchors', type=Path, required=True)
    cal.add_argument('--data-kind', choices=('synthetic', 'field'), required=True)
    args = parser.parse_args()
    try:
        if args.command == 'record':
            print(json.dumps(capture(args.port, args.output, args.seconds, args.network)))
        elif args.command == 'export':
            rows = export_capture(args.capture, read_truth(args.truth), load_anchors(args.anchors), args.network)
            with args.output.open('x', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=COLUMNS);writer.writeheader();writer.writerows(rows)
            print(f'Exported {len(rows)} rows; missing receptions retained as empty receiver rows')
        else:
            profiles, report = calibrate(load_samples(args.samples), load_anchors(args.anchors), args.data_kind)
            report['sample_sha256'] = hashlib.sha256(args.samples.read_bytes()).hexdigest()
            report['anchors_sha256'] = hashlib.sha256(args.anchors.read_bytes()).hexdigest()
            if args.output_anchors.exists():
                raise ValueError('refusing to replace an existing anchor profile')
            with args.report.open('x', encoding='utf-8') as f:
                json.dump(report, f, indent=2, allow_nan=False);f.write('\n')
            print(json.dumps(report, indent=2))
            if report['reference_gate'] != 'PASS' or args.data_kind != 'field':
                raise ValueError('deployment profile withheld: requires passing held-out FIELD data')
            with args.output_anchors.open('x', encoding='utf-8') as f:
                json.dump(profiles, f, indent=2, allow_nan=False);f.write('\n')
    except (OSError, ValueError, KeyError, TypeError) as e:
        parser.exit(2, f'Field tool: {e}\n')


if __name__ == '__main__':
    main()
