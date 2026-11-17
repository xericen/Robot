"""Append-only run directories. Legacy top-level CSVs are compatibility snapshots."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import uuid


def provenance(root):
    def git(*args):
        p=subprocess.run(["git", "-C", str(root), *args],capture_output=True,text=True,timeout=10)
        return p.stdout.strip() if p.returncode==0 else None
    files=[*root.glob("*.py"),*root.glob("algorithms/*.py"),*root.glob("simulator/*.py"),
           *root.glob("experiments/*.py"), root/"warehouse_maps.json",root/"requirements-newton.txt"]
    return {"python":platform.python_version(),"platform":platform.platform(),
            "git_commit":git("rev-parse","HEAD"),
            "git_dirty":bool(git("status","--porcelain","--",str(root))),
            "source_sha256":{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in sorted(files) if p.exists()},
            "dependencies":{d.metadata["Name"]:d.version for d in importlib.metadata.distributions()
                            if d.metadata["Name"]}}


def archive_result(result, output):
    from newton_results import result_row, write_rows
    root=Path(__file__).resolve().parent
    run_id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+"_"+uuid.uuid4().hex[:12]
    folder=Path(output)/"runs"/run_id
    folder.mkdir(parents=True,exist_ok=False)
    result["run_id"]=run_id
    configuration={key:result.get(key) for key in (
        "mapId","scenario","algorithm","seed","agent_count","worker_count","other_robot_count",
        "parameters","planner","planner_seed","traffic_mode","common_traffic","frame_limit",
        "requested_frame_limit","safety_distance_m","robot_speed_mps","encounter_mode","population_mode",
        "encounter","scene_hash","newton_version","warp_version","device","width","height",
        "map_config","shelf_poses","bodies","capture_telemetry","telemetry_schema","stop_threshold_mps","research_scenario_label")}
    def dump(name,value):
        (folder/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False))
    dump("configuration.json",configuration)
    dump("initial_state.json",result.get("initial_state",{}))
    dump("provenance.json",result.get("provenance") or provenance(root))
    with (folder/"orca_diagnostics.jsonl").open("w") as f:
        for event in result.get("diagnostic_events",[]):
            f.write(json.dumps(event,ensure_ascii=False,allow_nan=False)+"\n")
    # Separate trajectory snapshots from the compact result summary.
    dump("trajectory.json",result.get("frames",[]))
    if result.get("algorithm_samples_ms") is not None:
        dump("algorithm_samples_ms.json",result["algorithm_samples_ms"])
    if result.get("telemetry"):
        with (folder/"telemetry.jsonl").open("w") as f:
            for frame in result["telemetry"]:
                f.write(json.dumps(frame,ensure_ascii=False,allow_nan=False)+"\n")
    dump("result.json",{k:v for k,v in result.items()
                        if k not in ("frames","diagnostic_events","provenance","algorithm_samples_ms","telemetry")})
    write_rows(folder/"metrics.csv",[result_row(result)])
    dump("complete.json",{"run_id":run_id,"complete":True})
    return run_id
