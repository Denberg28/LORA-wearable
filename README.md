# LORA wearable

**0.1.0-rc.1 · TEST CANDIDATE · hardware validation BLOCKED**

Custom Arduino firmware for the **Seeed XIAO nRF52840 + header-connected
Wio-SX1262 kit**, and an offline Windows emergency monitor. Hold a small touch
button for three seconds to send SOS through a bounded LoRa relay network.
The USB base records wearable status in the Windows monitor. Optional external
UART GNSS gives GPS coordinates; three or more surveyed receivers can produce
a coarse RSSI location estimate when a current GPS fix is unavailable.

This is a controlled-validation prototype, not a validated emergency service.
No range, battery endurance, delivery rate or real location accuracy has been
measured. See [hardware validation](docs/HIL.md) before operational use.

## Hardware

Minimum: one wearable kit, one base kit, two compatible antennas, a Windows PC,
and a 3.3 V momentary digital touch sensor (active high by default). Add relay
kits to extend coverage. For location without GPS, use **at least three
non-collinear surveyed receivers hearing the wearable directly**, normally
three relay kits in addition to the base. More hops alone cannot locate a device.

The kit has no built-in GPS. Optional UART GNSS must output NMEA at 9600 baud
with 3.3 V logic. Use a protected 1-cell Li-ion/LiPo connected with the correct
polarity to the board's battery pads; verify charging current and battery
requirements against your exact board revision. Attach a suitable antenna
before enabling any transmitter. See [wiring](docs/HARDWARE.md).

## Windows monitor

Download the candidate's `LORA-Wearable-Monitor-Windows.zip`, extract, and run
`LORA-Wearable-Monitor.exe`. The application is unsigned. No internet, paid
service, Python installation or map account is required for this package.
The executable is built by the Windows CI job; inspect the linked workflow
result before assuming the package exists.

Or use Python 3.12 with Tk support:

```powershell
py -3 -m pip install -r requirements.txt
py -3 -m monitor.app --demo
py -3 -m monitor.app --anchors private/anchors.json
```

Select the base COM port, Connect, and wait for a gateway heartbeat. The monitor
shows SOS, stale links, coordinates, source and indicative uncertainty, plus an
offline position plot. It sounds a repeating system bell for unreviewed SOS.
**Review selected alert only silences that operator reminder.** Cancellation
requires release and a new three-second hold on the wearable. A stale link or
closed app never cancels an SOS.

Normal records live in `%LOCALAPPDATA%/LORA-wearable/events.sqlite3`; demo data
is isolated in its `demo` subdirectory. Event history can be exported as CSV.
Back up the entire data directory while the app is closed. Coordinates and
event records are personal data; the project does not upload them.

## Arduino IDE setup

1. Install Arduino IDE 2.x. Add the board-manager URL
   `https://files.seeedstudio.com/arduino/package_seeeduino_boards_index.json`.
2. Install **Seeed nRF52 Boards 1.1.13** and select **Seeed XIAO nRF52840**
   (`Seeeduino:nrf52:xiaonRF52840`). Use the non-mbed BSP.
3. Library Manager: **RadioLib 7.3.0**, **Crypto 0.4.0** by Rhys Weatherley,
   **TinyGPSPlus 1.0.3**. LittleFS and TinyUSB are supplied by the BSP.
4. Open `firmware/LoRaWearable/LoRaWearable.ino`.
5. Create private deployment settings below. Copy the chosen device's `.h` to
   `firmware/LoRaWearable/Config.h`, then Verify and Upload to that device's port.
   Repeat with each device's unique configuration. Close the monitor before
   uploading to the USB base.

### Provision a private network

Choose frequency and power permitted for your deployment area and equipment.
The example's 915 MHz is a configurable starting value, **not regional approval**.
All nodes require the same frequency, network ID and 32-byte secret key.

```powershell
py -3 scripts/provision.py --frequency 915 --power 10 --confirm-region --wearables 1 --relays 3
```

This creates `private/base.h`, `wearable-100.h`, `relay-10.h` through `relay-12.h`,
and an empty `anchors.json`. It refuses to replace existing keys. Preserve the
private directory securely; never publish it. Settings ship with transmission
disabled. **Public prebuilt firmware is radio-disabled and is only a build
reference; provision and compile locally before an RF test.**

Survey each relay's latitude/longitude. Set `ANCHOR_VALID true` and E7
coordinates in that relay's config; enter matching coordinates in the monitor
allowlist (real survey values only):

