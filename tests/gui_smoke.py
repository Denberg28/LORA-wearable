"""Exercise the actual Tk UI without RF hardware; usable on Windows or Xvfb."""
import argparse
import tempfile
import tkinter as tk
import time
from pathlib import Path
from monitor.app import App
from monitor.field import CaptureWriter
from monitor.simulate import packet

def main():
    with tempfile.TemporaryDirectory() as d:
        root=tk.Tk();a=App(root,argparse.Namespace(data=d,network=2761,anchors=None,demo=False))
        capture_path=Path(d)/'session.jsonl'
        a.capture=CaptureWriter(capture_path)
        a.inbox.put(('line',packet(lat=13.58,lon=123.28)))
        end=time.monotonic()+1.3
        while time.monotonic()<end:
            root.update();time.sleep(.01)
        assert a.table.exists('100')
        assert 'SOS ACTIVE' in a.table.item('100')['values'][1]
        a.table.selection_set('100');a.review()
        assert a.store.rows()[0][-1]==1
        assert a.store.rows()[0][1]==1, 'Review must not cancel SOS'
        a.inbox.put(('line',packet(active=False,seq=2,lat=13.58,lon=123.28)))
        end=time.monotonic()+.7
        while time.monotonic()<end:
            root.update();time.sleep(.01)
        assert a.store.rows()[0][1]==0
        # With a single direct receiver, report coverage but no wearable location.
        a.store.anchors={'10':{'lat':13.58,'lon':123.28}}
        a.inbox.put(('line',packet(origin=101,boot=1,seq=1,lat=None,lon=None)))
        a.inbox.put(('line',packet(origin=10,boot=1,seq=1,kind=3,target=101,
                                    ref_boot=1,ref_seq=1,rssi=-75)))
        end=time.monotonic()+.7
        while time.monotonic()<end:
            root.update();time.sleep(.01)
        assert a.table.exists('101')
        cells=a.table.item('101')['values']
        assert cells[3]=='Unknown', f'Invented wearable coordinates: {cells}'
        assert '10 (-75 dBm)' in cells[5], f'Missing direct hearing: {cells}'
        root.update()
        try:
            from PIL import ImageGrab
            Path('build').mkdir(exist_ok=True)
            x,y=root.winfo_rootx(),root.winfo_rooty()
            ImageGrab.grab(bbox=(x,y,x+root.winfo_width(),y+root.winfo_height())).save('build/monitor-smoke.png')
        except (ImportError,OSError):pass
        a.record() # Stops recording; no dialog when a capture already exists.
        assert '"type": "serial"' in capture_path.read_text()
        class FailedCapture:
            def append(self,event):raise OSError('simulated capture disk failure')
            def close(self):raise OSError('simulated capture close failure')
        a.capture=FailedCapture()
        a.inbox.put(('line',packet(origin=102,seq=1)))
        end=time.monotonic()+.7
        while time.monotonic()<end:
            root.update();time.sleep(.01)
        assert a.table.exists('102'), 'Optional capture failure suppressed an SOS'
        assert a.capture is None
        a.close()
    print('PASS actual Tk startup, packet display, review, cancel and shutdown')

if __name__=='__main__':main()

