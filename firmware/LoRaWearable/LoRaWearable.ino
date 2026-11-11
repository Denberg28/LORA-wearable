#include <Arduino.h>
#include <SPI.h>
#include <RadioLib.h>
#include <SHA256.h>
#include <TinyGPSPlus.h>
#include <Adafruit_LittleFS.h>
#include <InternalFileSystem.h>
#include "Protocol.h"
#if __has_include("Config.h")
#include "Config.h"
#else
#include "Config.example.h"
#endif
using namespace Adafruit_LittleFS_Namespace;
using namespace lw;
// Header-connected nRF52840 kit, NOT the ESP32-S3 B2B module.
SX1262 radio = new Module(D4,D1,D2,D3);
TinyGPSPlus gps;
Button touch;
volatile bool received=false;
bool ready=false,active=false,delivered=false,pending=false;
uint32_t bootNumber=0,sequence=0,lastStatus=0,lastTx=0,lastHealth=0;
uint32_t dropped=0,badPackets=0,txErrors=0;
uint8_t stateSlot=0;
struct Saved { uint32_t magic,boot,active,check; };
struct Outgoing { Frame frame;uint32_t due;bool used=false; } queue[12];
Seen seen[48];uint8_t seenIndex=0;
Frame lastPacket;
void irq() {received=true;}
void led(uint8_t pin,bool on) {digitalWrite(pin,on?LOW:HIGH);}
void fail(const char* reason) {ready=false;led(LED_RED,true);Serial.print("{\"type\":\"fault\",\"reason\":\"");Serial.print(reason);Serial.println("\"}");}
uint32_t checksum(const Saved& s) {return s.magic ^ s.boot ^ s.active ^ 0x57329adc;}
bool saveState(uint32_t n,bool sos) {
  Saved s{0x4c575331,n,uint32_t(sos),0};s.check=checksum(s);
  const char* path=stateSlot?"/lw1":"/lw0";
  File f(InternalFS); if(!f.open(path,FILE_O_WRITE))return false;
  f.seek(0); size_t written=f.write((uint8_t*)&s,sizeof(s));f.close();
  File v(InternalFS);Saved check{};if(!v.open(path,FILE_O_READ))return false;
  size_t read=v.read((uint8_t*)&check,sizeof(check));v.close();
  if(written!=sizeof(s)||read!=sizeof(s)||memcmp(&s,&check,sizeof(s)))return false;
  stateSlot^=1;return true;
}
bool loadState() {
  if(!InternalFS.begin())return false;
  Saved best{};bool found=false;
  for(uint8_t i=0;i<2;i++) {
    const char* path=i?"/lw1":"/lw0";
    if(!InternalFS.exists(path))continue;
    File f(InternalFS);Saved s{};if(!f.open(path,FILE_O_READ))return false;
    size_t n=f.read((uint8_t*)&s,sizeof(s));f.close();
    // Refuse corrupted storage rather than silently roll back a counter/SOS.
    if(n!=sizeof(s)||s.magic!=0x4c575331||s.active>1||s.check!=checksum(s))return false;
    if(!found||s.boot>=best.boot) {best=s;stateSlot=i^1;found=true;}
  }
  if(best.boot==UINT32_MAX)return false;
  bootNumber=best.boot+1;active=best.active;
  return saveState(bootNumber,active);
}
void sign(Frame& f) {SHA256 h;h.resetHMAC(NETWORK_KEY,32);h.update(f.b,BODY);h.finalizeHMAC(NETWORK_KEY,32,f.b+BODY,16);}
bool authentic(Frame f) {
  uint8_t tag[16];memcpy(tag,f.b+BODY,16);sign(f);uint8_t diff=0;
  for(size_t i=0;i<16;i++)diff|=tag[i]^f.b[BODY+i];return diff==0;
}
Frame makeFrame(uint8_t kind) {
  Frame f;f.b[0]='L';f.b[1]='W';f.b[2]=1;f.b[3]=kind;
  put16(f,4,NETWORK_ID);put16(f,6,DEVICE_ID);put16(f,8,DEVICE_ID);f.b[10]=3;
  put32(f,12,bootNumber);if(++sequence==0) {fail("sequence_exhausted");sequence=UINT32_MAX;}
  put32(f,16,sequence);return f;
}
void enqueue(Frame f,uint32_t delayMs) {
  for(auto& q:queue)if(!q.used) {sign(f);q.frame=f;q.due=millis()+delayMs;q.used=true;return;}
  dropped++;
}
bool duplicate(const Frame& f) {
  for(const auto& s:seen)if(same(s,f)&&uint32_t(millis()-s.at)<120000)return true;
  Seen& s=seen[seenIndex];s.origin=u16(f,6);s.boot=u32(f,12);s.seq=u32(f,16);s.at=millis();
  seenIndex=(seenIndex+1)%48;return false;
}
void sendStatus() {
  Frame f=makeFrame(STATUS);f.b[11]=active?1:0;
  if(GNSS_ENABLED && gps.location.isValid() && gps.location.age()<30000) {
    f.b[11]|=2;put32(f,30,int32_t(gps.location.lat()*1e7));put32(f,34,int32_t(gps.location.lng()*1e7));put16(f,38,gps.location.age()/1000);
  }
  // Zero battery means unavailable; never invent a percentage.
  lastPacket=f;pending=true;delivered=false;lastStatus=millis();enqueue(f,random(40,240));
}
void serialFrame(const Frame& f,int16_t rssi) {
  Serial.print("{\"type\":\"packet\",\"hex\":\"");
  const char hex[]="0123456789abcdef";for(uint8_t v:f.b) {Serial.print(hex[v>>4]);Serial.print(hex[v&15]);}
  Serial.print("\",\"rssi\":");Serial.print(rssi);Serial.println("}");
}
void handle(Frame f,int16_t rssi) {
  if(!shape(f,NETWORK_ID)||!authentic(f)) {badPackets++;return;}
  if(u16(f,6)==DEVICE_ID)return;
  if(DEVICE_ROLE==1) {
    if(f.b[3]==ACK && u16(f,6)==BASE_ID && u16(f,20)==DEVICE_ID && u32(f,22)==bootNumber && u32(f,26)==u32(lastPacket,16) && (f.b[11]&1)==(active?1:0)) {delivered=true;pending=false;}
    return;
  }
  bool dup=duplicate(f);
  if(DEVICE_ROLE==3) {
    serialFrame(f,rssi);
    // ACK means received by the USB gateway, never operator/rescuer acceptance.
    if(shouldAcknowledge(dup,f)) {
      Frame a=makeFrame(ACK);put16(a,20,u16(f,6));put32(a,22,u32(f,12));put32(a,26,u32(f,16));a.b[11]=f.b[11]&1;
      enqueue(a,random(60,200));
    }
  }
  if(dup)return;
  if(f.b[3]==STATUS && u16(f,8)==u16(f,6) && ANCHOR_VALID) {
    Frame obs=makeFrame(OBSERVATION);put16(obs,20,u16(f,6));put32(obs,22,u32(f,12));put32(obs,26,u32(f,16));
    obs.b[11]=2;put32(obs,30,int32_t(ANCHOR_LAT_E7));put32(obs,34,int32_t(ANCHOR_LON_E7));put16(obs,42,uint16_t(rssi));put16(obs,44,DEVICE_ID);
    if(DEVICE_ROLE==3) {sign(obs);serialFrame(obs,rssi);} else enqueue(obs,random(400,1300));
  }
  if(DEVICE_ROLE==2 && f.b[10]>0) {f.b[10]--;put16(f,8,DEVICE_ID);enqueue(f,random(100,500));}
}
void setup() {
  NRF_WDT->CONFIG=1;NRF_WDT->CRV=8*32768;NRF_WDT->RREN=1;NRF_WDT->TASKS_START=1;
  Serial.begin(115200); // Do not wait for USB; wearables must run on battery.
  const uint8_t leds[]={LED_RED,LED_GREEN,LED_BLUE};
  for(uint8_t p:leds) {pinMode(p,OUTPUT);led(p,false);}
  pinMode(D0,TOUCH_ACTIVE_HIGH?INPUT_PULLDOWN:INPUT_PULLUP);
  if(!REGION_CONFIRMED||!KEY_PROVISIONED) {fail("provision_key_and_region");return;}
  uint8_t nonzero=0;for(uint8_t k:NETWORK_KEY)nonzero|=k;
  if(!nonzero||DEVICE_ID==0||DEVICE_ID==65535||DEVICE_ROLE<1||DEVICE_ROLE>3||(DEVICE_ROLE==3&&DEVICE_ID!=BASE_ID)||(DEVICE_ROLE!=3&&DEVICE_ID==BASE_ID)) {fail("invalid_configuration");return;}
  if(!loadState()) {fail("persistent_state_error");return;}
  randomSeed(NRF_FICR->DEVICEID[0]^bootNumber^micros());
  if(GNSS_ENABLED)Serial1.begin(9600);
  // SF7, BW125, CR4/5; custom sync word, TCXO 1.8V; D5 external RX gate.
  radio.setRfSwitchPins(D5,RADIOLIB_NC);
  int16_t err=radio.begin(RADIO_MHZ,125.0,7,5,0x12,RADIO_DBM,8,1.8);
  if(err!=RADIOLIB_ERR_NONE) {fail("radio_init");return;}
  if(radio.setDio2AsRfSwitch(true)!=RADIOLIB_ERR_NONE) {fail("radio_switch");return;}
  radio.setDio1Action(irq);
  if(radio.startReceive()!=RADIOLIB_ERR_NONE) {fail("radio_receive");return;}
  ready=true;lastStatus=millis()-60000;
}
void loop() {
  NRF_WDT->RR[0]=0x6e524635;
  uint32_t now=millis();
  if(GNSS_ENABLED) {uint16_t budget=128;while(Serial1.available()&&budget--)gps.encode(Serial1.read());}
  if(!ready) {led(LED_RED,(now/150)%2);delay(5);return;}
  if(DEVICE_ROLE==1 && touch.update(digitalRead(D0)==(TOUCH_ACTIVE_HIGH?HIGH:LOW),now)) {
    if(bootNumber==UINT32_MAX || !saveState(bootNumber+1,!active)) {fail("state_write_error");return;}
    bootNumber++;sequence=0;active=!active;delivered=false;
    for(auto& q:queue)q.used=false;
    sendStatus();
  }
  if(received) {
    received=false;size_t len=radio.getPacketLength();Frame f;
    if(len==SIZE && radio.readData(f.b,SIZE)==RADIOLIB_ERR_NONE) handle(f,int16_t(radio.getRSSI()));
    else badPackets++;
    if(radio.startReceive()!=RADIOLIB_ERR_NONE) {fail("radio_receive");return;}
  }
  if(DEVICE_ROLE==1 && uint32_t(now-lastStatus)>uint32_t(pending?10000:(active?30000:60000)))sendStatus();
  // Aggregate node pacing at most one packet/1.5 s. Actual legal limits are site specific.
  if(uint32_t(now-lastTx)>=1500)for(auto& q:queue)if(q.used&&int32_t(now-q.due)>=0) {
    Frame f=q.frame;q.used=false;
    int16_t e=radio.transmit(f.b,SIZE);lastTx=millis();received=false;
    if(e!=RADIOLIB_ERR_NONE)txErrors++;
    if(radio.startReceive()!=RADIOLIB_ERR_NONE)fail("radio_receive");
    break;
  }
  if(uint32_t(now-lastHealth)>=5000) {
    lastHealth=now;Serial.print("{\"type\":\"health\",\"id\":");Serial.print(DEVICE_ID);
    Serial.print(",\"dropped\":");Serial.print(dropped);Serial.print(",\"bad\":");Serial.print(badPackets);
    Serial.print(",\"tx_errors\":");Serial.print(txErrors);Serial.println("}");
  }
  if(DEVICE_ROLE==1) {
    led(LED_RED,active&&((now/(delivered?600:150))%2));
    led(LED_GREEN,!active&&delivered);led(LED_BLUE,!delivered&&(now/500)%2);
  } else led(LED_GREEN,(now/1000)%2);
  delay(2);
}
