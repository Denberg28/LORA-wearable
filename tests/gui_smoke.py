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
        def until(predicate):
            deadline=time.monotonic()+3
            while not predicate() and time.monotonic()<deadline:
                root.update();time.sleep(.01)
            assert predicate(), 'UI did not reach expected state within 3 seconds'
        try:
            capture_path=Path(d)/'session.jsonl'
            a.capture=CaptureWriter(capture_path)
            a.inbox.put(('line',packet(lat=13.58,lon=123.28)))
            until(lambda:a.table.exists('100'))
            assert 'SOS ACTIVE' in a.table.item('100')['values'][1]
            a.table.selection_set('100');a.review()
            assert a.store.rows()[0][-1]==1
            assert a.store.rows()[0][1]==1, 'Review must not cancel SOS'
            a.inbox.put(('line',packet(active=False,seq=2,lat=13.58,lon=123.28)))
            until(lambda:a.store.rows()[0][1]==0)
            # With a single direct receiver, report coverage but no wearable location.
            a.store.configure_anchors({'10':{'lat':13.58,'lon':123.28}})
            a.inbox.put(('line',packet(origin=101,boot=1,seq=1,lat=None,lon=None)))
            a.inbox.put(('line',packet(origin=10,boot=1,seq=1,kind=3,target=101,
                                       ref_boot=1,ref_seq=1,rssi=-75)))
            until(lambda:a.table.exists('101') and '10 (-75 dBm)' in a.table.item('101')['values'][5])
            cells=a.table.item('101')['values']
            assert cells[3]=='Unknown', f'Invented wearable coordinates: {cells}'
            # Every packet in this tick uses the same processing instant: direct
            # sightings cannot be excluded as future observations on first render.
            row=a.store.db.execute('SELECT seen FROM devices WHERE id=101').fetchone()
            observation=a.store.db.execute('SELECT at FROM observations WHERE target=101').fetchone()
            assert row[0]==observation[0], 'Batch timestamp mismatch'
            root.update()
            try:
                from PIL import ImageGrab
                Path('build').mkdir(exist_ok=True)
                x,y=root.winfo_rootx(),root.winfo_rooty()
                ImageGrab.grab(bbox=(x,y,x+root.winfo_width(),y+root.winfo_height())).save('build/monitor-smoke.png')
            except (ImportError,OSError):pass
            a.record() # Stops recording; no dialog when already recording.
            assert '"type": "serial"' in capture_path.read_text()
            class FailedCapture:
                def append(self,event):raise OSError('simulated capture disk failure')
                def close(self):raise OSError('simulated capture close failure')
            a.capture=FailedCapture()
            a.inbox.put(('line',packet(origin=102,seq=1)))
            until(lambda:a.table.exists('102'))
            assert a.capture is None, 'Capture failure suppressed live SOS'
        finally:
            a.close()
    print('PASS Tk startup, packet/coverage display, review, cancel, recording failure and shutdown')


if __name__=='__main__':main()
