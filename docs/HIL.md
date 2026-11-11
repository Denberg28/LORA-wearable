# Runnable hardware validation procedure

**Status: BLOCKED — no physical kits, GNSS, touch module or RF test equipment
available in the build workspace.** Record actual measurements; do not infer
radio performance from compile results, simulation, LED state or a heartbeat.

Use one wearable, one USB base and up to three relays of the documented kit,
antennas attached, safe power supplies/protected cells and a Windows PC. Preserve
existing factory images/configuration before replacing firmware. Provision a
private network, record source commit, per-device config SHA256 (not key), board
revisions, antennas/gain, frequency/power, positions, enclosure, power setup,
Windows version and app version. Start at low permitted power on a bench.

1. **Provisioning gate:** upload a public default image. Confirm red fault and
   `provision_key_and_region`; spectrum/second receiver must see no transmitted
   packets. Upload private builds, verify all unique IDs and base heartbeat.
2. **Input lifecycle:** release sensor >1 s; hold <3 s (no SOS), hold >=3 s (one
   SOS within 3.0–3.5 s), keep held20 s (no cancellation). Release/rehold >=3 s
   to cancel. Repeat100 cycles. Boot while held (no transition until release).
   Test physical button, enclosure, wet finger/no touch, vibration and brownout.
3. **Direct link:** with no relay, perform100 SOS/cancel trials, save PC exports,
   video LED timing and timestamp observations. Every transition must appear
   within30 s under recorded bench conditions; receipt must never imply human
   review. PC Review must leave wearable SOS unchanged.
4. **Relay link:** attenuate/shield/separate wearable and base until direct path
   is demonstrably absent. Place one relay to bridge them. Repeat100 trials;
   expect <=30 s. Repeat two/three relay hops; document omitted topologies and
   measured distribution. Remove relay during active SOS; restore after60 s;
   next unique status must recover. Check no endless flood loops.
5. **Fault injection:** replay recorded old valid SOS/cancel frames through a
   separately provisioned test sender; mutate byte/tag/network/version/length.
   Wrong auth frames must increment rejects and not update/cancel the PC.
   Delay/reorder statuses and receipts. Old receipts must not confirm a newer
   state. Disconnect/reconnect USB20 times; heartbeat missing <=12 s, reopen
   within5 s of COM return (plus heartbeat interval), existing SOS remains.
6. **Persistence:** during SOS, power-cycle20 times including during transition
   writes. SOS stays active or explicit storage fault disables RF; never silently
   idle. Confirm PC high water marks survive app restart. Corrupt a test MCU
   state record using a dedicated debug build: expect storage fault, no RF.
7. **Watchdog:** in a separately labeled debug build, deliberately stall `loop`
   after SOS. Measure reset <=9 s and active SOS recovery. Remove this injection
   and rebuild final source; repeat all affected checks on final firmware.
8. **GPS:** connect optional GNSS, enable config, use open sky. Compare exported
   coords against independent reference. Remove GNSS TX/antenna; after30 s
   location must become stale/unknown or use a valid RSSI estimate. Never retain
   a stale point under a current GPS label. Check valid zero/negative coords.
9. **RSSI location:** survey three/four non-collinear nodes and configure both
   firmware and monitor allowlist. Disable wearable GNSS. Verify direct
   observations all reference the same wearable generation/sequence. Relayed
   RSSI and unknown anchors must not contribute. Record >=20 known points,
   indoors/outdoors, body/antenna orientations, RSSI, estimated position, error,
   and indicative radius. Report median/p95/max error; no advertised accuracy
   until calibrated evidence exists. Test collinear and missing-node cases.
   With exactly one, then two surveyed receivers hearing the same wearable
   beacon directly, verify the Windows monitor displays receiver ID and RSSI,
   plots squares at fixed surveyed receiver locations, and shows wearable
   position UNKNOWN (unless a clearly labeled independent last-known fix
   exists). Check that an unrelated/old beacon cannot contribute to coverage,
   and that sightings expire after 30 s without being shown as current. The
   receiver sites are not estimates of wearer direction, distance, or position.
10. **Load/endurance:** run8 h with one wearable/three relays, intermittent SOS,
    USB interruptions and link fades. Record memory, disk use, TX errors, queue
    drops and delivery times. Any unexplained loss/crash/drop blocks stable.
    Measure battery current with actual hardware in idle, RX, TX and SOS; run
    to documented low-battery cutoff. No runtime claim from nominal capacity.

For each step, append PASS/FAIL/BLOCKED, measured values, timestamp, exact final
source/config hashes, evidence paths and tester identity in `docs/HIL_RESULTS.md`.
User-run tests count only with those observations. Stop stable promotion on any
failed required criterion. A failed physical core flow must be fixed before a
new candidate; missing equipment alone permits this explicitly labeled candidate.
