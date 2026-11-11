#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
namespace lw {
constexpr size_t SIZE=64, BODY=48;
enum Kind : uint8_t { STATUS=1, ACK=2, OBSERVATION=3 };
struct Frame { uint8_t b[SIZE]{}; };
inline uint16_t u16(const Frame& f, size_t p) { return uint16_t(f.b[p]) | uint16_t(f.b[p+1])<<8; }
inline uint32_t u32(const Frame& f, size_t p) { return uint32_t(u16(f,p)) | uint32_t(u16(f,p+2))<<16; }
inline void put16(Frame& f,size_t p,uint16_t v) { f.b[p]=v;f.b[p+1]=v>>8; }
inline void put32(Frame& f,size_t p,uint32_t v) { put16(f,p,v);put16(f,p+2,v>>16); }
inline bool shape(const Frame& f, uint16_t net) {
  if(f.b[0]!='L'||f.b[1]!='W'||f.b[2]!=1||f.b[3]<1||f.b[3]>3||u16(f,4)!=net) return false;
  if(!u16(f,6)||u16(f,6)==65535||!u16(f,8)||u16(f,8)==65535||f.b[10]>3||f.b[11]>3||u16(f,46)) return false;
  if(!u32(f,12)||!u32(f,16)) return false;
  if(f.b[11]&2) {
    int32_t lat=int32_t(u32(f,30)),lon=int32_t(u32(f,34));
    if(lat < -900000000 || lat > 900000000 || lon < -1800000000 || lon > 1800000000 || u16(f,38)>30) return false;
  }
  if(f.b[3]!=STATUS && (!u16(f,20)||!u32(f,22)||!u32(f,26))) return false;
  return true;
}
struct Button {
  bool raw=false,stable=false,armed=false,fired=false; uint32_t changed=0,pressed=0;
  bool update(bool down,uint32_t now) {
    if(down!=raw) {raw=down;changed=now;}
    if(uint32_t(now-changed)>=40 && stable!=raw) {
      stable=raw;
      if(!stable) {armed=true;fired=false;} else pressed=now;
    }
    // Require a released input after boot; a stuck-high sensor cannot activate.
    if(!down && uint32_t(now-changed)>=40) armed=true;
    if(armed && stable && !fired && uint32_t(now-pressed)>=3000) {fired=true;return true;}
    return false;
  }
};
struct Seen {
  uint16_t origin=0;uint32_t boot=0,seq=0,at=0;
};
inline bool same(const Seen& s,const Frame& f) { return s.origin==u16(f,6)&&s.boot==u32(f,12)&&s.seq==u32(f,16); }
// The gateway acknowledges every newly observed STATUS independently of other
// wearables; a global ACK throttle can starve devices transmitting in bursts.
inline bool shouldAcknowledge(bool duplicate, const Frame& f) { return !duplicate && f.b[3]==STATUS; }
}
