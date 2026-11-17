"""Shelf map catalogue shared by physics, A*, spawns and render metadata."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import numpy as np

from algorithms.pathfinding import astar_path
from simulator.physics import valid_position


def map_catalog():
    return json.loads(Path(__file__).with_suffix(".json").read_text())


def get_map(map_id):
    try:
        return copy.deepcopy(next(m for m in map_catalog() if m["mapId"] == map_id))
    except StopIteration as error:
        raise ValueError("지원하지 않는 선반 맵입니다.") from error


def shelf_geometry(config):
    """Yield the exact local box pose plus its axis-aligned navigation footprint."""
    w, d = config["shelfSize"]
    result = []
    for centre, rotation in zip(config["shelfPositions"], config["shelfRotations"], strict=True):
        angle = np.deg2rad(rotation)
        width = abs(w*np.cos(angle)) + abs(d*np.sin(angle))
        depth = abs(w*np.sin(angle)) + abs(d*np.cos(angle))
        x, y = centre
        result.append({"position": [x, y], "rotation": rotation, "size": [w, d],
                       "obstacle": ([x-width/2, y-depth/2, width, depth] if rotation % 90 == 0 else
                                    {"position":[x,y], "size":[w,d], "rotation":rotation}),
                       "bounds":[x-width/2, y-depth/2, width, depth]})
    return result


def segment_clear(a, b, radius, width, height, obstacles):
    a, b = np.asarray(a), np.asarray(b)
    count = max(2, int(np.linalg.norm(b-a) / .08) + 2)
    return all(valid_position(a+(b-a)*t, radius, width, height, obstacles)
               for t in np.linspace(0, 1, count))


def validate_map(config, radius=.42, safety=.35):
    width, height = config["warehouseSize"]
    geometry = shelf_geometry(config)
    if len(geometry) != 6:
        raise ValueError("각 맵에는 선반 6개가 필요합니다.")
    rects = [g["obstacle"] for g in geometry]
    bounds = [g["bounds"] for g in geometry]
    for i, (x, y, w, d) in enumerate(bounds):
        if x <= 0 or y <= 0 or x+w >= width or y+d >= height:
            raise ValueError("선반이 외벽과 겹칩니다.")
        for xx, yy, ww, dd in bounds[i+1:]:
            if min(x+w, xx+ww)-max(x, xx) > 1e-6 and min(y+d, yy+dd)-max(y, yy) > 1e-6:
                raise ValueError("선반끼리 겹칩니다.")
    for key in ("startPosition", "goalPosition", "robotSpawnPosition"):
        if not valid_position(np.array(config[key]), radius+safety, width, height, rects):
            raise ValueError("출발/목표 위치에 로봇과 안전 여유를 확보할 수 없습니다.")
    path = astar_path(np.array(config["robotSpawnPosition"]), np.array(config["goalPosition"]),
                      width, height, rects, radius+safety)
    if not all(segment_clear(a, b, radius+safety, width, height, rects) for a, b in zip(path, path[1:])):
        raise ValueError("선반 맵의 경로가 장애물 여유 영역을 통과합니다.")
    return geometry, path


def apply_map(scenario, map_id, seed, safety=.35):
    config = get_map(map_id)
    if (scenario.width, scenario.height) != tuple(config["warehouseSize"]):
        if map_id == "map1":
            return scenario
        raise ValueError("다중 선반 맵은 easy/medium/hard/crowded 환경에서 선택하세요.")
    geometry, _ = validate_map(config, .42, safety)
    # Map 1 is the exact existing layout and seeded traffic baseline.
    if map_id != "map1":
        scenario.obstacles = [g["obstacle"] for g in geometry]
        scenario.start = np.array(config["robotSpawnPosition"], dtype=float)
        scenario.goal = np.array(config["goalPosition"], dtype=float)
        width, height = scenario.width, scenario.height
        occupied = [(scenario.start, .42)]
        protected = scenario.protected_radius
        rng = np.random.default_rng(seed)

        def valid_spawn(point, radius):
            return (valid_position(point, radius+.25, width, height, scenario.obstacles)
                    and all(np.linalg.norm(point-p) >= radius+r+.35 for p, r in occupied)
                    and all(np.linalg.norm(point-p) >= protected+radius for p in (scenario.start, scenario.goal)))

        # Reserve worker-0..3 first so extra robots/crowds cannot consume them.
        order = sorted(scenario.agents, key=lambda a: (a.kind != "worker", int(a.identifier.rsplit("-",1)[-1])))
        worker_index = 0
        candidates = np.array([(x,y) for x in np.arange(1.5,width-1,1.3)
                               for y in np.arange(1.5,height-1,1.3)], dtype=float)
        rng.shuffle(candidates)
        for agent in order:
            p = target = None
            if agent.kind == "worker" and worker_index < len(config["workerSpawnPositions"]):
                p = np.array(config["workerSpawnPositions"][worker_index], dtype=float)
                target = np.array(config["workerPatrolTargets"][worker_index], dtype=float)
                worker_index += 1
                if not valid_spawn(p, agent.radius) or not segment_clear(
                        p, target, agent.radius+.15, width, height, scenario.obstacles):
                    raise ValueError("설정된 작업자 배치/순찰 경로가 유효하지 않습니다.")
            else:
                best = []
                for candidate in candidates:
                    if valid_spawn(candidate, agent.radius):
                        clearance = min(float(np.linalg.norm(candidate-q)) for q, r in occupied)
                        best.append((clearance, candidate))
                if not best:
                    raise ValueError("유효한 에이전트 초기 배치를 확보하지 못했습니다.")
                p = max(best, key=lambda item:item[0])[1].copy()
                for offset in ((0,3),(3,0),(0,-3),(-3,0),(0,1.5),(1.5,0),(0,-1.5),(-1.5,0)):
                    candidate = p + offset
                    if segment_clear(p, candidate, agent.radius+.15, width, height, scenario.obstacles):
                        target = candidate
                        break
                if target is None:
                    raise ValueError("유효한 에이전트 순찰 경로를 확보하지 못했습니다.")
            occupied.append((p, agent.radius))
            agent.position, agent.origin, agent.goal = p.copy(), p.copy(), target.copy()
            direction = target-p
            agent.velocity = direction / max(float(np.linalg.norm(direction)), 1e-9) * agent.max_speed
    config["workerSpawnPositions"] = [a.position.tolist() for a in scenario.agents if a.kind == "worker"]
    config["workerPatrolTargets"] = [a.goal.tolist() for a in scenario.agents if a.kind == "worker"]
    scenario.map_config = config
    scenario.description = config["description"]
    return scenario
