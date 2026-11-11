# LORA wearable 0.1.0-rc.4 — TEST CANDIDATE

Supersedes rc.1–rc.3: their normal BSP filesystem startup can auto-erase state
on mount failure. rc.4 preserves failed storage and requires deliberate new-device
commissioning. See docs/STORAGE.md before first use or upgrade. Existing valid
state remains compatible; never initialize an enrolled identity or downgrade
to bypass a fault.

Adds per-receiver RSSI calibration, bounded dB-space fitting, field session
recording/receiver loading in the Windows UI, exact-beacon CSV export and held-out
location evaluation. Misses remain in the availability denominator; training and
evaluation sites cannot overlap. Synthetic/failed evaluations cannot produce
a deployment profile. Late receiver reports cannot refresh an old position.

Automated candidate checks include all three firmware roles plus the radio-free
storage initializer, Python/native behavior, Windows UI and executable packaging.
The source archive contains an exact commit manifest; SHA256SUMS covers both ZIPs.
Public operational images remain radio-disabled; privately provision and compile.

**Hardware/field validation remains BLOCKED.** No connected radio, flash power-cut,
touch, battery, USB delivery or real location result was measured. Synthetic
6 dB noise, 15 dB body shadow and one-receiver loss fail coarse location targets;
ideal/3 dB simulations are not field accuracy evidence. This is a controlled
validation candidate, not a validated emergency service or stable release.

See docs/PROGRESS.md, docs/FIELD_VALIDATION.md, docs/TESTING.md and docs/HIL.md.
Back up private configs and PC data. Prefer correction/re-enrollment to rollback
when persistent state fails; previous releases contain the storage defect.
