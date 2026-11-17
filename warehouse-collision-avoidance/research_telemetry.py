"""Derive operational encounter measures from complete supplemental Newton frames only."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

def enrich(out):
    out=Path(out)
    d=pd.read_csv(out/"supplemental_measurements.csv")
    rows=[]
    for row in d.to_dict("records"):
        folder=out/"runs"/row["run_id"];r=json.loads((folder/"result.json").read_text())
        frames=[json.loads(line) for line in (folder/"telemetry.jsonl").open()]
        samples=json.loads((folder/"algorithm_samples_ms.json").read_text())
        if len(samples)!=row["algo_steps"] or len(frames)!=row["algo_steps"]:raise ValueError("Incomplete telemetry")
        if not np.isclose(np.percentile(samples,95),row["algo_time_p95_ms"]):raise ValueError("P95 mismatch")
        path=np.asarray(r["initial_state"]["path"]);a,b=path[:-1],path[1:];delta=b-a
        denom=np.sum(delta*delta,axis=1)
        entries={};crossings={};actor0=r["encounter"]["actors"][0]
        touches=0;active=False
        for f in frames:
            touching=actor0["id"]+"_shape" in f["contact_labels"]
            if touching and not active:touches+=1
            active=touching
            for actor in f["neighbors_after"]:
                p=np.asarray(actor["position"])
                t=np.clip(np.sum((p-a)*delta,axis=1)/denom,0,1)
                distance=np.min(np.linalg.norm(p-(a+t[:,None]*delta),axis=1))
                if distance <= .42+actor["radius"]+r["safety_distance_m"] and actor["id"] not in entries:
                    entries[actor["id"]]=f["t"]
                initial=next(x for x in r["encounter"]["actors"] if x["id"]==actor["id"])
                origin=np.asarray(initial["position"]);goal=np.asarray(initial["goal"]);axis=goal-origin
                if r["encounter_mode"]=="crossing" and np.dot(p-(origin+goal)/2,axis)>=0 and actor["id"] not in crossings:
                    crossings[actor["id"]]=f["t"]
        row.update(actor_path_band_entry_s=json.dumps(entries),actor_first_crossing_s=json.dumps(crossings),
                   head_on_actor0_contact_count=touches if r["encounter_mode"]=="head_on" else None,
                   passage_success=int(r["collision_free_success"]) if r["encounter_mode"]=="narrow_passing" else None,
                   entry_definition="actual post-step actor enters protected radius band around existing global path",
                   stop_definition="actual XY speed <0.05m/s while goal farther than0.25m; >5s is a stop candidate, not proven deadlock")
        rows.append(row)
    result=pd.DataFrame(rows)
    result.to_csv(out/"supplemental_analysis.csv",index=False,na_rep="N/A")
    return result
