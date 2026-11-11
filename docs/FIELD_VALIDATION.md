# Measure location and communication performance

The supported architecture is a reliable-alert prototype with independent
location evidence: optional current GNSS, otherwise coarse calibrated RSSI
multilateration, otherwise direct receiver coverage, otherwise unknown/last
known. Relay hops extend delivery but do not create range or bearing samples.
Frequency hopping is not implemented and would not itself supply position.

Semtech distinguishes [RSSI estimation](https://www.semtech.com/loracloud-documentation/gls.html)
from [fine-timestamp TDOA](https://blog.semtech.com/using-the-lora-sx1303-fine-timestamp-feature-to-enhance-asset-tracking).
This project implements RSSI, not TDOA. PC clocks, USB timestamps and firmware
`millis()` are not comparable fine RF timestamps. The existing SX1262 receiver
path provides no demonstrated TDOA timing chain.

## Concrete prototype targets

These are engineering targets for controlled evaluation, not validated safety
or accuracy guarantees. Existing alert/HIL criteria in HIL.md also apply.

- At least 6 distinct training positions per receiver, with distances spanning
  at least 4x; at least 5 separately surveyed evaluation positions. Prefer many
  more points, different days, body orientations, obstacles and realistic motion.
- Never reuse a location across training/evaluation, even under another label.
  The tool rejects shared point labels and coordinates within one meter.
- Evaluate every expected beacon, including missed receptions. Prototype
  location target: >=90% position availability, median error <=100 m,
  95th-percentile error <=250 m. Failed targets withhold a deployment profile.
- Report SOS activation-to-base latency and receipt return separately from
  position availability. A missing location must never suppress an SOS alert.
  Use the 100-trial delivery/latency procedure in HIL.md; no measured result exists yet.
- Current estimates require >=3 non-collinear direct surveyed receivers.
  Four or more provide redundancy; fewer receivers remain coverage evidence.

## Capture on Windows

Provision and commission the hardware using README.md and STORAGE.md. Survey
receiver locations independently. Load `private/anchors.json` with the monitor's
**Load receivers** button. Select the gateway COM port and connect. Click
**Record field session** and choose a new local `.jsonl` file; click **Stop
recording** when done. This works in the packaged Windows executable. The
recording contains coordinates/identities and should remain private.

Alternatively, with Python and requirements installed, close the monitor so
only the recorder owns the COM port:

```powershell
py -3 -m monitor.field record --port COM4 --seconds 600 --output private/base-session.jsonl
```

Capture the wearable's USB on a second COM port in another terminal when doing
controlled trials. Its `tx` diagnostics identify device/generation/sequence,
SOS state, local uptime and radio transmission result. `ok:1` means the local
radio call completed, not that another device received the frame. Include
unsuccessful/absent base receptions in expected trials. USB-powered measurements
do not establish wearable battery endurance. Capture files preserve PC receive
times and monotonic elapsed times; neither is RF time of arrival.

## Independently label the exact beacons

Create `private/truth.csv` with these columns:

```csv
device,boot,seq,point,lat,lon,split
```

Each row identifies one expected wearable beacon from its transmission log and
the surveyed wearer position at that transmission. `point` is a stable survey
site name; `split` is `train` or `eval`. Use the actual boot/sequence values and
real survey coordinates, including expected beacons the base did not receive.
Do not derive ground truth from the estimator, a receiver's location, or an
assumed sequence. Wearer movement during labeling invalidates stationary labels.

Export accepted direct observations, grouped by exact beacon:

```powershell
py -3 -m monitor.field export --capture private/base-session.jsonl --truth private/truth.csv --anchors private/anchors.json --output private/samples.csv
py -3 -m monitor.field calibrate --samples private/samples.csv --anchors private/anchors.json --data-kind field --report private/location-report.json --output-anchors private/calibrated-anchors.json
```

Export keeps an empty receiver row for missing trials, so misses cannot silently
improve availability. Receivers must be allowlisted; replay duplicates collapse;
observation/status reception times must be within 30 s. Only a trusted gateway
has authenticated RF frames: the PC tools check packet shape, not HMAC again.
Files are created exclusively; existing captures, profiles and reports are not
overwritten. If calibration/evaluation fails, inspect the report, collect more
representative evidence, and rerun to new paths. `--data-kind synthetic` can
produce a report but deliberately cannot write a deployment profile.

The tool fits per-receiver log-distance intercept/exponent using one median
RSSI per training site, estimates residual signal variation, and evaluates on
held-out beacon labels. Profiles are rejected outside supported propagation
bounds. Loading a changed survey/profile invalidates old RSSI positions and
receiver observations; SOS, event history, ordering and GPS remain intact.

## What software evidence actually shows

Run `python -m tests.location_benchmark` for the deterministic 600 m-square
synthetic topology. Results are in `docs/evidence/rc4-synthetic-location.json`.
Ideal and 3 dB random-noise scenarios meet the reference targets; 6 dB noise,
a 15 dB single-receiver body-shadow scenario, and losing one of four receivers
do not. Losing two receivers yields no position. Some simulated errors exceed
the indicative plotted radius. These failures are retained in the evidence.

Consequently, this candidate does **not** establish dependable location through
body shielding or obstacles. The large uncertainty indicator is not a confidence
region or guaranteed search radius. Test actual antenna placement, body
orientation, receiver geometry and propagation before adopting the fallback.
If measured RSSI performance fails the targets, keep coverage-only/GNSS behavior
and revisit receiver placement or hardware; do not tune against held-out sites
and then report them as independent validation.
