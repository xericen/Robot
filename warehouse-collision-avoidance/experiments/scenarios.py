from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from simulator.agents import Agent
from simulator.physics import valid_position


@dataclass
class Scenario:
    name: str
    width: float
    height: float
    start: np.ndarray
    goal: np.ndarray
    obstacles: list[tuple[float, float, float, float]]
    agents: list[Agent]
    description: str
    layout_version: int = 1
    protected_radius: float = 0.0
    map_config: dict | None = None


def _free_position(rng: np.random.Generator, width: float, height: float,
                   obstacles: list[tuple[float, float, float, float]], radius: float = 0.3) -> np.ndarray:
    for _ in range(2000):
        point = np.array([rng.uniform(1.5, width - 1.5), rng.uniform(1.0, height - 1.0)])
        blocked = any(x - radius <= point[0] <= x + w + radius and y - radius <= point[1] <= y + h + radius
                      for x, y, w, h in obstacles)
        if not blocked and not (point[0] < 3 and abs(point[1] - height / 2) < 1.0):
            return point
    raise RuntimeError("에이전트 초기 위치를 생성하지 못했습니다.")


def _legacy_scenario(name: str, agent_count: int, seed: int, cooperative: bool = False) -> Scenario:
    if agent_count < 0 or agent_count > 120:
        raise ValueError("에이전트 수는 0~120 범위여야 합니다.")
    rng = np.random.default_rng(seed)
    width, height = 24.0, 16.0
    shelves: list[tuple[float, float, float, float]] = []
    description = "장애물이 거의 없는 기본 환경"
    if name in {"warehouse", "crossing", "multi_robot", "crowded"}:
        shelves = [
            (5.0, 1.5, 2.5, 5.0), (5.0, 9.5, 2.5, 5.0),
            (10.5, 1.5, 2.5, 5.0), (10.5, 9.5, 2.5, 5.0),
            (16.0, 1.5, 2.5, 5.0), (16.0, 9.5, 2.5, 5.0),
        ]
        description = "선반과 좁은 통로가 있는 물류창고"
    start, goal = np.array([1.2, 8.0]), np.array([22.8, 8.0])
    agents: list[Agent] = []
    for index in range(agent_count):
        kind = "worker"
        radius, max_speed = 0.28, float(rng.uniform(0.55, 0.9))
        position = _free_position(rng, width, height, shelves, radius)
        if name == "crossing":
            lane_x = 8.5 + (index % 3) * 3.0
            position = np.array([lane_x, 2.0 if index % 2 == 0 else 14.0])
            goal_position = np.array([lane_x, 14.0 if index % 2 == 0 else 2.0])
            description = "작업자가 통로를 가로지르는 환경"
        elif name == "multi_robot":
            kind, radius, max_speed = "robot", 0.35, 1.0
            y = 2.0 + (index % 6) * 2.25
            position = np.array([3.0 if index % 2 == 0 else 21.0, y])
            goal_position = np.array([21.0 if index % 2 == 0 else 3.0, y])
            description = "다수의 로봇이 교차 이동하는 환경"
        else:
            goal_position = _free_position(rng, width, height, shelves, radius)
            if name == "crowded":
                kind = "robot" if index % 4 == 0 else "worker"
                description = "사람과 로봇이 혼재된 혼잡 환경"
        direction = goal_position - position
        direction /= max(float(np.linalg.norm(direction)), 1e-9)
        agents.append(Agent(
            identifier=f"{kind}-{index}", position=position, velocity=direction * max_speed,
            goal=goal_position, radius=radius, max_speed=max_speed, kind=kind,
            cooperative=cooperative or kind == "robot",
        ))
    return Scenario(name, width, height, start, goal, shelves, agents, description)


PRESETS = {"easy": (2, 0), "medium": (4, 0), "hard": (7, 2)}


