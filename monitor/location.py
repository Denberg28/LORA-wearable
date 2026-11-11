"""Calibrated RSSI multilateration: deliberately conservative, never GPS."""
import math
from dataclasses import dataclass

@dataclass(frozen=True)
class Estimate:
    lat: float
    lon: float
    uncertainty_m: float
    residual_m: float

def estimate(samples, rssi_at_1m=-40.0, exponent=2.7):
    # samples: (lat, lon, direct RSSI). All must refer to the SAME beacon.
    if len(samples) < 3 or not 1.5 <= exponent <= 6 or not -90 <= rssi_at_1m <= -10:
        return None
    lat0 = sum(s[0] for s in samples) / len(samples)
    lon0 = sum(s[1] for s in samples) / len(samples)
    scale = 111320 * math.cos(math.radians(lat0))
    if abs(scale) < 1000:
        return None
    points = []
    for lat, lon, rssi in samples:
        if not -140 <= rssi <= -10 or abs(lon - lon0) > .2 or abs(lat - lat0) > .2:
            return None
        distance = 10 ** ((rssi_at_1m - rssi) / (10 * exponent))
        if not 1 <= distance <= 10000:
            return None
        points.append(((lon - lon0) * scale, (lat - lat0) * 111320, distance))
    # Linearized least squares, with geometry checks before using the solution.
    x0, y0, d0 = points[0]
    aa = ab = bb = ac = bc = 0.0
    for x, y, d in points[1:]:
        a, b = 2 * (x - x0), 2 * (y - y0)
        c = d0*d0 - d*d + x*x - x0*x0 + y*y - y0*y0
        aa += a*a; ab += a*b; bb += b*b; ac += a*c; bc += b*c
    det = aa*bb - ab*ab
    if det <= 0 or det / max((aa+bb)**2, 1) < .005:
        return None
    x, y = (ac*bb-bc*ab)/det, (bc*aa-ac*ab)/det
    residual = math.sqrt(sum((math.hypot(x-a, y-b)-d)**2 for a,b,d in points)/len(points))
    span = max(math.hypot(a-x0, b-y0) for a,b,_ in points)
    if span < 10 or residual > max(100, span) or math.hypot(x,y) > max(500, span*3):
        return None
    uncertainty = max(100, residual*2, max(p[2] for p in points)*.75)
    return Estimate(lat0+y/111320, lon0+x/scale, uncertainty, residual)
