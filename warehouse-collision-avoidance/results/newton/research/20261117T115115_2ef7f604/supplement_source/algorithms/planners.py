"""Global planners share one footprint and swept-segment predicate; local avoidance is separate."""
from __future__ import annotations
import time
import numpy as np
from algorithms.pathfinding import astar_path
from simulator.physics import valid_position

PLANNERS = ("astar", "dijkstra", "rrt")
RRT_SETTINGS = {"max_iterations":3000, "time_limit_s":3.0, "step_m":1.5, "goal_bias":.15}

def edge_clear(a, b, radius, width, height, obstacles):
    a, b = np.asarray(a), np.asarray(b)
    n = max(2, int(np.linalg.norm(b-a)/.08)+2)
    return all(valid_position(a+(b-a)*t, radius, width, height, obstacles) for t in np.linspace(0,1,n))

def path_length(path):
    return sum(float(np.linalg.norm(b-a)) for a,b in zip(path,path[1:]))

def turning_count(path, threshold_degrees=15):
    count = 0
    for a,b,c in zip(path,path[1:],path[2:]):
        u,v=np.asarray(b)-a,np.asarray(c)-b
        if np.linalg.norm(u)*np.linalg.norm(v) > 1e-10:
            angle=np.degrees(np.arccos(np.clip(np.dot(u,v)/(np.linalg.norm(u)*np.linalg.norm(v)),-1,1)))
            count += angle >= threshold_degrees
    return int(count)

def plan(name, start, goal, width, height, obstacles, radius, seed=42):
    if name not in PLANNERS:
        raise ValueError("지원하지 않는 전역 경로 탐색기입니다.")
    start,goal=np.asarray(start,dtype=float),np.asarray(goal,dtype=float)
    if not all(valid_position(p,radius,width,height,obstacles) for p in (start,goal)):
        raise ValueError("전역 경로의 출발/목표 위치가 유효하지 않습니다.")
    began=time.perf_counter_ns();stats={"expanded_nodes":None,"iterations":None}
    if name in ("astar","dijkstra"):
        path=astar_path(start,goal,width,height,obstacles,radius,stats=stats,heuristic=name=="astar")
    else:
        rng=np.random.default_rng(seed);nodes=[start];parents=[-1];path=None
        deadline=time.monotonic()+RRT_SETTINGS["time_limit_s"]
        for iteration in range(RRT_SETTINGS["max_iterations"]):
            if time.monotonic() >= deadline:
                break
            sample=goal if rng.random()<RRT_SETTINGS["goal_bias"] else rng.uniform([radius,radius],[width-radius,height-radius])
            distances=np.linalg.norm(np.asarray(nodes)-sample,axis=1);parent=int(np.argmin(distances))
            delta=sample-nodes[parent];length=float(np.linalg.norm(delta))
            candidate=nodes[parent]+delta/max(length,1e-10)*min(length,RRT_SETTINGS["step_m"])
            if not edge_clear(nodes[parent],candidate,radius,width,height,obstacles):
                continue
            nodes.append(candidate);parents.append(parent)
            if np.linalg.norm(candidate-goal)<=RRT_SETTINGS["step_m"] and edge_clear(candidate,goal,radius,width,height,obstacles):
                path=[goal];index=len(nodes)-1
                while index>=0:
                    path.append(nodes[index]);index=parents[index]
                path.reverse();break
        stats["iterations"]=iteration+1
        stats["tree_nodes"]=len(nodes)
        if path is None:
            raise RuntimeError("RRT가 반복/시간 한도 내 경로를 찾지 못했습니다.")
        # Deterministic shortcutting retains the same swept-circle clearance.
        short=[path[0]];i=0
        while i<len(path)-1:
            j=len(path)-1
            while j>i+1 and not edge_clear(path[i],path[j],radius,width,height,obstacles):j-=1
            short.append(path[j]);i=j
        path=short
    if not all(edge_clear(a,b,radius,width,height,obstacles) for a,b in zip(path,path[1:])):
        raise RuntimeError("계산된 경로의 연속 충돌 검사가 실패했습니다.")
    stats.update(planner=name,planning_time_ms=(time.perf_counter_ns()-began)/1e6,
                 planned_path_length_m=path_length(path),turning_count=turning_count(path),
                 replanning_count=0,planner_seed=seed)
    return path,stats
