"""Reproducible Newton CPU study: fixed ORCA controller, varied global planner."""
from __future__ import annotations
import argparse, contextlib, io, json, os, platform, time
from pathlib import Path
import numpy as np
from algorithms.planners import RRT_SETTINGS
from warehouse_maps import map_catalog

ROOT=Path(__file__).parent
def atomic(path,data):
    temp=path.with_suffix(".tmp");temp.write_text(json.dumps(data,ensure_ascii=False,indent=2));os.replace(temp,path)

def aggregate(rows):
    result=[]
    for mode in ("static","dynamic"):
        for m in map_catalog():
            for planner in ("astar","dijkstra","rrt"):
                group=[r for r in rows if r["traffic_mode"]==mode and r["mapId"]==m["mapId"] and r["planner"]==planner]
                if not group:continue
                item={"traffic_mode":mode,"mapId":m["mapId"],"mapName":m["mapName"],"planner":planner,
                      "runs":len(group),"success_rate":100*sum(r["status"]=="success" for r in group)/len(group)}
                for key in ("planned_path_length_m","planning_time_ms","expanded_nodes","travel_time_s",
                            "collisions","replanning_count","turning_count","actual_distance_m"):
                    values=[r[key] for r in group if r.get(key) is not None]
                    item[key]=float(np.mean(values)) if values else None
                    item[key+"_variance"]=float(np.var(values)) if len(values)>1 else None
                result.append(item)
    return result

def main():
    from newton_warehouse import run
    import newton, warp as wp
    parser=argparse.ArgumentParser();parser.add_argument("--rrt-repeats",type=int,default=3)
    args=parser.parse_args()
    if not 2<=args.rrt_repeats<=10:raise ValueError("RRT repeats must be 2..10")
    folder=ROOT/"results"/"planning";folder.mkdir(parents=True,exist_ok=True)
    (folder/"pid").write_text(str(os.getpid()))
    rows=[];total=6*2*(2+args.rrt_repeats);began=time.time()
    document={"schema":1,"generated_at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
      "environment":{"os":platform.platform(),"python":platform.python_version(),"device":"cpu",
                     "newton":newton.__version__,"warp":wp.__version__,"warehouse_m":[38,26],"shelf_size_m":[3,7,3.2],
                     "robot_radius_m":.42,"safety_m":.35,"speed_mps":1.2,"frames":3600,
                     "avoidance":"orca","population_seed":42,"workers":4,"rrt_settings":RRT_SETTINGS,
                     "rrt_seeds":list(range(42,42+args.rrt_repeats)),
                     "deterministic_repeats":1,
                     "traffic":"same four spawn/patrol targets across all maps; static holds zero target velocity",
                     "planning_resolution_m":.5,"edge_sampling_m":.08,
                     "turn_definition":"planned path heading changes >=15 degrees; actual heading count N/A",
                     "replanning":"no online replanning; initial calculation excluded"},
      "maps":map_catalog(),"rows":rows,"summary":[],"completed":0,"total":total,"phase":"running"}
    atomic(folder/"progress.json",document)
    try:
        for mode in ("static","dynamic"):
            for m in map_catalog():
                for planner in ("astar","dijkstra","rrt"):
                    for seed in (range(42,42+args.rrt_repeats) if planner=="rrt" else [42]):
                        row={"traffic_mode":mode,"mapId":m["mapId"],"mapName":m["mapName"],
                             "planner":planner,"planner_seed":seed,"status":"planning_failed",
                             "planned_path_length_m":None,"planning_time_ms":None,"expanded_nodes":None,
                             "travel_time_s":None,"collisions":None,"replanning_count":None,
                             "turning_count":None,"actual_distance_m":None}
                        try:
                            with contextlib.redirect_stdout(io.StringIO()):
                                r=run(scenario_name="medium",agent_count=4,map_id=m["mapId"],planner=planner,
                                      planner_seed=seed,traffic_mode=mode,common_traffic=True,
                                      frames=3600,trace_stride=10)
                            for key in ("status","planned_path_length_m","planning_time_ms","expanded_nodes",
                                        "collisions","replanning_count","turning_count","contact_labels",
                                        "iterations","safety_violations","goal_distance_m"):
                                row[key]=r.get(key)
                            row.update(travel_time_s=r["sim_time_s"] if r["status"]=="success" else None,
                                       observed_time_s=r["sim_time_s"],actual_distance_m=r["path_length_m"],
                                       path=r["astar_path"],trajectory=[f["robot"] for f in r["frames"]],
                                       start=r["start"],goal=r["goal"],shelf_poses=r["shelf_poses"],
                                       final_velocity=r["final_velocity"],
                                       initial_workers=r["frames"][0]["workers"],
                                       worker_max_displacement_m=max(float(np.linalg.norm(np.asarray(f["workers"])-r["frames"][0]["workers"],axis=1).max()) for f in r["frames"]))
                        except (ValueError,RuntimeError) as error:
                            row["error"]=str(error)
                        rows.append(row);document.update(completed=len(rows),summary=aggregate(rows),elapsed_s=time.time()-began)
                        atomic(folder/"progress.json",document)
                        print(f'{len(rows)}/{total} {mode} {m["mapId"]} {planner} {seed} {row["status"]}',flush=True)
        document["phase"]="complete";atomic(folder/"latest.json",document);atomic(folder/"progress.json",document)
    except Exception as error:
        document.update(phase="error",error=str(error));atomic(folder/"progress.json",document);raise

if __name__=="__main__":main()
