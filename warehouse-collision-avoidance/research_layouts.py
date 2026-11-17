"""Layout geometry and actual existing planners. Width metrics have explicit operational definitions."""
from __future__ import annotations
import itertools,json,time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.ndimage import label
from warehouse_maps import map_catalog,shelf_geometry
from simulator.physics import valid_position
from algorithms.planners import plan,edge_clear,path_length
from newton_safety import rectangle_distance

def polygon(shelf):
    w,h=shelf["size"];angle=np.deg2rad(shelf["rotation"])
    rotation=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
    return np.array([[-w/2,-h/2],[w/2,-h/2],[w/2,h/2],[-w/2,h/2]])@rotation.T+np.array(shelf["position"])

def project(p,a,b):
    d=b-a
    return a+d*np.clip(np.dot(p-a,d)/max(np.dot(d,d),1e-12),0,1)

def minimum_passable_gap(polygons,width,height,obstacles,component,xs,ys,required,resolution):
    # Sample each boundary and exact nearest point on another boundary.
    # Midpoint must fit the protected circle and belong to START's free-space component.
    boundaries=list(polygons)+[np.array([[0.,0.],[width,0.]]),np.array([[width,0.],[width,height]]),
                              np.array([[width,height],[0.,height]]),np.array([[0.,height],[0.,0.]])]
    best=float("inf")
    for ia,ib in itertools.combinations(range(len(boundaries)),2):
        if ia>=len(polygons) and ib>=len(polygons):continue
        a,b=boundaries[ia],boundaries[ib]
        edges_a=list(zip(a,np.roll(a,-1,axis=0))) if len(a)>2 else [(a[0],a[1])]
        edges_b=list(zip(b,np.roll(b,-1,axis=0))) if len(b)>2 else [(b[0],b[1])]
        for p,q in edges_a:
            samples=np.linspace(p,q,max(2,int(np.linalg.norm(q-p)/resolution)+1))
            for u,v in edges_b:
                candidates=[(point,project(point,u,v)) for point in samples]
                candidates += [(project(point,p,q),point) for point in (u,v)]
                for x,y in candidates:
                    gap=float(np.linalg.norm(x-y))
                    if gap<2*required-1e-8 or gap>=best:continue
                    mid=(x+y)/2
                    if not valid_position(mid,required,width,height,obstacles):continue
                    ix=int(np.argmin(abs(xs-mid[0])));iy=int(np.argmin(abs(ys-mid[1])))
                    if component[iy,ix]:best=gap
    return best if np.isfinite(best) else None

def analyze_layouts(out,resolution=.25):
    out=Path(out);rows=[];planner_runs=[];scenes=[]
    for config in map_catalog():
        width,height=config["warehouseSize"];radius=.42;safety=.35;required=radius+safety
        geometry=shelf_geometry(config);obstacles=[s["obstacle"] for s in geometry]
        polygons=[polygon(s) for s in geometry]
        xs=np.arange(resolution/2,width,resolution);ys=np.arange(resolution/2,height,resolution)
        free=np.array([[valid_position(np.array([x,y]),required,width,height,obstacles) for x in xs] for y in ys])
        components,_=label(free) # 4-connectivity gives a conservative reachable-area estimate.
        start=np.array(config["robotSpawnPosition"]);goal=np.array(config["goalPosition"])
        sid=components[np.argmin(abs(ys-start[1])),np.argmin(abs(xs-start[0]))]
        reachable=(components==sid)&free
        gap=minimum_passable_gap(polygons,width,height,obstacles,reachable,xs,ys,required,resolution)
        paths={}
        for planner in ("astar","dijkstra","rrt"):
            for seed in (42,43,44):
                began=time.perf_counter()
                row={"map":config["mapId"],"planner":planner,"seed":seed,"status":"failed",
                     "path_length_m":None,"expanded_nodes":None,"turning_count":None}
                try:
                    path,stats=plan(planner,start,goal,width,height,obstacles,required,seed)
                    assert all(edge_clear(a,b,required,width,height,obstacles) for a,b in zip(path,path[1:]))
                    row.update(status="success",path_length_m=path_length(path),
                               expanded_nodes=stats["expanded_nodes"],turning_count=stats["turning_count"],
                               planning_time_ms=stats["planning_time_ms"],iterations=stats.get("iterations"))
                    paths.setdefault(planner,path)
                except (RuntimeError,ValueError) as error:
                    row.update(error=str(error),planning_time_ms=(time.perf_counter()-began)*1000)
                planner_runs.append(row)
        a=[r for r in planner_runs if r["map"]==config["mapId"] and r["planner"]=="astar"][0]
        dij=[r for r in planner_runs if r["map"]==config["mapId"] and r["planner"]=="dijkstra"][0]
        if a["status"]!="success" or dij["status"]!="success":raise ValueError("Required planner disconnected")
        if not np.isclose(a["path_length_m"],dij["path_length_m"]):raise ValueError("A*/Dijkstra grid lengths disagree")
        occupancy=sum(s["size"][0]*s["size"][1] for s in geometry)/(width*height)
        direct=float(np.linalg.norm(goal-start))
        points=np.concatenate([np.linspace(u,v,max(2,int(np.linalg.norm(v-u)/.08)+1)) for u,v in zip(paths["astar"],paths["astar"][1:])])
        bottleneck=min(min([p[0],width-p[0],p[1],height-p[1]]+[rectangle_distance(p,r) for r in obstacles]) for p in points)
        rows.append({"map":config["mapId"],"map_name":config["mapName"],"obstacle_occupancy_ratio":occupancy,
            "geometric_free_ratio":1-occupancy,"protected_traversable_ratio_estimate":float(free.mean()),
            "start_reachable_ratio_estimate":float(reachable.mean()),"area_grid_resolution_m":resolution,
            "start":json.dumps(start.tolist()),"goal":json.dumps(goal.tolist()),"straight_distance_m":direct,
            "shortest_grid_path_length_m":a["path_length_m"],"path_grid_resolution_m":.5,
            "detour_ratio":a["path_length_m"]/direct,"minimum_passable_gap_m":gap,
            "gap_definition":"sampled rack/wall boundary gap fitting protected radius; midpoint START-connected, .25m sampling",
            "selected_path_clearance_diameter_m":2*bottleneck,"robot_radius_m":radius,"safety_margin_m":safety,
            "turning_count":a["turning_count"],"expanded_nodes":a["expanded_nodes"],
            "astar_planning_time_ms_mean":np.mean([r["planning_time_ms"] for r in planner_runs if r["map"]==config["mapId"] and r["planner"]=="astar"]),
            "navigation_matches_shelf_poses":True})
        scenes.append({"map":config["mapId"],"config":config,"polygons":[p.tolist() for p in polygons],
                       "paths":{k:[p.tolist() for p in v] for k,v in paths.items()}})
    pd.DataFrame(rows).to_csv(out/"warehouse_layout_analysis.csv",index=False,na_rep="N/A")
    pd.DataFrame(planner_runs).to_csv(out/"warehouse_planner_runs.csv",index=False,na_rep="N/A")
    (out/"warehouse_layout_scenes.json").write_text(json.dumps(scenes,ensure_ascii=False,indent=2))
    return pd.DataFrame(rows)
