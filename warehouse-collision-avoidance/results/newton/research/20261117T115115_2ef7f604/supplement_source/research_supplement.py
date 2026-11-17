"""Only missing instrumentation is rerun. Existing experiment inputs are read-only."""
from __future__ import annotations
import argparse,contextlib,io,json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from newton_warehouse import run
from newton_results import result_row,write_rows
from experiment_archive import archive_result
from research_data import ROOT

def first_time(frames,predicate):
    return next((f["t"] for f in frames if predicate(f)),None)

def summarize(result):
    frames=result["telemetry"]
    reaction=first_time(frames,lambda f: np.linalg.norm(np.asarray(f["target_velocity"])-f["preferred_velocity"])>.05
                         and min((np.linalg.norm(np.asarray(n["position"])-f["robot_before"]) for n in f["neighbors_before"]),default=999)<4.)
    decel=None
    for before,after in zip(frames,frames[1:]):
        dt=after["t"]-before["t"]
        old=np.linalg.norm(before["velocity"]);new=np.linalg.norm(after["velocity"])
        if old>.2 and (new-old)/dt<-.1 and min((np.linalg.norm(np.asarray(n["position"])-after["robot"]) for n in after["neighbors_after"]),default=999)<4:
            decel=after["t"];break
    movements={}
    for a in result["encounter"]["actors"]:
        movements[a["id"]]=first_time(frames,lambda f: any(n["id"]==a["id"] and np.linalg.norm(n["velocity"])>.05 for n in f["neighbors_after"]))
    return {"avoidance_response_s":reaction,"deceleration_onset_s":decel,
            "actor_observed_move_s":json.dumps(movements),
            "actor_release_command_s":json.dumps({a["id"]:a["release_time_s"] for a in result["encounter"]["actors"]}),
            "extra_path_length_m":result["path_length_m"]-result["planned_path_length_m"],
            "stop_candidate_5s":int(result["longest_stop_s"]>=5),
            "head_on_actor0_contact_count":None,
            "interpretation":"one seed supplemental, no population-level CI; stop/decel/response are operational definitions"}

def main():
    p=argparse.ArgumentParser();p.add_argument("output",type=Path);p.add_argument("--frames",type=int,default=5400)
    args=p.parse_args();folder=args.output
    (folder/"supplement_source").mkdir()
    paths=[*ROOT.glob("*.py"),*ROOT.glob("algorithms/*.py"),*ROOT.glob("simulator/*.py"),*ROOT.glob("experiments/*.py"),ROOT/"warehouse_maps.json"]
    hashes={}
    for path in paths:
        rel=path.relative_to(ROOT);dest=folder/"supplement_source"/rel
        dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(path.read_bytes())
        hashes[str(rel)]=hashlib.sha256(path.read_bytes()).hexdigest()
    (folder/"supplement_source"/"sha256.json").write_text(json.dumps(hashes,indent=2))
    cases=[("Crossing","crossing",p,n) for p in ("workers","mixed") for n in (2,4,8,16)]
    cases += [("Head-On","head_on","workers",4),("Narrow Passage","narrow_passing","workers",4)]
    rows=[]
    for label,mode,population,n in cases:
        hashes=[]
        for algorithm in ("naive","vo","orca"):
            with contextlib.redirect_stdout(io.StringIO()):
                r=run(algorithm_name=algorithm,scenario_name="crowded",agent_count=n,seed=42,frames=args.frames,
                      encounter_mode=mode,population_mode=population,capture_telemetry=True,persist=False,quiet=True,trace_stride=60)
            r["research_scenario_label"]="Dense Traffic" if mode=="crossing" and n>=8 else label
            archive_result(r,folder)
            row=result_row(r);row.update(scenario_label=r["research_scenario_label"],source="supplemental_seed42",
                                        **summarize(r))
            rows.append(row);hashes.append(r["scene_hash"])
            pd.DataFrame(rows).to_csv(folder/"supplemental_measurements.csv",index=False,na_rep="N/A")
            print(f'{len(rows)}/30 {label} {population} n={n} {algorithm} {r["status"]}',flush=True)
        if len(set(hashes))!=1:raise ValueError("Supplemental paired scene mismatch")
    (folder/"supplement_complete.json").write_text(json.dumps({"runs":len(rows),"frames":args.frames,"seed":42,
        "reason":"frame runtime distribution, LP inner counters, stop and reaction telemetry missing historically",
        "not_pooled_with_240":True},indent=2))

if __name__=="__main__":main()
