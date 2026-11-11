"""Decode only authenticated packets supplied by the trusted USB gateway."""
from dataclasses import dataclass
import struct

@dataclass(frozen=True)
class Packet:
    kind: int
    origin: int
    sender: int
    boot: int
    seq: int
    flags: int
    target: int
    ref_boot: int
    ref_seq: int
    lat: float
    lon: float
    age: int
    rssi: int
    observer: int

def decode(value: str, network: int) -> Packet:
    if not isinstance(value, str) or len(value) != 128:
        raise ValueError('packet length')
    b = bytes.fromhex(value)
    u16 = lambda p: struct.unpack_from('<H', b, p)[0]
    u32 = lambda p: struct.unpack_from('<I', b, p)[0]
    if b[:3] != b'LW\x01' or b[3] not in (1, 2, 3) or u16(4) != network:
        raise ValueError('protocol/network')
    if u16(6) in (0, 65535) or u16(8) in (0, 65535) or b[10] > 3 or b[11] > 3 or u16(46):
        raise ValueError('header')
    lat, lon = struct.unpack_from('<ii', b, 30)
    if not u32(12) or not u32(16):
        raise ValueError('ordering')
    if b[11] & 2 and (abs(lat) > 900000000 or abs(lon) > 1800000000 or u16(38) > 30):
        raise ValueError('position')
    if b[3] != 1 and (not u16(20) or not u32(22) or not u32(26)):
        raise ValueError('reference')
    return Packet(b[3], u16(6), u16(8), u32(12), u32(16), b[11], u16(20), u32(22), u32(26),
                  lat / 1e7, lon / 1e7, u16(38), struct.unpack_from('<h', b, 42)[0], u16(44))
