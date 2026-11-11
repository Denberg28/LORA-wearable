#pragma once
#include <stdint.h>
namespace lw {
struct Saved { uint32_t magic,boot,active,check; };
inline uint32_t checksum(const Saved& s) { return s.magic ^ s.boot ^ s.active ^ 0x57329adc; }
inline bool validSaved(const Saved& s) {
  return s.magic==0x4c575331 && s.active<=1 && s.check==checksum(s);
}
// The BSP's derived begin() erases/reformats on a mount failure. Explicit
// base dispatch is essential: normal boot must fail without writing storage.
template<class MountOnly, class FileSystem>
bool mountExisting(FileSystem& fs) { return static_cast<MountOnly&>(fs).begin(); }
}
