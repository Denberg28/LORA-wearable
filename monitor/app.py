"""Run with python -m monitor.app. Tk UI stays independent of serial I/O."""
import argparse
import csv
import json
import math
import os
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from .model import Store, load_anchors

VERSION='0.1.0-rc.1'

class SerialWorker(threading.Thread):
    def __init__(self, port, inbox, stop):
        super().__init__(daemon=True)
        self.port,self.inbox,self.stop=port,inbox,stop

    def emit(self,item):
        try:
            self.inbox.put_nowait(item)
        except queue.Full:
            # Never silently lose alerts. Stop transport and surface overflow on UI.
            self.stop.set()

    def run(self):
        import serial
        while not self.stop.is_set():
            try:
                with serial.Serial(self.port,115200,timeout=.2,write_timeout=.2) as port:
                    self.emit(('connection','USB open; awaiting gateway heartbeat'))
                    buf=bytearray()
                    while not self.stop.is_set():
                        part=port.read(256)
                        for byte in part:
                            if byte==10:
                                self.emit(('line',bytes(buf).decode('ascii',errors='strict')))
                                buf.clear()
                            elif len(buf)<1024:
                                buf.append(byte)
                            else:
                                raise ValueError('oversized serial frame')
            except (serial.SerialException,OSError,ValueError,UnicodeError) as e:
                self.emit(('connection',f'Link unavailable: {e}; retrying'))
                self.stop.wait(2)

