Initial LORA wearable controlled-validation candidate.

- Arduino IDE sketch for wearable, relay and USB base using XIAO nRF52840 + Wio-SX1262 header kit.
- Three-second touch SOS/cancel, persistent state, authenticated bounded multi-hop communication and gateway receipts.
- Windows offline monitor: SOS alerts, local review/history, stale links, optional GPS and coarse RSSI location estimates.
- Source, disabled-radio reference firmware, Windows application, manifest and checksums included.

**HIL and field validation BLOCKED. Not a stable or operationally validated emergency device.**

Public firmware cannot transmit: provision a private key and permitted radio settings, then build/upload through Arduino IDE. GPS requires an external module. RSSI location needs three or more surveyed receivers hearing the wearable directly, and remains uncalibrated. Frequency hopping is not implemented. Gateway receipt is not human rescue confirmation.

Read README.md, docs/HARDWARE.md and docs/HIL.md before testing. Back up private configuration and PC data before upgrades. There is no prior known-good project release; remove this candidate or restore your independently backed-up factory firmware to roll back. Never replace private keys/counters casually.
