"""Deterministic serial simulator; deliberately not an authenticated RF sender."""
import json
import struct

def packet(seq=1, active=True, lat=None, lon=None, origin=100, boot=1,
           kind=1,target=0,ref_boot=0,ref_seq=0,rssi=0):
    b=bytearray(64);b[:4]=b'LW\x01'+bytes([kind])
    struct.pack_into('<HHH',b,4,2761,origin,origin);b[10]=3
    b[11]=int(active)|(2 if lat is not None else 0)
    struct.pack_into('<IIHII',b,12,boot,seq,target,ref_boot,ref_seq)
    struct.pack_into('<ii',b,30,int((lat or 0)*1e7),int((lon or 0)*1e7))
    struct.pack_into('<hH',b,42,rssi,origin if kind==3 else 0)
    return json.dumps({'type':'packet','hex':b.hex(),'rssi':-60})
