# Limitations and validation blockers

- HIL/field/real Windows USB validation is BLOCKED; no emergency-readiness claim.
- RSSI location is a model-based estimate with assumed calibration; no real
  accuracy demonstrated. This is ranging/multilateration, not angular triangulation.
- Frequency hopping, GPS module, waterproof enclosure and low-power sleep are
  not included. Continuous receive runtime is unmeasured.
- Trust-on-first-use ordering cannot reject a previously unseen delayed frame.
  Shared-key peers can impersonate another network member. RF is not encrypted.
- Gateway receipt does not prove PC persistence, operator attention or rescue.
- Bounded flood queues may drop packets under congestion, reported in health.
  No guaranteed delivery/range or validated capacity above initial HIL topology.
- Software visual review and Windows smoke/build evidence must be distinguished
  from actual COM-port/HIL operation. System bell audibility depends on PC audio.
- Public firmware images intentionally do not transmit; private provisioning and
  local recompilation are required. Never publish a provisioned image or key.

No known critical/high implementation defect is accepted for candidate delivery.
Missing hardware verification is recorded separately from defect severity.
