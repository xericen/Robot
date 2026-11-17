import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from live_payload import metadata_payload,display_indices,read_snapshot
from newton_live import LiveBridge,atomic_json

def test_display_path_is_bounded_and_retains_start_end():
    for length in (1,2,200,256,257,5401):
        ix=display_indices(length)
        assert len(ix)<=256 and ix[0]==0 and ix[-1]==length-1
        assert ix==sorted(set(ix))

def test_large_analysis_logs_do_not_enter_live_metadata():
    source={"algorithm":"ORCA","scene_hash":"same","provenance":{"versions":"x"*10000},
            "diagnostic_events":[{"frame":i} for i in range(1000)],"algorithm_samples_ms":[1]*5400,"telemetry":[1]*5400}
    assert metadata_payload(source)=={"algorithm":"ORCA","scene_hash":"same"}
    assert len(source["diagnostic_events"])==1000

def setup_snapshot(folder,revision=1):
    atomic_json(folder/f"metadata-{revision}.json",{"algorithm":"ORCA","scene_hash":"unchanged","width":38})
    for i in range(4):atomic_json(folder/("frame-%04d.json"%i),{"t":i/30,"robot":[i,0]})
    atomic_json(folder/"status.json",{"metadata_version":f"metadata-{revision}.json","phase":"running","frame_count":4,
                "frame_index":3,"current":{"t":.1},"ack":"same"})

def test_compact_status_avoids_repeating_metadata_but_retains_every_frame(tmp_path):
    setup_snapshot(tmp_path)
    first=read_snapshot(tmp_path,compact=True)
    assert first["algorithm"]=="ORCA" and len(first["frames"])==4
    next_=read_snapshot(tmp_path,since=1,compact=True,metadata_version="metadata-1.json")
    assert "algorithm" not in next_ and [f["t"] for f in next_["frames"]]==[2/30,3/30]
    assert next_["current"]=={"t":.1}
    full=read_snapshot(tmp_path,since=3)
    assert full["algorithm"]=="ORCA" and full["frames"]==[]
    setup_snapshot(tmp_path,2)
    changed=read_snapshot(tmp_path,since=3,compact=True,metadata_version="metadata-1.json")
    assert changed["algorithm"]=="ORCA"

def test_snapshot_revision_blocks_path_traversal(tmp_path):
    atomic_json(tmp_path/"status.json",{"metadata_version":"../private.json"})
    with pytest.raises(ValueError):read_snapshot(tmp_path)

def test_hidden_3d_skips_rendering_without_changing_physics_history():
    bridge=LiveBridge.__new__(LiveBridge)
    bridge.render_fps=10;bridge.render_3d=False;bridge.last_draw=0
    calls=[];bridge.draw=lambda frame:calls.append(frame)
    for i in range(100):bridge.maybe_draw({"t":i/30})
    assert calls==[]
    bridge.render_3d=True
    bridge.maybe_draw({"t":100/30})
    bridge.maybe_draw({"t":101/30})
    assert len(calls)==1

def test_legacy_status_format_still_loads(tmp_path):
    atomic_json(tmp_path/"status.json",{"algorithm":"VO","frame_count":1,"current":{"t":0}})
    atomic_json(tmp_path/"frame-0000.json",{"t":0})
    assert read_snapshot(tmp_path)["algorithm"]=="VO"

def test_heartbeat_keeps_read_only_polling_alive(tmp_path):
    import time
    bridge=LiveBridge.__new__(LiveBridge)
    bridge.folder=tmp_path;bridge.command=lambda:None
    bridge.last_touch=time.monotonic()-1000;bridge.phase="running";bridge.resume_at=0
    (tmp_path/"heartbeat").touch()
    bridge.before_frame()
    assert time.monotonic()-bridge.last_touch<1
