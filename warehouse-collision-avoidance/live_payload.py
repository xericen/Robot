"""Small live status envelopes; complete physics frames and archives remain intact."""
from __future__ import annotations
import json,re
from pathlib import Path

HEAVY_FIELDS={"frames","provenance","diagnostic_events","algorithm_samples_ms","telemetry"}

def metadata_payload(metadata):
    return {k:v for k,v in metadata.items() if k not in HEAVY_FIELDS}

def display_indices(length,limit=256):
    if length<=limit:return list(range(length))
    return [round(i*(length-1)/(limit-1)) for i in range(limit)]

def read_snapshot(folder,since=-1,compact=False,metadata_version="",fresh=False):
    folder=Path(folder)
    state=json.loads((folder/"status.json").read_text())
    version=state.get("metadata_version","")
    result={}
    if version:
        if not re.fullmatch(r"metadata-[0-9]+\.json",version):
            raise ValueError("Invalid live metadata revision")
        if not compact or metadata_version!=version:
            result.update(json.loads((folder/version).read_text()))
    result.update(state)
    start=0 if fresh else max(0,since+1)
    result["frames"]=[json.loads((folder/("frame-%04d.json"%i)).read_text())
                      for i in range(start,result["frame_count"])]
    result["token"]=folder.name
    result["viewer_url"]="/warehouse-viewer/"+folder.name
    return result
