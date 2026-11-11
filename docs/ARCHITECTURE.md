# Interfaces, states and recovery

One sketch implements wearable (role 1), relay (2) and base (3). Device IDs are
unique; base ID defaults to 1, wearables start at 100, relays at 10. Node discovery
is implicit: all provisioned peers listen with identical LoRa parameters. No
pairing service or internet is required.

## Wire protocol v1

Fixed 64-byte little-endian frames. Bytes 0..47 are HMAC-SHA256 authenticated
with a deployment-random 32-byte shared key; first 16 digest bytes form the tag.
RadioLib's PHY CRC is additional corruption detection. Each relay modifies
sender and hop budget and recomputes HMAC; every trusted node knows the key.

| Offset | Width | Meaning |
|---|---|---|
| 0 | 2 | ASCII LW |
| 2 / 3 | 1 / 1 | version 1 / kind (1 status, 2 receipt, 3 observation) |
| 4 / 6 / 8 | 2 / 2 / 2 | network / origin ID / last sender ID |
| 10 / 11 | 1 / 1 | relay budget 0..3 / flags (bit0 SOS, bit1 current coordinates) |
| 12 / 16 | 4 / 4 | persistent boot/event generation / packet sequence |
| 20 / 22 / 26 | 2 / 4 / 4 | referenced wearable ID / generation / sequence |
| 30 / 34 | 4 / 4 signed | latitude / longitude E7 |
| 38 / 40 | 2 / 2 | source fix age seconds / battery mV (0 unavailable) |
| 42 / 44 | 2 signed / 2 | direct RSSI dBm / observer ID |
| 46 | 2 | reserved zero |
| 48 | 16 | truncated HMAC-SHA256 |

Status carries wearable coordinates; observations carry anchor coordinates and
reference the *exact* original wearable beacon. The monitor only uses surveyed
allowlisted anchor coordinates, not packet-supplied coordinates. Relays measure
RSSI only where origin==last sender; forwarded signal strength never becomes an
observation of the wearable. Observation-before-status arrival is supported.
Recent GPS wins over RSSI. Samples from different beacons never mix.

## State and authority

Only a deliberate local input changes wearable SOS. There is no actuator,
motor output, arming or competing control authority; these controls are N/A.
Two alternating LittleFS records hold generation and SOS with integrity checks.
Every boot/state transition advances generation. Writes are read back before
transmission. Any invalid record or exhausted counter causes a visible fault
and disabled RF. State transition writes never depend on PC/USB availability.

Monitor SQLite persists per-origin generation/sequence high water marks across
restart. Old or duplicate packets cannot cancel/refresh an existing newer state.
New peer first contact is trust-on-first-use: no synchronized RF clock means
unseen delayed packets cannot be identified as old. Physically clearing MCU
storage requires intentional re-enrollment; never reset counters in place.

Gateway receipts match base identity, wearable ID, generation, sequence and
SOS bit and pass network HMAC. They confirm gateway reception only. The PC and
human review have no authority to cancel. Receipt loss causes renewed status
attempts. Reconnecting PC never replays commands because no command API exists.

## Timing, bounds and faults

40 ms debounce, 3000 ms hold; input must be released after boot/each action.
Watchdog 8 s, fed from main loop. RadioLib blocking transmit is internally
bounded; physical hold latency and watchdog timing remain HIL checks. RX uses
DIO1 notifications. Transmission spacing >=1500 ms/node; 12 queued packets,
48 duplicate-cache slots, 120 s duplicate retention, randomized forwarding.
Duplicate cache keys contain origin/generation/sequence; TTL bounds loops even
after cache eviction. Queue overflow increments reported drops. This pacing
does not itself establish compliance with a region's airtime restrictions.

Status intervals: 10 s waiting for receipt, 30 s SOS after receipt, 60 s idle.
Each periodic attempt has a new sequence so relays can recover after lost floods.
No automatic cancellation on link loss, PC failure or receipt. The base emits
health every 5 s. Firmware radio/flash faults are explicit JSON faults and red
indication. Radio fault does not silently report ready; recovery is reboot after
the cause is corrected. Hardware watchdog reset restores SOS.

USB: 115200 baud ASCII newline-delimited JSON, max 1024 bytes/line. `packet`
events carry 128-character `hex` and last-link RSSI; `health` reports ID, drops,
rejects and TX errors. These are authenticated by gateway firmware on RF input,
not re-authenticated by PC. USB serial must be trusted. Diagnostic output
depends on functioning USB; disconnected USB does not block setup waiting.

Serial worker queue max1024; overflow stops transport, requiring explicit
reconnect. UI consumes up to100 events/tick, keeps SQLite work on UI thread,
and surfaces errors. Observations expire after60 s, location uses <=30 s samples.
Event history intentionally persists to local disk; storage errors stop transport.
No cloud telemetry, downloaded maps, shell execution or network listeners.
