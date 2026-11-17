"""Independent 2D disk/half-plane feasibility oracle and evidence-based ORCA audit."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from research_data import ROOT,read_json
from newton_safety import rectangle_distance

def feasible_velocity(lines,speed,tolerance=1e-7):
    if not lines:return np.zeros(2)
    p=np.array([l["point"] for l in lines],dtype=float)
    d=np.array([l["direction"] for l in lines],dtype=float)
    # det(d,p-v)<=0 -> normals @ v >= offsets
    normals=np.column_stack((-d[:,1],d[:,0]));offsets=np.sum(normals*p,axis=1)
    norms=np.linalg.norm(normals,axis=1)
    if np.any((norms<1e-12)&(offsets>tolerance)):return None
    valid=norms>1e-12;normals=normals[valid];offsets=offsets[valid];norms=norms[valid]
    if not len(norms):return np.zeros(2)
    u=normals/norms[:,None];h=offsets/norms
    foot=u*h[:,None];direction=np.column_stack((-u[:,1],u[:,0]))
    candidates=[np.zeros((1,2))]
    mask=np.abs(h)<=speed+tolerance
    half=np.sqrt(np.maximum(0,speed*speed-h[mask]*h[mask]))
    candidates.extend([foot[mask]+direction[mask]*half[:,None],foot[mask]-direction[mask]*half[:,None],foot[mask]])
    i,j=np.triu_indices(len(u),1)
    det=u[i,0]*u[j,1]-u[i,1]*u[j,0];mask=np.abs(det)>1e-10
    i,j,det=i[mask],j[mask],det[mask]
    if len(i):
        candidates.append(np.column_stack(((h[i]*u[j,1]-u[i,1]*h[j])/det,
                                           (u[i,0]*h[j]-h[i]*u[j,0])/det)))
    v=np.concatenate(candidates)
    good=(np.linalg.norm(v,axis=1)<=speed+tolerance)&np.all(v@u.T>=h-tolerance,axis=1)
    return v[np.flatnonzero(good)[0]] if good.any() else None

def analyze_failures(df,out,run_root=None):
    rows=[]
    run_root=Path(run_root or ROOT/"results/newton")
    for r in df[df.algorithm=="ORCA"].to_dict("records"):
        folder=run_root/"runs"/r["run_id"]
        result=read_json(folder/"result.json")
        radius=result["bodies"][0]["radius"];width=result["width"];height=result["height"]
        obstacles=result["initial_state"]["obstacles"]
        previous=-2;episode=0
        for line in (folder/"orca_diagnostics.jsonl").open():
            e=json.loads(line);frame=e["frame"];position=np.array(e["robot_after"])
            if frame!=previous+1:episode+=1
            previous=frame
            target_error=float(e["max_target_constraint_residual"]);actual_error=float(e["max_actual_constraint_residual"])
            feasible=feasible_velocity(e["halfplanes"],result["robot_speed_mps"])
            if feasible is None:category="D"
            elif target_error>1e-7:category="A"
            elif actual_error>1e-7:category="B"
            else:category="E"
            neighbors=[]
            for a in e["neighbors"]:
                dp=np.asarray(a["position"])-position;dv=np.asarray(a["velocity"])-e["actual_velocity"]
                neighbors.append({**a,"relative_position_post":dp.tolist(),"relative_velocity_post":dv.tolist(),
                                  "clearance_post_m":float(np.linalg.norm(dp)-radius-a["radius"])})
            dynamic=min((a["clearance_post_m"] for a in neighbors),default=float("inf"))
            static=min([position[0],width-position[0],position[1],height-position[1]]
                       +[rectangle_distance(position,b) for b in obstacles])-radius
            rows.append({"run_id":r["run_id"],"source":"main240","scenario":r["encounter_mode"],"seed":r["seed"],
                         "map":r["map"],"population":r["population_mode"],"agent_count":r["agent_count"],
                         "frame":frame,"episode":episode,"simulation_time_s":e["t"],"category":category,
                         "category_basis":{"A":"output infeasible although independent feasible candidate exists",
                           "B":"output feasible, actual post-step velocity violates pre-step planes",
                           "D":"independent disk/half-plane feasibility test found no feasible speed",
                           "E":"logs do not identify a unique cause"}[category],
                         "noncooperative_C_candidate":bool(category=="E" and e["safety_neighbors"]),
                         "robot_position":json.dumps(e["robot_after"]),"robot_velocity":json.dumps(e["actual_velocity"]),
                         "preferred_velocity":json.dumps(e.get("preferred_velocity")) if e.get("preferred_velocity") is not None else None,
                         "orca_output_velocity":json.dumps(e["target_velocity"]),"actual_newton_velocity":json.dumps(e["actual_velocity"]),
                         "worker_states_relative_post":json.dumps(neighbors),"minimum_clearance_m":min(dynamic,static),
                         "active_orca_constraints":json.dumps(e["halfplanes"]),"constraint_violation_amount":target_error,
                         "actual_constraint_violation_amount":actual_error,"velocity_tracking_error":e["tracking_error_mps"],
                         "feasible_candidate":json.dumps(feasible.tolist()) if feasible is not None else None,
                         "infeasible_fallback":e["infeasible_fallback"],"static_only":not e["safety_neighbors"] and not e["collisions"]})
    result=pd.DataFrame(rows)
    result.to_csv(Path(out)/"orca_failure_analysis.csv",index=False,na_rep="N/A")
    summary={"frames":len(result),"categories":result.category.value_counts().to_dict(),
             "C_causal_count":0,"C_candidates":int(result.noncooperative_C_candidate.sum()),
             "confirmed_output_errors":int(result.category.eq("A").sum()),
             "note":"Frames are correlated, not independent trials. C is not causally identified. E includes static risk; historical preferred velocity is N/A."}
    (Path(out)/"orca_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    # Save representative observed timelines; no interpolation over unlogged gaps.
    selected=[]
    for category in ("A","B","D","E"):
        g=result[result.category==category]
        if len(g):
            rid=g.groupby("run_id").size().sort_values(ascending=False).index[0]
            if rid not in selected:selected.append(rid)
        if len(selected)==3:break
    (Path(out)/"orca_representatives.json").write_text(json.dumps(selected))
    return result
