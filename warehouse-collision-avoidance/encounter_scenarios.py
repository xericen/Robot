"""Seeded, algorithm-independent encounters, generated against actual navigation geometry."""
from __future__ import annotations
import hashlib
import json
import numpy as np
from algorithms.planners import plan
from simulator.agents import Agent
from simulator.physics import valid_position
from warehouse_maps import segment_clear

ENCOUNTERS = ("baseline", "head_on", "crossing", "narrow_passing")
POPULATIONS = ("legacy", "workers", "mixed")


def point_on_path(path, progress):
    lengths = [float(np.linalg.norm(b-a)) for a,b in zip(path,path[1:])]
    remaining = progress * sum(lengths)
    travelled = 0.
    for a,b,length in zip(path,path[1:],lengths):
        if remaining <= length or b is path[-1]:
            return a+(b-a)*min(1,remaining/max(length,1e-9)), (b-a)/max(length,1e-9), travelled+remaining
        remaining -= length
        travelled += length
    raise ValueError("경로에 유효한 선분이 없습니다.")


def configure(scenario, encounter, population, count, seed, safety, speed, planner, planner_seed):
    if encounter not in ENCOUNTERS or population not in POPULATIONS:
        raise ValueError("지원하지 않는 만남 조건/인구 구성입니다.")
    if encounter == "baseline" and population == "legacy":
        return {"mode":"baseline","population":"legacy","barriers":[],"actors":[]}
    if scenario.layout_version < 2:
        raise ValueError("통제 실험은 easy/medium/hard/crowded의 38×26m 창고를 사용하세요.")
    if encounter == "baseline":
        encounter = "crossing"
    count = len(scenario.agents) if population == "legacy" else count
    path, _ = plan(planner, scenario.start, scenario.goal, scenario.width, scenario.height,
                   scenario.obstacles, .42+safety, planner_seed)
    barriers = []
    if encounter == "narrow_passing":
        if not scenario.map_config or scenario.map_config["mapId"] != "map1":
            raise ValueError("좁은 교행 통제 실험은 Map1 Standard 전용입니다.")
        # Two explicitly recorded cargo barriers form a physical 2.8m passage.
        # Both navigation and Newton receive these exact rectangles.
        for progress in np.linspace(.35,.65,16):
            centre, tangent, _ = point_on_path(path, progress)
            if max(abs(tangent)) < .999:
                continue
            normal = np.array([-tangent[1],tangent[0]])
            width,depth = ((4.,.6) if abs(tangent[0])>.9 else (.6,4.))
            candidate=[]
            for sign in (-1,1):
                c=centre+normal*sign*1.7
                candidate.append([float(c[0]-width/2),float(c[1]-depth/2),width,depth])
            corners=[np.array([x+dx*w,y+dy*h]) for x,y,w,h in candidate for dx in (0,1) for dy in (0,1)]
            if all(valid_position(p,.02,scenario.width,scenario.height,scenario.obstacles) for p in corners):
                barriers=candidate
                break
        if not barriers:
            raise ValueError("이 맵에는 2.8m 교행 시험 통로를 안전하게 배치할 구간이 없습니다.")
        scenario.obstacles = list(scenario.obstacles)+barriers
        path,_=plan(planner,scenario.start,scenario.goal,scenario.width,scenario.height,
                    scenario.obstacles,.42+safety,planner_seed)
    actors=[]
    occupied=[(scenario.start,.42),(scenario.goal,.42)]
    kinds = [a.kind for a in scenario.agents]
    totals={"worker":0,"robot":0}
    for i in range(count):
        rng=np.random.default_rng(np.random.SeedSequence([seed,i,20261117]))
        kind=(kinds[i] if population=="legacy" else ("robot" if population=="mixed" and i%4==3 else "worker"))
        radius=.42 if kind=="robot" else .30
        velocity=float(rng.uniform(.72,.98) if kind=="worker" else rng.uniform(.85,1.1))
        found=None
        for attempt in range(500):
            progress=float(rng.uniform(.27,.66) if i==0 else rng.uniform(.20,.80))
            if encounter=="narrow_passing" and i==0:
                centre_barrier=np.array([barriers[0][0]+barriers[0][2]/2,barriers[0][1]+barriers[0][3]/2])
                centre_barrier2=np.array([barriers[1][0]+barriers[1][2]/2,barriers[1][1]+barriers[1][3]/2])
                meet=(centre_barrier+centre_barrier2)/2
                # Find closest navigation segment, without changing the planner.
                choices=[(np.linalg.norm(point_on_path(path,p)[0]-meet),p) for p in np.linspace(.1,.9,81)]
                progress=min(choices)[1]
            meet,tangent,distance=point_on_path(path,progress)
            normal=np.array([-tangent[1],tangent[0]])
            axis = normal if encounter=="crossing" or i>0 else tangent
            side = 1 if i==0 or rng.random()<.5 else -1
            offset=float(rng.uniform(1.7,2.5))
            if encounter=="narrow_passing" and i==0:
                offset=3.5
            p=meet+axis*side*offset
            goal=meet-axis*side*offset
            if not segment_clear(p,goal,radius+.15,scenario.width,scenario.height,scenario.obstacles):
                continue
            if any(np.linalg.norm(p-q) < radius+r+safety+.1 for q,r in occupied):
                continue
            # Release relative to nominal robot ETA. Jitter changes the actual encounter by seed.
            release=max(0.,distance/speed-offset/velocity+float(rng.uniform(-1.1,1.1)))
            found=(p,goal,release,progress)
            break
        if found is None:
            raise ValueError(f"안전한 통제 에이전트 배치를 찾지 못했습니다: {i}")
        p,goal,release,progress=found
        identifier=f"{kind}-{totals[kind]}";totals[kind]+=1
        agent=Agent(identifier,p,np.zeros(2),goal,radius=radius,max_speed=velocity,kind=kind,cooperative=False)
        agent.release_time_s=release
        actors.append(agent)
        occupied.append((p,radius))
    scenario.agents=actors
    return {"mode":encounter,"population":population,"barriers":barriers,
            "passage_width_m":2.8 if barriers else None,
            "rng":"SeedSequence([seed, actor_index, 20261117]); prefix-stable within a population mode",
            "actors":[{"id":a.identifier,"kind":a.kind,"position":a.position.tolist(),"goal":a.goal.tolist(),
                       "radius":a.radius,"max_speed":a.max_speed,"release_time_s":a.release_time_s}
                      for a in actors]}


def scene_fingerprint(document):
    return hashlib.sha256(json.dumps(document,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
