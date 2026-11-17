"""Backpressure from the actual Viser render and the parent dashboard's presented frame."""
from __future__ import annotations
import json,threading,time

class PresentationSync:
    def __init__(self,server,enabled=False):
        self.enabled=enabled;self.client=None;self.ready=False;self.pending=False
        self.rendered_frame=-1;self.error="";self.changed=False;self.last_latency_ms=0.
        self.lock=threading.RLock();self.generation=0
        if enabled:
            server.on_client_connect(self.connect)
            server.on_client_disconnect(self.disconnect)

    def connect(self,client):
        with self.lock:
            self.client=client;self.ready=False;self.pending=False;self.generation+=1;self.changed=True

    def disconnect(self,client):
        with self.lock:
            if self.client is client:
                self.client=None;self.ready=False;self.pending=False;self.generation+=1;self.changed=True

    def request(self,frame):
        if not self.enabled:return
        with self.lock:
            if self.client is None or self.pending:return
            client=self.client;generation=self.generation
            self.pending=True;self.changed=True
        def capture():
            start=time.perf_counter()
            try:
                client.get_render(height=16,width=16,timeout=10)
                with self.lock:
                    if self.client is client and self.generation==generation:
                        self.ready=True;self.rendered_frame=frame;self.error=""
            except Exception as error:
                with self.lock:
                    if self.generation==generation:self.ready=False;self.error=type(error).__name__
            finally:
                with self.lock:
                    if self.generation==generation:
                        self.pending=False;self.changed=True;self.last_latency_ms=(time.perf_counter()-start)*1000
        threading.Thread(target=capture,daemon=True).start()

    def presented(self,frame):
        with self.lock:
            self.rendered_frame=max(self.rendered_frame,int(frame));self.changed=True

    def reset(self):
        with self.lock:
            self.generation+=1;self.ready=False;self.pending=False;self.rendered_frame=-1;self.changed=True

def acknowledged_frame(folder,version):
    try:
        data=json.loads((folder/"presented.json").read_text())
        return int(data["frame"]) if data["metadata_version"]==version else -1
    except (OSError,ValueError,KeyError,TypeError):
        return -1

def can_advance(cursor,ack,render_3d,sync,max_lead=6):
    if not sync.enabled:return True
    if ack<0 or cursor-ack>=max_lead:return False
    return not render_3d or (sync.ready and not sync.pending and cursor-sync.rendered_frame<max_lead)