def _warehouse_scenario(name: str, agent_count: int, seed: int, cooperative: bool) -> Scenario:
    rng = np.random.default_rng(seed)
    width, height = 38.0, 26.0
    start, goal = np.array([2.5, 13.0]), np.array([35.5, 13.0])
    shelves = [(x, y, 3.0, 7.0) for x in (8.0, 16.0, 24.0) for y in (3.0, 16.0)]
    protected = 3.0
    if name in PRESETS:
        worker_count, other_robots = PRESETS[name]
    else:
        other_robots = min(4, agent_count // 4)
        worker_count = agent_count - other_robots
    agents = []

    def append(kind, position, destination, speed):
        radius = .30 if kind == "worker" else .42
        position, destination = np.array(position, dtype=float), np.array(destination, dtype=float)
        if not valid_position(position, radius + .25, width, height, shelves):
            raise RuntimeError("초기 강체와 선반의 간격이 부족합니다.")
        if any(np.linalg.norm(position - p) < protected + radius for p in (start, goal)):
            raise RuntimeError("출발/목표 보호 구역에 강체를 배치할 수 없습니다.")
        if any(np.linalg.norm(position - a.position) < radius + a.radius + .35 for a in agents):
            raise RuntimeError("초기 강체 간격이 부족합니다.")
        velocity = destination - position
        velocity = velocity / max(float(np.linalg.norm(velocity)), 1e-9) * speed
        agents.append(Agent(f"{kind}-{sum(a.kind == kind for a in agents)}",
                            position, velocity, destination, radius=radius, max_speed=speed,
                            kind=kind, cooperative=cooperative or kind == "robot"))

    # Other robots stay inside the six-metre central corridor.
    for index in range(other_robots):
        x, y = ((32.0, 14.4), (26.0, 11.4), (19.0, 14.4), (10.0, 11.4))[index]
        append("robot", (x, y), (5.0 if index % 2 == 0 else 33.0, y), 1.0)

    # Only this minority crosses the primary route. First crossing is timed to
    # meet the approaching AMR, so avoidance differences are observable.
    crossings = min(3, max(1, worker_count // 3)) if worker_count else 0
    for index in range(crossings):
        lane_x = (13.5, 21.5, 29.5)[index % 3]
        side = -1 if index % 2 == 0 else 1
        distance = min(11.0, max(5.0, (lane_x - start[0]) / 1.2 * .72))
        # Extra crossing workers use a separate lane/depth at high crowd counts.
        lane_x += (index // 3) * .9
        if index >= 3:
            break
        append("worker", (lane_x, 13 + side * distance),
               (lane_x, 13 - side * distance), .72)

    # Full-height free aisles; stratified farthest-point allocation distributes
    # workers across both halves rather than accumulating them at START.
    candidates = np.array([
        (x, y) for x in np.arange(2.0, width - 1.5, 1.3)
        for y in np.r_[np.arange(1.5, 9.1, 1.3), np.arange(17.0, height - 1.0, 1.3)]
        if not any(sx - .55 <= x <= sx + sw + .55 for sx, sy, sw, sh in shelves)
        and valid_position(np.array([x, y]), .55, width, height, shelves)
        and all(np.linalg.norm(np.array([x, y]) - p) >= protected + .30 for p in (start, goal))
    ], dtype=float)
    rng.shuffle(candidates)
    while sum(a.kind == "worker" for a in agents) < worker_count:
        occupied = np.array([start] + [a.position for a in agents])
        radii = np.array([.42] + [a.radius for a in agents])
        clearance = np.min(np.linalg.norm(candidates[:, None, :] - occupied[None, :, :], axis=2)
                           - radii[None, :], axis=1)
        valid = clearance >= .30 + .35
        if not valid.any():
            raise RuntimeError("안전한 초기 작업자 배치 공간이 부족합니다.")
        index = int(np.argmax(np.where(valid, clearance, -np.inf)))
        position = candidates[index]
        low, high = (1.5, 9.0) if position[1] < 13 else (17.0, 24.5)
        target_y = float(np.clip(position[1] + (3.5 if position[1] < (low+high)/2 else -3.5), low, high))
        append("worker", position, (position[0], target_y), float(rng.uniform(.6, .85)))
        candidates = np.delete(candidates, index, axis=0)
    return Scenario(name, width, height, start, goal, shelves, agents,
                    f"{name} · 중앙 통로 6m · 보호 반경 3m", 2, protected)


def create_scenario(name: str, agent_count: int, seed: int, cooperative: bool = False,
                    map_id: str | None = None, safety_distance: float = .35) -> Scenario:
    if name not in SCENARIOS:
        raise ValueError("지원하지 않는 시나리오입니다.")
    if not 0 <= agent_count <= 120:
        raise ValueError("에이전트 수는 0~120 범위여야 합니다.")
    scenario = (_warehouse_scenario(name, agent_count, seed, cooperative) if name in (*PRESETS, "crowded")
                else _legacy_scenario(name, agent_count, seed, cooperative))
    if map_id is not None:
        from warehouse_maps import apply_map
        scenario = apply_map(scenario, map_id, seed, safety_distance)
    return scenario


SCENARIOS = ("easy", "medium", "hard", "crowded", "basic", "warehouse", "crossing", "multi_robot")
