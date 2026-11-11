# Changelog

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
