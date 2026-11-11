#include "../firmware/LoRaWearable/Protocol.h"
#include "../firmware/LoRaWearable/StateStorage.h"
#include <cassert>
#include <cstdio>
struct MountOnly {
  bool mounted=false;
  bool begin() { return mounted; }
};
struct AutoErasingFS : MountOnly {
  bool erased=false;
  bool begin() { erased=true;return true; }
};
int main() {
  AutoErasingFS fs;
  assert(!lw::mountExisting<MountOnly>(fs));assert(!fs.erased);
  fs.mounted=true;assert(lw::mountExisting<MountOnly>(fs));assert(!fs.erased);
  lw::Saved s{0x4c575331,19,1,0};s.check=lw::checksum(s);
  assert(lw::validSaved(s));s.active=0;assert(!lw::validSaved(s));
  lw::Frame f;f.b[0]='L';f.b[1]='W';f.b[2]=1;f.b[3]=1;f.b[10]=3;
  lw::put16(f,4,2761);lw::put16(f,6,100);lw::put16(f,8,100);lw::put32(f,12,1);lw::put32(f,16,1);
  assert(lw::shape(f,2761));
  // An ACK must be queued for each unique wearable status; duplicate storms
  // must not trigger unbounded repeat acknowledgements.
  assert(lw::shouldAcknowledge(false,f));
  assert(!lw::shouldAcknowledge(true,f));
  f.b[3]=lw::ACK;assert(!lw::shouldAcknowledge(false,f));
  f.b[3]=lw::OBSERVATION;assert(!lw::shouldAcknowledge(false,f));
  f.b[3]=lw::STATUS;
  f.b[10]=4;assert(!lw::shape(f,2761));
  lw::Button b;
  // Stuck active at boot is ignored until released.
  assert(!b.update(true,0));assert(!b.update(true,40));assert(!b.update(true,4000));
  assert(!b.update(false,4100));assert(!b.update(false,4140));
  assert(!b.update(true,4200));assert(!b.update(true,4240));assert(!b.update(true,7239));
  assert(b.update(true,7240));assert(!b.update(true,15000));
  assert(!b.update(false,15001));assert(!b.update(false,15041));
  assert(!b.update(true,15100));assert(!b.update(true,15140));assert(b.update(true,18140));
  // Millisecond counter wrap must not break debounce/hold.
  lw::Button c;c.update(false,0xfffff000);c.update(false,0xfffff040);
  c.update(true,0xffffff00);c.update(true,0xffffff40);assert(c.update(true,0x00000b00));
  std::puts("PASS firmware protocol + touch lifecycle + nonformatting storage");
}

