#pragma once
// Copy to Config.h, or run scripts/provision.py. Never commit Config.h.
#define DEVICE_ROLE 1 // 1 wearable, 2 relay, 3 USB base
#define DEVICE_ID 100 // unique 1..65534; base must use BASE_ID
#define BASE_ID 1
#define NETWORK_ID 2761
#define REGION_CONFIRMED false // Confirm local permitted frequency/power first.
#define RADIO_MHZ 915.0f // configurable; not a claim of local authorization
#define RADIO_DBM 10
#define KEY_PROVISIONED false
static const uint8_t NETWORK_KEY[32] = {0};
#define TOUCH_ACTIVE_HIGH false // Kit's D0 onboard pushbutton pulls LOW; set true for external active-high touch output
#define GNSS_ENABLED false // external UART GNSS, TX -> D7, GND common
#define ANCHOR_VALID false
#define ANCHOR_LAT_E7 0
#define ANCHOR_LON_E7 0
