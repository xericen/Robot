import json,queue,threading,time
from types import SimpleNamespace
import pytest
from presentation_sync import PresentationSync,can_advance,acknowledged_frame
from viewer_transport import pack_messages,unpack_messages,Connection

class Server:
    def on_client_connect(self,fn):self.connect=fn
    def on_client_disconnect(self,fn):self.disconnect=fn

def test_no_progress_before_actual_client_render():
    server=Server();sync=PresentationSync(server,True);release=threading.Event()
    client=SimpleNamespace(get_render=lambda **kw:release.wait(2))
    assert not can_advance(0,0,True,sync)
    server.connect(client);sync.request(0)
    assert sync.pending and not sync.ready
    assert not can_advance(0,0,True,sync)
    release.set()
    end=time.monotonic()+2
    while sync.pending and time.monotonic()<end:time.sleep(.005)
    assert sync.ready and sync.rendered_frame==0 and can_advance(0,0,True,sync)
    server.disconnect(client)
    assert not can_advance(1,0,True,sync)

def test_parent_backpressure_limits_unseen_frames_and_reset_invalidates_ack(tmp_path):
    sync=PresentationSync(Server(),True)
    assert not can_advance(0,-1,False,sync)
    assert can_advance(5,0,False,sync)
    assert not can_advance(6,0,False,sync)
    (tmp_path/"presented.json").write_text(json.dumps({"frame":100,"metadata_version":"metadata-1.json"}))
    assert acknowledged_frame(tmp_path,"metadata-1.json")==100
    assert acknowledged_frame(tmp_path,"metadata-2.json")==-1

def test_old_render_completion_cannot_ready_reset_scene():
    server=Server();sync=PresentationSync(server,True);release=threading.Event()
    server.connect(SimpleNamespace(get_render=lambda **kw:release.wait(1)))
    sync.request(20);sync.reset();release.set();time.sleep(.03)
    assert not sync.ready and sync.rendered_frame==-1

def test_binary_packets_preserve_order_and_bytes():
    packets=[b"camera",b"\x00\xff"*1000,b"render"]
    assert unpack_messages(pack_messages(packets))==packets
    assert len(pack_messages(packets))==sum(map(len,packets))+12
    for bad in (b"\x00",b"\x00\x00\x00\x05x"):
        with pytest.raises(ValueError):unpack_messages(bad)

def test_poll_budget_keeps_deferred_messages_in_order():
    c=Connection.__new__(Connection);c.messages=queue.Queue();c.deferred=None;c.drain_lock=threading.Lock()
    for x in (b"a"*8,b"b"*8,b"c"*8):c.messages.put(x)
    assert c.drain(max_bytes=10)==[b"a"*8]
    assert c.drain(max_bytes=10)==[b"b"*8]
    assert c.drain(max_bytes=10)==[b"c"*8]

def test_gpu_frame_acknowledgement_bounds_native_scene_lead():
    sync=PresentationSync(Server(),True)
    sync.ready=True;sync.rendered_frame=10
    assert can_advance(15,15,True,sync)
    assert not can_advance(16,16,True,sync)
    sync.presented(13)
    assert can_advance(16,16,True,sync)
    sync.presented(9)
    assert sync.rendered_frame==13
