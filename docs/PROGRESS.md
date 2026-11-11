# Development checkpoint — 0.1.0-rc.4

Date: 11 November 2026. Previous published software baseline: rc.3 / main
`91d2c1e77831eff0447b5cd3f1b78676a00188fd`. Its CI passed, but no hardware or
field evidence existed. A new storage defect was found during this review;
rc.1–rc.3 are superseded and should not be deployed.

## Implemented in this revision

- Prevent implicit flash erasure on normal boot; require deliberate new-device
  commissioning; preserve compatible existing SOS records and counters.
- Add a separately configured radio-free `storage-init` image and exact USB
  confirmation, refusing to overwrite existing readable state.
- Fit RSSI positions in dB space with per-receiver calibration, bounded work,
  geometry/consistency checks and nonfinite-input rejection.
- Prevent late observations refreshing stale beacon locations; invalidate RSSI
  results after changing receiver surveys/models; preserve SOS and GPS.
- Add local session recording, receiver setup in the Windows UI, offline
  exact-beacon labeling/export, calibration and held-out evaluation.
- Preserve missed-beacon denominators, prevent training/evaluation site leakage,
  and withhold profiles from synthetic or failed evaluation data.
- Expose wearable transmission identities for controlled field measurements.
- Harden packet decoding against whitespace-shortened hex and invalid references.

## Acceptance and current outcome

Software unit/native checks pass locally; exact-commit firmware/Windows/UI and
packaging results are recorded by GitHub Actions before candidate publication.
The packaged manifest identifies the source commit. New checks and commands
are in TESTING.md; no local firmware compile is claimed in this environment.

Synthetic evaluation reaches the coarse reference target under ideal/3 dB
noise conditions. It fails under 6 dB noise, 15 dB body shadow and one-receiver
loss. These are useful negative results, not physical measurements. There is
no evidence yet that deployed RSSI location meets the user's operational goal.

## Remaining physical work

BLOCKED: no connected XIAO/Wio radios, touch input, battery/GNSS or field site
available to this environment. Required next evidence is:

1. Commission new devices; verify normal startup cannot format failed storage,
   including power cuts during SOS transitions, without resetting counters.
2. Measure SOS delivery and round-trip receipts under direct, relay, collision,
   dropout/recovery and multiwearable trials from HIL.md.
3. Survey receivers and wearer positions; record transmitted/received beacons;
   calibrate and evaluate independent sites using FIELD_VALIDATION.md.
4. Measure battery runtime, wet-input behavior, GPS validity, USB disconnect,
   watchdog recovery and the final installed configuration.

Stable promotion remains blocked until applicable HIL/field gates pass. The
software is a controlled test candidate, not a completed validated emergency
service. Future autonomous turns should read this checkpoint, current CI and
known issues before making additional changes. Do not infer success from a
build, repeat ideal simulations as field proof, or silently lower the targets.
