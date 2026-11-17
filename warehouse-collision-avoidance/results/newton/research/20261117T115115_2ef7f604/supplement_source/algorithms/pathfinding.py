from __future__ import annotations

import heapq
import math

import numpy as np

from simulator.physics import valid_position


def astar_path(start: np.ndarray, goal: np.ndarray, width: float, height: float,
               obstacles: list[tuple[float, float, float, float]], radius: float,
               resolution: float = 0.5, *, stats: dict | None = None,
               heuristic: bool = True) -> list[np.ndarray]:
    cols, rows = int(width / resolution) + 1, int(height / resolution) + 1

    def cell(point: np.ndarray) -> tuple[int, int]:
        return int(round(point[0] / resolution)), int(round(point[1] / resolution))

    def point(node: tuple[int, int]) -> np.ndarray:
        return np.array([node[0] * resolution, node[1] * resolution], dtype=float)

    start_cell, goal_cell = cell(start), cell(goal)
    frontier: list[tuple[float, tuple[int, int]]] = [(0.0, start_cell)]
    came_from: dict[tuple[int, int], tuple[int, int] | None] = {start_cell: None}
    cost = {start_cell: 0.0}
    directions = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
    closed = set()
    while frontier:
        _, current = heapq.heappop(frontier)
        if current in closed:
            continue
        closed.add(current)
        if current == goal_cell:
            break
        for dx, dy in directions:
            neighbor = current[0] + dx, current[1] + dy
            if not (0 <= neighbor[0] < cols and 0 <= neighbor[1] < rows):
                continue
            # Do not cut across an inflated shelf corner on a diagonal edge.
            if dx and dy and (not valid_position(point((current[0]+dx, current[1])),
                                                radius, width, height, obstacles)
                              or not valid_position(point((current[0], current[1]+dy)),
                                                    radius, width, height, obstacles)):
                continue
            candidate = point(neighbor)
            if not valid_position(candidate, radius, width, height, obstacles):
                continue
            new_cost = cost[current] + math.hypot(dx, dy)
            if neighbor not in cost or new_cost < cost[neighbor]:
                cost[neighbor] = new_cost
                priority = new_cost + (math.dist(neighbor, goal_cell) if heuristic else 0.0)
                heapq.heappush(frontier, (priority, neighbor))
                came_from[neighbor] = current
    if stats is not None:
        stats["expanded_nodes"] = len(closed)
    if goal_cell not in came_from:
        raise RuntimeError("A*가 출발점과 목적지를 연결하는 경로를 찾지 못했습니다.")
    nodes: list[tuple[int, int]] = []
    current: tuple[int, int] | None = goal_cell
    while current is not None:
        nodes.append(current)
        current = came_from[current]
    nodes.reverse()
    raw = [point(node) for node in nodes]
    raw[0], raw[-1] = np.asarray(start, dtype=float), np.asarray(goal, dtype=float)
    return simplify_path(raw)


def simplify_path(path: list[np.ndarray]) -> list[np.ndarray]:
    if len(path) < 3:
        return path
    simplified = [path[0]]
    previous_direction = None
    for index in range(1, len(path)):
        direction = np.sign(path[index] - path[index - 1])
        signature = tuple(direction.tolist())
        if previous_direction is not None and signature != previous_direction:
            simplified.append(path[index - 1])
        previous_direction = signature
    simplified.append(path[-1])
    return simplified
