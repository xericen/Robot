"""Verify completed research, derived dashboard values, preservation and resume behavior."""
from __future__ import annotations
import argparse,hashlib,json,subprocess,sys,tempfile
from pathlib import Path
import numpy as np
import pandas as pd
from research_data import ROOT,assert_originals,read_json,digest,inputs

def verify(out):
    out=Path(out);bundle=read_json(out/"dashboard.json");audit=read_json(out/"audit.json")
    assert_originals(audit)
    assert audit["totals"]==dict(total=240,success=227,collision_free_success=152,safe_success=53)
    assert not audit["issues"] and not audit["mismatches"]
    counts={}
    for label,df,limit in (("main240",inputs()[0],5400),("pilot18",inputs()[1],2400)):
        keys=["map","encounter_mode","population_mode","agent_count","seed"]
        assert not df.duplicated(keys+["algorithm"]).any()
        assert df.groupby(keys).size().eq(3).all()
        configs={}
        for row in df.to_dict("records"):
            folder=ROOT/"results/newton/runs"/row["run_id"]
            assert (folder/"complete.json").is_file()
            r=read_json(folder/"result.json");cfg=read_json(folder/"configuration.json")
            last=read_json(folder/"trajectory.json")[-1]
            goal=int(np.linalg.norm(np.array(last["robot"])-r["goal"])<=.25 and np.linalg.norm(last["velocity"])<=.02)
            free=int(goal and r["collisions"]==0)
            safe=int(free and r["safety_violations"]==0 and r["static_safety_violations"]==0
                     and (r["min_dynamic_clearance_m"] is None or r["min_dynamic_clearance_m"]>=r["safety_distance_m"]-1e-6)
                     and r["min_static_clearance_m"]>=r["safety_distance_m"]-1e-6)
            assert (goal,free,safe)==tuple(row[k] for k in ("success","collision_free_success","safe_success"))
            assert cfg["frame_limit"]==limit and cfg["mapId"]==row["map"] and cfg["algorithm"]==row["algorithm"]
            assert cfg["seed"]==row["seed"] and cfg["agent_count"]==row["agent_count"]
            config_keys=["mapId","scenario","seed","agent_count","worker_count","other_robot_count","parameters","planner","planner_seed",
                         "traffic_mode","common_traffic","frame_limit","safety_distance_m","robot_speed_mps","encounter_mode","population_mode","encounter","scene_hash"]
            fingerprint=json.dumps({k:cfg[k] for k in config_keys},sort_keys=True)
            condition=tuple(row[k] for k in keys)
            if condition in configs:assert configs[condition]==fingerprint
            else:configs[condition]=fingerprint
        counts[label]={"rows":len(df),"matched_triplets":len(configs),"physical_final_states_verified":True}
    (out/"source_configuration_validation.json").write_text(json.dumps(counts,indent=2))
    for key,name in (("algorithms","algorithm_comparison.csv"),("scenarios","scenario_comparison.csv"),
                     ("scalability","scalability_analysis.csv"),("layouts","warehouse_layout_analysis.csv")):
        df=pd.read_csv(out/name)
        assert len(df)==len(bundle[key])
        for i,row in df.iterrows():
            for col in df.select_dtypes(include="number").columns:
                v=bundle[key][i][col]
                if pd.isna(row[col]):assert v is None
                else:assert np.isclose(row[col],v,atol=1e-9,rtol=1e-9),(key,col)
    assert len(bundle["figures"])>=9
    for f in bundle["figures"]:
        assert (out/"figs"/f).read_bytes().startswith(b"\x89PNG")
    assert read_json(out/"instrumentation_validation.json")["physical_results_unchanged"]
    assert read_json(out/"browser_validation.json")["passed"]
    raw=out/"supplemental_measurements.csv";before=digest(raw)
    runs=sorted(x.name for x in (out/"runs").iterdir())
    subprocess.run([sys.executable,str(ROOT/"research_supplement.py"),str(out)],check=True,capture_output=True,text=True)
    assert digest(raw)==before and sorted(x.name for x in (out/"runs").iterdir())==runs
    with tempfile.TemporaryDirectory() as tmp:
        missing=Path(tmp)/"missing"
        command=[sys.executable,str(ROOT/"research_pipeline.py"),"--primary",str(Path(tmp)/"absent"),
                 "--pilot",str(Path(tmp)/"absent"),"--output",str(missing)]
        result=subprocess.run(command,capture_output=True,text=True)
        assert result.returncode!=0 and read_json(missing/"missing.json")["status"]=="missing"
        assert not (missing/"algorithm_comparison.csv").exists()
        result=subprocess.run(command,capture_output=True,text=True)
        assert result.returncode!=0 and "Output exists" in result.stderr
    assert_originals(audit)
    result={"passed":True,"original_files_verified":len(audit["original_sha256"]),"raw_totals_recomputed":True,
            "dashboard_matches_all_numeric_csv_fields":True,"resume_no_new_runs":True,"missing_data_generates_no_values":True,
            "existing_output_rejected":True,"supplement_runs":len(runs),"figures":len(bundle["figures"])}
    (out/"research_validation.json").write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("output",type=Path);verify(p.parse_args().output)
