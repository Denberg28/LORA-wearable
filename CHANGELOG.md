# Changelog

## 0.1.0-rc.4 — 2026-11-11

- Fix BSP auto-formatting on normal boot, require deliberate new-device storage setup, and add a radio-free commissioning image. Supersedes rc.1–rc.3.
- Add per-receiver RSSI calibration, dB-space location fitting, independent evaluation, local field capture and receiver loading in the Windows monitor.
- Preserve missed trials, reject site leakage and withhold deployable profiles from synthetic/failed evaluations.
- Reject nonfinite/shortened packet inputs, prevent late position refresh and invalidate RSSI positions after survey/model changes.
- Record negative synthetic noise/body-shadow results. Physical link, flash, battery and location validation remain blocked.

## 0.1.0-rc.3 — 2026-11-11

- Add direct receiver-coverage reference for the exact latest wearable beacon:
  surveyed receiver IDs, signal RSSI and pinned receiver sites, even when
  multilateration cannot yield a wearable position.
- Distinguish fixed receiver squares from wearable estimates; no sparse-anchor
  bearing, distance or invented location claims.
- Add simulated regression checks for out-of-order observations, freshness,
  beacon isolation and 1–2 anchor fallback. Field accuracy remains unverified.

## 0.1.0-rc.2 — 2026-11-11

- Default SOS input now matches Wio-SX1262's onboard active-low D0 button;
  external active-high 3.3 V capacitive sensors remain configurable.
- Remove the gateway's shared ACK throttle so independent new wearable statuses
  can each receive a queued receipt. Duplicate STATUS packets no longer create
  redundant ACKs. Added native ACK decision tests.
- Hardware wiring and HIL limitations clarified; no physical verification or
  positioning accuracy claims.

## 0.1.0-rc.1 — 2026-11-11

Initial controlled-validation candidate: XIAO nRF52840/Wio-SX1262 wearable,
relay and USB base sketch; persistent local SOS/cancel; shared-key HMAC; bounded
multi-hop flooding; gateway receipts; optional external GNSS; same-beacon direct
RSSI observations; offline Windows Tk/SQLite monitor and position plot; local
review, event export, reconnect and stale-link handling; pinned builds, tests,
candidate packaging and hardware-validation procedure. HIL remains BLOCKED.

