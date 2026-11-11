"""Bounded RSSI multilateration. An indicative estimate, never a GPS fix."""
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Estimate:
    lat: float
    lon: float
    uncertainty_m: float
    residual_m: float


def valid_calibration(model):
    """Reject unusable profiles rather than substituting a different model."""
    try:
        a, n, sigma = (float(model[k]) for k in ('rssi_at_1m', 'exponent', 'sigma_db'))
        return all(map(math.isfinite, (a, n, sigma))) and -90 <= a <= -10 and 1.5 <= n <= 6 and 2 <= sigma <= 20
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


def _solve(aa, ab, bb, ac, bc):
    det = aa * bb - ab * ab
    if det <= 0:
        return None
    return (ac * bb - bc * ab) / det, (bc * aa - ac * ab) / det


def estimate(samples, rssi_at_1m=-40.0, exponent=2.7, calibrations=None):
    """All samples must be direct receivers of the SAME beacon.

    Per-receiver profiles are optional, in sample order. Fit in dB space so a
    distant receiver's squared range cannot dominate. No temporal smoothing or
    discarded outliers: inconsistent data returns unknown. Bounds cap work.
    """
    if not 3 <= len(samples) <= 64:
        return None
    default = {'rssi_at_1m': rssi_at_1m, 'exponent': exponent, 'sigma_db': 6.0}
    models = calibrations if calibrations is not None else [default] * len(samples)
    if len(models) != len(samples) or not all(valid_calibration(m) for m in models):
        return None
    try:
        if any(len(s) != 3 or not all(math.isfinite(float(v)) for v in s) for s in samples):
            return None
        samples = [tuple(map(float, s)) for s in samples]
    except (TypeError, ValueError, OverflowError):
        return None
    if any(abs(lat) > 90 or abs(lon) > 180 or not -140 <= rssi <= -10 for lat, lon, rssi in samples):
        return None
    lat0 = sum(s[0] for s in samples) / len(samples)
    lon0 = sum(s[1] for s in samples) / len(samples)
    scale = 111320 * math.cos(math.radians(lat0))
    if abs(scale) < 1000:
        return None
    points = []
    for (lat, lon, rssi), m in zip(samples, models):
        if abs(lon - lon0) > .2 or abs(lat - lat0) > .2:
            return None
        a, n, sigma = (float(m[k]) for k in ('rssi_at_1m', 'exponent', 'sigma_db'))
        distance = 10 ** ((a - rssi) / (10 * n))
        if not 1 <= distance <= 10000:
            return None
        points.append(((lon - lon0) * scale, (lat - lat0) * 111320, distance, rssi, a, n, sigma))
    points.sort()
    # Translation/reference-invariant geometry and linear initial position.
    aa = sum(p[0] ** 2 for p in points)
    ab = sum(p[0] * p[1] for p in points)
    bb = sum(p[1] ** 2 for p in points)
    if aa * bb - ab * ab <= .005 * max((aa + bb) ** 2, 1):
        return None
    span = max(math.hypot(a[0]-b[0], a[1]-b[1]) for a in points for b in points)
    if span < 10:
        return None
    c = [p[0] ** 2 + p[1] ** 2 - p[2] ** 2 for p in points]
    cm = sum(c) / len(c)
    linear = _solve(4*aa, 4*ab, 4*bb,
                    sum(2*p[0]*(v-cm) for p, v in zip(points, c)),
                    sum(2*p[1]*(v-cm) for p, v in zip(points, c)))
    bound = max(500, span * 3)

    def evaluate(x, y):
        residuals, jacobian = [], []
        for px, py, _, rssi, a, n, sigma in points:
            dx, dy = x-px, y-py
            r2 = max(dx*dx+dy*dy, 1)
            residuals.append((a-5*n*math.log10(r2)-rssi)/sigma)
            k = -10*n/(math.log(10)*r2*sigma)
            jacobian.append((k*dx, k*dy))
        return sum(r*r for r in residuals), residuals, jacobian

    starts = [(0.0, 0.0)] + ( [linear] if linear and math.hypot(*linear) <= bound else [] )
    # Fixed number of starts/iterations, including interior starts near receivers.
    starts += [(p[0]*.8, p[1]*.8) for p in points[:8]]
    best = None
    for x, y in starts:
        damping = .001
        for _ in range(35):
            cost, residuals, jac = evaluate(x, y)
            jaa = sum(j[0]**2 for j in jac)
            jab = sum(j[0]*j[1] for j in jac)
            jbb = sum(j[1]**2 for j in jac)
            step = _solve(jaa+damping, jab, jbb+damping,
                          -sum(r*j[0] for r, j in zip(residuals, jac)),
                          -sum(r*j[1] for r, j in zip(residuals, jac)))
            if step is None:
                break
            nx, ny = x+step[0], y+step[1]
            if math.hypot(nx, ny) <= bound and evaluate(nx, ny)[0] < cost:
                x, y = nx, ny
                damping = max(damping/3, 1e-12)
                if math.hypot(*step) < .001:
                    break
            else:
                damping *= 10
        candidate = evaluate(x, y)[0], x, y
        if best is None or candidate < best:
            best = candidate
    cost, x, y = best
    _, residuals, jac = evaluate(x, y)
    jaa = sum(j[0]**2 for j in jac)
    jab = sum(j[0]*j[1] for j in jac)
    jbb = sum(j[1]**2 for j in jac)
    det = jaa*jbb-jab*jab
    if det <= .001 * max((jaa+jbb)**2, 1e-30):
        return None
    # Do not hide inconsistent receiver measurements behind a good average fit.
    if math.sqrt(cost/len(points)) > 2.5 or max(map(abs, residuals)) > 3.5:
        return None
    residual = math.sqrt(sum((math.hypot(x-p[0], y-p[1])-p[2])**2 for p in points)/len(points))
    if residual > max(100, span) or math.hypot(x, y) > bound:
        return None
    # Local conditioning term plus a large model-error floor. This is NOT a
    # calibrated confidence interval and cannot bound multipath/body shielding.
    weak = ((jaa+jbb)-math.hypot(jaa-jbb, 2*jab))/2
    if weak <= 0:
        return None
    uncertainty = max(100, residual*2, max(p[2] for p in points)*.75, 2/math.sqrt(weak))
    lat, lon = lat0+y/111320, lon0+x/scale
    if abs(lat)>90 or abs(lon)>180:
        return None
    return Estimate(lat, lon, uncertainty, residual)