```json
{"10":{"lat":13.00000,"lon":123.00000},"11":{"lat":13.00100,"lon":123.00000},"12":{"lat":13.00000,"lon":123.00100}}
```

These numbers are illustrative, not installation locations. RSSI is affected by
body shielding, buildings, antenna orientation and multipath. The first release
uses an assumed -40 dBm at 1 m and path-loss exponent 2.7. Indicative uncertainty
is **not a statistical confidence radius**; field calibration remains required.
Degenerate geometry and inconsistent solutions produce unknown/last-known location.

## Reproducible command-line build

Use Arduino CLI **1.3.1** and Python **3.12**. Linux CLI builds additionally
require `python -m pip install adafruit-nrfutil==0.5.3.post16` on PATH for the
board's DFU packaging recipe:

```sh
arduino-cli core update-index --additional-urls https://files.seeedstudio.com/arduino/package_seeeduino_boards_index.json
arduino-cli core install Seeeduino:nrf52@1.1.13 --additional-urls https://files.seeedstudio.com/arduino/package_seeeduino_boards_index.json
arduino-cli lib install RadioLib@7.3.0 Crypto@0.4.0 TinyGPSPlus@1.0.3
python scripts/build_firmware.py
python scripts/build_firmware.py --device-config private/wearable-100.h
python -m unittest discover -s tests -v
g++ -std=c++11 -Wall -Wextra -Werror tests/protocol_test.cpp -o build/protocol-test
```

The first build compiles all roles into `build/firmware/`. The private-config
build compiles that one configured device. Do not distribute provisioned images:
firmware contains the network secret. Monitor source requires only pyserial;
its UI uses Python's Tk and SQLite standard libraries.

## Behavior and limits

- SOS survives reboot. A held input at boot is ignored until released, preventing
  automatic activation/cancellation from a stuck sensor.
- Blue blink: no current gateway receipt; fast red: active SOS awaiting receipt;
  slow red: SOS with a recent receipt; green: idle with receipt. A receipt means
  **the gateway received a packet**, not that the PC saved it or a rescuer saw it.
- Retransmit with a new sequence after 10 s while awaiting receipt; once received,
  active status every 30 s, idle every 60 s. No maximum delivery time is guaranteed.
- Relays forward each unique packet once, at most three relay hops, with jitter,
  bounded caches/queues and visible drop counters. Same-channel flooding is used.
  **Frequency-hopping spread spectrum is not implemented.**
- GPS is current for 30 s; retained positions become last known. Links become
  stale after 150 s. The base cannot remotely cancel a wearable's SOS.
- Protocol v1 is custom, not Meshtastic, LoRaWAN, EWS-LORA or TeleRC compatible.
- Shared-key HMAC authenticates network membership, not separate device identity.
  There is no encryption, trusted RF timestamp or denial-of-service protection.
  Previously unseen delayed packets cannot be distinguished from fresh first
  contact. Use a trusted, local USB base; serial input is not an internet API.
- Single-channel half-duplex collision behavior, touch performance in rain,
  runtime and RF range require HIL/field validation. Initial HIL scope is one
  wearable and up to three relays; larger fleets are not validated.

## Delivery, upgrade and rollback

See [specification](docs/SPEC.md), [architecture](docs/ARCHITECTURE.md),
[test evidence](docs/TESTING.md), [HIL procedure](docs/HIL.md),
[known issues](docs/KNOWN_ISSUES.md) and [changelog](CHANGELOG.md).
Release packages include a commit manifest and SHA-256 checksums. Upgrade all
v1 nodes together; back up private configs and PC data first. Never erase MCU
storage to fix an ordering problem without re-enrolling that ID in a **new**
monitor database/network. Downgrading counters can cause rejected packets.
No prior working project release exists; rollback is removal of this candidate
or restoration of a separately backed-up factory firmware/configuration.

Hardware sources:
[Seeed kit guide](https://wiki.seeedstudio.com/xiao_nrf52840%26_wio_SX1262_kit_for_meshtastic/),
[XIAO BSP guide](https://wiki.seeedstudio.com/XIAO_BLE/),
[kit pin definitions](https://github.com/meshtastic/firmware/blob/develop/variants/nrf52840/seeed_xiao_nrf52840_kit/variant.h),
[RadioLib](https://github.com/jgromes/RadioLib/tree/7.3.0).
