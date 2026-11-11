"""Exercise the actual Tk UI without RF hardware; usable on Windows or Xvfb."""
import argparse
import tempfile
import tkinter as tk
import time
from pathlib import Path
from monitor.app import App
from monitor.simulate import packet

def main():
    with tempfile.TemporaryDirectory() as d:
        root=tk.Tk();a=App(root,argparse.Namespace(data=d,network=2761,anchors=None,demo=False))
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
        root.update()
        try:
            from PIL import ImageGrab
            Path('build').mkdir(exist_ok=True)
            x,y=root.winfo_rootx(),root.winfo_rooty()
            ImageGrab.grab(bbox=(x,y,x+root.winfo_width(),y+root.winfo_height())).save('build/monitor-smoke.png')
        except (ImportError,OSError):pass
        a.close()
    print('PASS actual Tk startup, packet display, review, cancel and shutdown')

if __name__=='__main__':main()
