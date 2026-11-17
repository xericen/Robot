"""Seed-cluster paired statistics. Configurations/frames sharing a seed are not iid trials."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

METRICS=["success","collision_free_success","safe_success","collision_count","safety_violation_count",
         "static_safety_violation_count","min_separation_m","path_length_m","arrival_time_s",
         "replan_count","algo_time_avg_ms","algo_time_median_ms","algo_time_p95_ms","robot_stop_time_s",
         "algo_time_max_ms","neighbor_checks","candidate_checks","constraints",
         "constraint_evaluations","lp_pair_evaluations"]
PAIR_KEYS=["map","encounter_mode","population_mode","agent_count","seed"]

def cluster_ci(values,seeds,iterations=3000,seed=20261117):
    v=np.asarray(values,dtype=float);s=np.asarray(seeds)
    mask=np.isfinite(v);v,s=v[mask],s[mask]
    groups=np.unique(s)
    if len(groups)<2:return (None,None,len(groups))
    sums=np.array([v[s==g].sum() for g in groups]);counts=np.array([(s==g).sum() for g in groups])
    rng=np.random.default_rng(seed)
    index=rng.integers(0,len(groups),(iterations,len(groups)))
    estimates=sums[index].sum(axis=1)/counts[index].sum(axis=1)
    lo,hi=np.percentile(estimates,[2.5,97.5])
    return float(lo),float(hi),len(groups)

def describe(g,column):
    if column not in g:return {"mean":None,"median":None,"std":None,"min":None,"max":None,
                               "ci95_low":None,"ci95_high":None,"observations":0,"seed_clusters":0}
    v=pd.to_numeric(g[column],errors="coerce");valid=v.dropna()
    lo,hi,nseed=cluster_ci(v,g.seed)
    return {"mean":float(valid.mean()) if len(valid) else None,"median":float(valid.median()) if len(valid) else None,
            "std":float(valid.std()) if len(valid)>1 else None,"min":float(valid.min()) if len(valid) else None,
            "max":float(valid.max()) if len(valid) else None,"ci95_low":lo,"ci95_high":hi,
            "observations":len(valid),"seed_clusters":nseed}

def comparison(g,context):
    row=dict(context);row["total_runs"]=len(g)
    for metric in METRICS:
        desc=describe(g,metric)
        row.update({metric+"_"+k:v for k,v in desc.items()})
    for metric in ("success","collision_free_success","safe_success"):
        row[metric+"_count"]=int(g[metric].sum())
        row[metric+"_denominator"]=len(g)
        row[metric+"_rate_pct"]=100*g[metric].mean()
    row["safety_all_count_mean"]=(g.safety_violation_count+g.static_safety_violation_count).mean()
    return row

def paired_differences(df):
    rows=[]
    for a,b in (("VO","Naive"),("ORCA","Naive"),("ORCA","VO")):
        x=df[df.algorithm==a];y=df[df.algorithm==b]
        joined=x.merge(y,on=PAIR_KEYS,suffixes=("_a","_b"),validate="one_to_one")
        if not joined.scene_hash_a.eq(joined.scene_hash_b).all():raise ValueError("paired scene mismatch")
        for metric in METRICS:
            if metric+"_a" not in joined:continue
            delta=pd.to_numeric(joined[metric+"_a"],errors="coerce")-pd.to_numeric(joined[metric+"_b"],errors="coerce")
            valid=delta.notna()
            lo,hi,nseed=cluster_ci(delta,joined.seed)
            seed_effect=delta.groupby(joined.seed).mean().dropna()
            sd=seed_effect.std()
            dz=float(seed_effect.mean()/sd) if len(seed_effect)>1 and sd>1e-12 else None
            rows.append({"algorithm_a":a,"algorithm_b":b,"metric":metric,"mean_difference":float(delta[valid].mean()) if valid.any() else None,
                         "ci95_low":lo,"ci95_high":hi,"paired_observations":int(valid.sum()),"seed_clusters":nseed,
                         "paired_cohen_dz_seed_level":dz,"identical_pairs":int((delta[valid].abs()<1e-12).sum()),
                         "effect_note":"A minus B; arrival uses jointly successful pairs. dz uses seed means; undefined at zero variance."})
    return pd.DataFrame(rows)

def write_tables(main,pilot,out,extra=None):
    out=Path(out)
    primary=pd.DataFrame([comparison(g,{"algorithm":a,"source":"main240"}) for a,g in main.groupby("algorithm")])
    primary.to_csv(out/"algorithm_comparison.csv",index=False,na_rep="N/A")
    paired_differences(main).to_csv(out/"paired_comparisons.csv",index=False,na_rep="N/A")
    scenario_rows=[]
    for scenario,label in (("head_on","Head-On"),("crossing","Crossing"),("narrow_passing","Narrow Passage")):
        for a,g in pilot[pilot.encounter_mode==scenario].groupby("algorithm"):
            scenario_rows.append(comparison(g,{"scenario_label":label,"algorithm":a,"source":"pilot18","frame_limit":2400,
                                               "interpretation":"n=4 workers, 2 seeds; not pooled with main240"}))
    dense=main[main.agent_count>=8]
    for a,g in dense.groupby("algorithm"):
        scenario_rows.append(comparison(g,{"scenario_label":"Dense Traffic","algorithm":a,"source":"main240_subset",
            "frame_limit":5400,"interpretation":"Crossing n=8/16, workers/mixed. Overlaps main data, not independent additional trials."}))
    scenarios=pd.DataFrame(scenario_rows);scenarios.to_csv(out/"scenario_comparison.csv",index=False,na_rep="N/A")
    scale=[]
    for (p,n,a),g in main.groupby(["population_mode","agent_count","algorithm"]):
        row=comparison(g,{"population":p,"agent_count":n,"algorithm":a,"source":"main240"})
        for key in ("neighbor_checks","candidate_checks","constraints"):
            values=g[key]/g.algo_steps
            lo,hi,_=cluster_ci(values,g.seed)
            row[key+"_per_step_mean"]=values.mean();row[key+"_per_step_ci95_low"]=lo;row[key+"_per_step_ci95_high"]=hi
        row["runtime_definition"]="mean of per-run frame means; historical frame median/P95 unavailable"
        scale.append(row)
    pd.DataFrame(scale).to_csv(out/"scalability_analysis.csv",index=False,na_rep="N/A")
    missing={"main240":["per-frame median/P95 runtime","stop time","LP inner evaluations","preferred velocity","reaction/deceleration onset"],
             "handling":"N/A; no reconstruction from two trajectory samples or mean/max",
             "denominators":"80 runs per algorithm; 10 seed clusters, n2 cohorts share physical scenes",
             "bootstrap":"3000 replicates, resample entire seeds across configurations, paired A-B; fixed RNG20261117",
             "n_policy":"retain measured 2,4,8,16; n12 omitted to reuse original study; no invented samples",
             "extra_runs":"supplemental telemetry kept separate from historical performance tables"}
    (out/"statistical_method.json").write_text(json.dumps(missing,ensure_ascii=False,indent=2))
    return primary,scenarios