class App:
    def __init__(self,root,args):
        self.root=root;self.args=args
        self.data=Path(args.data).resolve();self.data.mkdir(parents=True,exist_ok=True)
        anchors=load_anchors(Path(args.anchors)) if args.anchors else {}
        self.store=Store(self.data/'events.sqlite3',args.network,anchors)
        self.inbox=queue.Queue(maxsize=1024);self.worker=None;self.stop=threading.Event()
        self.last_health=0;self.last_alarm=0;self.connected=False;self.rejected=0
        self.error_state=None
        root.title(f'LORA wearable · {VERSION}');root.geometry('1100x720');root.minsize(860,580)
        style=ttk.Style();style.theme_use('clam');style.configure('Treeview',rowheight=30)
        top=ttk.Frame(root,padding=16);top.pack(fill='x')
        ttk.Label(top,text='LORA wearable',font=('Segoe UI',20,'bold')).pack(side='left')
        ttk.Label(top,text='  Emergency monitoring · TEST CANDIDATE',foreground='#ad5200').pack(side='left')
        tools=ttk.Frame(root,padding=(16,0,16,10));tools.pack(fill='x')
        self.port=tk.StringVar();self.ports=ttk.Combobox(tools,textvariable=self.port,width=17)
        self.ports.pack(side='left');ttk.Button(tools,text='Refresh ports',command=self.refresh_ports).pack(side='left',padx=4)
        self.connect_button=ttk.Button(tools,text='Connect',command=self.toggle);self.connect_button.pack(side='left')
        ttk.Button(tools,text='Review selected alert',command=self.review).pack(side='left',padx=8)
        ttk.Button(tools,text='Export event history',command=self.export).pack(side='right')
        self.status=tk.StringVar(value='DEMO · simulated signals' if args.demo else 'Disconnected')
        ttk.Label(root,textvariable=self.status,padding=(16,6)).pack(fill='x')
        cols=('id','status','seen','position','method','review')
        self.table=ttk.Treeview(root,columns=cols,show='headings',height=7,selectmode='browse')
        for col,label,width in zip(cols,('Wearable','Alert / link','Last received','Coordinates','Location source','Operator'),(85,150,100,240,210,100)):
            self.table.heading(col,text=label);self.table.column(col,width=width)
        self.table.tag_configure('sos',background='#ffe0dc',foreground='#8c1515')
        self.table.tag_configure('stale',foreground='#846200');self.table.pack(fill='x',padx=16)
        self.canvas=tk.Canvas(root,bg='#10212e',highlightthickness=0);self.canvas.pack(fill='both',expand=True,padx=16,pady=12)
        ttk.Label(root,text='Offline position plot · RSSI is approximate · Review does not cancel SOS · Gateway receipt does not confirm rescue',padding=(16,0,16,12)).pack(fill='x')
        self.refresh_ports();root.protocol('WM_DELETE_WINDOW',self.close)
        if args.demo:
            old=self.store.db.execute('SELECT MAX(boot) FROM ordering WHERE id=100').fetchone()[0] or 0
            self.demo_boot=old+1;self.demo_step=0;root.after(100,self.demo)
        root.after(200,self.tick)

    def refresh_ports(self):
        try:
            from serial.tools import list_ports
            self.ports['values']=[p.device for p in list_ports.comports()]
            if not self.port.get() and self.ports['values']:
                self.port.set(self.ports['values'][0])
        except ImportError:
            self.status.set('Install requirements.txt to connect USB serial')

    def toggle(self):
        if self.args.demo:
            return
        if self.worker and self.worker.is_alive():
            self.stop.set();self.connected=False;self.status.set('Disconnecting…');return
        if not self.port.get():
            return
        self.error_state=None
        self.stop=threading.Event();self.worker=SerialWorker(self.port.get(),self.inbox,self.stop)
        self.worker.start();self.connected=True;self.last_health=0;self.connect_button.config(text='Disconnect')

    def review(self):
        chosen=self.table.selection()
        if chosen:
            self.store.review(int(chosen[0]))

    def export(self):
        target=filedialog.asksaveasfilename(defaultextension='.csv',initialfile='lora-events.csv')
        if target:
            try:
                with open(target,'w',newline='',encoding='utf-8') as f:
                    out=csv.writer(f);out.writerow(('UTC epoch','device','SOS active','boot','sequence'))
                    out.writerows(self.store.db.execute('SELECT * FROM events ORDER BY at'))
            except OSError as e:
                messagebox.showerror('Export failed',str(e))

    def tick(self):
        now=time.time()
        for _ in range(100):
            try:
                kind,line=self.inbox.get_nowait()
            except queue.Empty:
                break
            if kind=='connection':
                self.status.set(line);self.last_health=0
            else:
                try:
                    data=json.loads(line)
                    if data.get('type')=='health':
                        self.error_state=None
                        self.last_health=now
                        self.status.set(f"Gateway {data['id']} online · queue drops {data['dropped']} · rejected {data['bad']} · TX errors {data['tx_errors']} · local rejected {self.rejected}")
                    elif data.get('type')=='fault':
                        self.last_health=0;self.error_state=f"GATEWAY FAULT: {data.get('reason')}"
                        self.status.set(self.error_state)
                    else:
                        self.store.ingest(line)
                except (ValueError,TypeError,KeyError,AttributeError):
                    self.rejected+=1
                except Exception as e:
                    # Persistence failure must be visible; never claim an alert was recorded.
                    self.stop.set();self.error_state=f'STORAGE ERROR: {e}';self.status.set(self.error_state)
        if self.worker and not self.worker.is_alive():
            self.connected=False;self.connect_button.config(text='Connect')
            if self.stop.is_set() and not self.error_state:self.status.set('Disconnected / transport stopped; reconnect to resume')
        elif self.connected and not self.error_state and (not self.last_health or now-self.last_health>12):
            self.status.set('Gateway heartbeat missing · alerts may not be reaching this monitor')
        selected=self.table.selection()
        for item in self.table.get_children():self.table.delete(item)
        rows=self.store.rows();positions=[];alarm=False
        for dev,active,seen,lat,lon,fixed,method,uncertainty,reviewed in rows:
            stale=now-seen>150
            label=('SOS ACTIVE' if active else 'Idle')+(' · STALE' if stale else '')
            age=int(max(0,now-seen));valid=fixed is not None and now-fixed<=30
            pos=f'{lat:.6f}, {lon:.6f}' if lat is not None else 'Unknown'
            source=method if valid else ('Last known · stale' if lat is not None else 'Unknown')
            if valid and uncertainty:source+=f' ±{uncertainty:.0f} m (indicative)'
            self.table.insert('', 'end',iid=str(dev),values=(dev,label,f'{age}s ago',pos,source,'Reviewed' if reviewed else 'Unreviewed'),tags=('sos' if active else ('stale' if stale else ''),))
            if lat is not None:positions.append((dev,lat,lon,active,valid,uncertainty or 0))
            alarm |= bool(active and not reviewed)
        for item in selected:
            if self.table.exists(item):self.table.selection_set(item)
        if alarm and now-self.last_alarm>5:
            self.root.bell();self.last_alarm=now
        self.plot(positions)
        self.root.after(500,self.tick)

    def plot(self,positions):
        c=self.canvas;c.delete('all');w,h=max(c.winfo_width(),200),max(c.winfo_height(),150)
        if not positions:
            c.create_text(w/2,h/2,text='No location yet\nAdd GNSS or three surveyed receiver nodes',fill='#a7c2d1',font=('Segoe UI',15),justify='center');return
        lat0=sum(p[1] for p in positions)/len(positions);lon0=sum(p[2] for p in positions)/len(positions)
        points=[(p,(p[2]-lon0)*111320*math.cos(math.radians(lat0)),(p[1]-lat0)*111320) for p in positions]
        extent=max(200,max(max(abs(x),abs(y))+p[5] for p,x,y in points));scale=min(w-100,h-100)/(2*extent)
        for x in range(0,w,50):c.create_line(x,0,x,h,fill='#1c3646')
        for y in range(0,h,50):c.create_line(0,y,w,y,fill='#1c3646')
        c.create_text(18,16,anchor='nw',text=f'N ↑     center {lat0:.5f}, {lon0:.5f}     width ≈ {w/scale:.0f} m',fill='#a7c2d1')
        for p,x,y in points:
            dev,lat,lon,active,valid,unc=p;x=w/2+x*scale;y=h/2-y*scale
            color='#ff6868' if active else '#58d9b6'
            if not valid:color='#8997a0'
            if unc:
                r=unc*scale;c.create_oval(x-r,y-r,x+r,y+r,outline=color,dash=(4,4))
            c.create_oval(x-6,y-6,x+6,y+6,fill=color,outline='')
            c.create_text(x+12,y,anchor='w',text=str(dev),fill=color,font=('Segoe UI',12,'bold'))

    def demo(self):
        from .simulate import packet
        self.demo_step+=1
        p=packet(seq=self.demo_step,boot=self.demo_boot,active=self.demo_step>=3,lat=13.58+self.demo_step*.00001,lon=123.28)
        self.inbox.put(('line',p));self.root.after(3000,self.demo)

    def close(self):
        self.stop.set()
        if self.worker:self.worker.join(timeout=1)
        self.store.db.close();self.root.destroy()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--demo',action='store_true');parser.add_argument('--network',type=int,default=2761)
    parser.add_argument('--anchors');parser.add_argument('--data',default=str(Path(os.getenv('LOCALAPPDATA',Path.home()))/'LORA-wearable'))
    args=parser.parse_args()
    if args.demo:
        args.data=str(Path(args.data)/'demo')
    root=tk.Tk()
    try:
        App(root,args)
    except Exception as e:
        messagebox.showerror('Startup failed',str(e));root.destroy();raise
    root.mainloop()

if __name__=='__main__':main()
