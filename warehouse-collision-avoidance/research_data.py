"""Read-only research inputs and integrity audit. Historical files are never rewritten."""
from __future__ import annotations
import csv,hashlib,json,subprocess,urllib.request
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
MAIN=ROOT/"results/newton/studies/20261117T094214513880Z_fc56a91c"
PILOT=ROOT/"results/newton/studies/20261117T093838421883Z_01843a5b"

def read_json(path):return json.loads(Path(path).read_text())
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def git(*args):
    p=subprocess.run(["git","-C",str(ROOT),*args],capture_output=True,text=True,timeout=15)
    return p.stdout.strip() if p.returncode==0 else None

def inputs():
    d=pd.read_csv(MAIN/"measurements.csv")
    pilot=pd.read_csv(PILOT/"measurements.csv")
    return d,pilot

def original_paths():
    paths={MAIN/"measurements.csv",PILOT/"measurements.csv"}
    for folder in (MAIN,PILOT):
        paths.update(folder.glob("*.json"));paths.update(folder.glob("*.csv"))
    for d in inputs():
        for rid in d.run_id:
            paths.update((ROOT/"results/newton/runs"/rid).glob("*"))
    paths.update((ROOT/"results/csv").glob("*"));paths.update((ROOT/"results/figures").glob("*"))
    paths.update((ROOT/"results/newton").glob("map*_*.csv"))
    sweep=ROOT/"results/newton/sweep_agent_count.csv"
    if sweep.exists():paths.add(sweep)
    return sorted(p for p in paths if p.is_file())

def audit():
    d,pilot=inputs()
    keys=["map","encounter_mode","population_mode","agent_count","seed","algorithm"]
    issues=[]
    if len(d)!=240:issues.append("run_count")
    if d.duplicated(keys).any() or d.run_id.duplicated().any():issues.append("duplicate")
    if not d.groupby(keys[:-1]).size().eq(3).all():issues.append("missing_algorithm")
    if not d.groupby(keys[:-1]).scene_hash.nunique().eq(1).all():issues.append("unpaired_scene")
    if not d.groupby(["population_mode","agent_count","algorithm"]).size().eq(10).all():issues.append("missing_seed")
    hashes={str(p.relative_to(ROOT)):digest(p) for p in original_paths()}
    versions={};bad=[];recomputed={"success":0,"collision_free_success":0,"safe_success":0}
    for row in d.to_dict("records"):
        folder=ROOT/"results/newton/runs"/row["run_id"]
        if not (folder/"complete.json").exists():issues.append("incomplete_archive");continue
        r=read_json(folder/"result.json");c=read_json(folder/"configuration.json")
        last=read_json(folder/"trajectory.json")[-1]
        success=int(np.linalg.norm(np.array(last["robot"])-r["goal"])<=.25 and np.linalg.norm(last["velocity"])<=.02)
        collision_free=int(success and r["collisions"]==0)
        safe=int(collision_free and r["safety_violations"]==0 and r["static_safety_violations"]==0
                 and (r["min_dynamic_clearance_m"] is None or r["min_dynamic_clearance_m"]>=r["safety_distance_m"]-1e-6)
                 and r["min_static_clearance_m"]>=r["safety_distance_m"]-1e-6)
        for k,v in zip(recomputed,(success,collision_free,safe)):
            recomputed[k]+=v
            if v!=row[k]:bad.append({"run_id":row["run_id"],"field":k})
        for a,b in (("path_length_m","path_length_m"),("collision_count","collisions"),
                    ("safety_violation_count","safety_violations"),("algo_time_avg_ms","algo_time_avg_ms")):
            if not np.isclose(row[a],r[b],rtol=1e-12,atol=1e-12):bad.append({"run_id":row["run_id"],"field":a})
        if (c["agent_count"]!=row["agent_count"] or c["frame_limit"]!=5400 or c["planner"]!="astar"
            or c["traffic_mode"]!="dynamic" or c["seed"]!=row["seed"]):bad.append({"run_id":row["run_id"],"field":"configuration"})
        if row["timeout"]==1 and pd.notna(row["arrival_time_s"]):bad.append({"run_id":row["run_id"],"field":"failed_arrival"})
        if row["population_mode"]=="workers" and row["other_robot_count"]!=0:bad.append({"run_id":row["run_id"],"field":"population"})
        if row["population_mode"]=="mixed" and row["other_robot_count"]!=row["agent_count"]//4:bad.append({"run_id":row["run_id"],"field":"population"})
        provenance=read_json(folder/"provenance.json")
        for name,h in provenance["source_sha256"].items():versions.setdefault(name,set()).add(h)
    remote={}
    try:
        def get(url):
            return json.load(urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Robot-research-audit"}),timeout=20))
        commit=get("https://api.github.com/repos/xericen/Robot/commits/main")
        tree=get("https://api.github.com/repos/xericen/Robot/git/trees/"+commit["sha"]+"?recursive=1")
        remote={"url":"https://github.com/xericen/Robot","head":commit["sha"],"date":commit["commit"]["committer"]["date"],
                "truncated":tree.get("truncated",False),"tree_entries":len(tree["tree"]),
                "main_240_paths":[v["path"] for v in tree["tree"] if MAIN.name in v["path"]]}
    except Exception as e:remote={"error":str(e),"verified":False}
    return {"totals":{"total":len(d),**recomputed},"expected_match":recomputed=={"success":227,"collision_free_success":152,"safe_success":53},
            "issues":issues,"mismatches":bad,"timeouts":int(d.timeout.sum()),"pilot_runs":len(pilot),
            "git":{"branch":git("branch","--show-current"),"head":git("rev-parse","HEAD"),"remotes":git("remote","-v"),
                   "tracked_changes":git("status","--short","--untracked-files=no"),
                   "scope_changes":git("status","--short","--","warehouse-collision-avoidance","src/app/page.algorithm.run")},
            "github":remote,"source_versions":{k:sorted(v) for k,v in versions.items()},
            "version_caution":"Run metadata records dirty WIZ worktree HEAD and per-file hashes; it is not proof of a clean Robot Git commit. Source hash variation during the historical study is retained.",
            "original_sha256":hashes,
            "missing_historical_metrics":["robot_stop_time_s","algo_time_median_ms","algo_time_p95_ms",
                "lp_pair_evaluations","preferred_velocity","deceleration_onset_s","avoidance_response_s"]}

def assert_originals(audit):
    changed=[p for p,h in audit["original_sha256"].items() if not (ROOT/p).exists() or digest(ROOT/p)!=h]
    if changed:raise RuntimeError("Original input changed: "+str(changed))
    return True
