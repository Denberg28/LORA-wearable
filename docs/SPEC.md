# Specification and baseline

Repository: `https://github.com/Denberg28/LORA-wearable`, public, default `main`.
Observed empty on 2026-11-11. Initial rules commit
`544bbf072bb1e4c9c7f557d7c74a311bbdddba0d`; no known-good functional release.
Rules imported from Denberg28/Agents_md AGENTS.md v1.1 and preserved locally.

## MVP and flow

Wearable: boot -> restore persistent SOS -> wait for release -> 3 s touch hold ->
persist new state -> transmit authenticated status -> relay(s) -> USB base ->
Windows monitor -> local SQLite event history and audible operator reminder.
Gateway sends a matched RF receipt, which changes wearable indication. Release
and another 3 s hold persists/sends cancellation. PC review never cancels RF SOS.

Optional GNSS: fresh NMEA fix -> packet coordinates -> GPS label. Without fresh
GPS, direct observations from >=3 surveyed non-collinear nodes for the same
beacon -> conservative RSSI multilateration -> estimate + indicative uncertainty.
Insufficient or unsuitable geometry -> unknown or clearly stale last-known fix.

Assumptions: identical header-connected nRF52840 kit used for all roles; 3.3 V
active-high non-latching touch module on D0; optional generic GNSS leaves D0
free. A base is USB connected to Windows. PC storage is local and offline.

Non-goals: RF frequency hopping, precision triangulation/TDoA, voice/text chat,
cloud dispatch, automatic rescue notification, BLE app, waterproof certification,
validated battery runtime, LoRaWAN/Meshtastic interoperability or remote control.

## Acceptance criteria

| ID | Measurable expected result | Required evidence |
|---|---|---|
| AC1 | Each role builds with pinned real XIAO BSP | automated build |
| AC2 | 40 ms debounce; one transition after 3 s stable hold; no repeats until release; boot-held input ignored | native test + HIL ±0.5 s |
| AC3 | SOS persists over 20 power cycles; corrupted storage disables RF with visible fault | HIL |
| AC4 | All 100 direct and 100 one-relay SOS/cancel trials received within 30 s at documented bench RF conditions; any loss blocks stable | HIL |
| AC5 | Malformed/wrong network/wrong HMAC rejected; duplicate/older messages never roll PC state back, including restart | software + HIL |
| AC6 | Idle/no-fix never fabricates coordinates; GPS stale >30 s and link stale >150 s; stale never cancels SOS | software + HIL |
| AC7 | >=3 same-beacon direct observations required; collinear geometry rejected; synthetic solution within 2 m of model truth | software; real accuracy field-only |
| AC8 | USB unplug -> stale gateway indication <=12 s; reconnect within 5 s after COM availability without UI freeze; SOS retained | HIL + Windows |
| AC9 | Watchdog resets a deliberately stalled MCU within 9 s; restored SOS remains active | HIL |
| AC10 | 8 h run, 20 reconnect/power cycles, no crash/unbounded memory growth/undisclosed queue drops | HIL/Windows soak |
| AC11 | Source, firmware and Windows artifacts versioned, checksummed and tied to commit; secrets absent | packaging/CI |

Candidate requires automated build, behavior, regression, simulated integration
and packaging gates. Physical AC3/4/8/9/10 and real RF/position portions remain
BLOCKED without equipment. Stable release is forbidden until all pass.
