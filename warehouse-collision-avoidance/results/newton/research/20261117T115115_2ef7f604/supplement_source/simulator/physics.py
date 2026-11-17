from __future__ import annotations

import numpy as np


def circle_rectangle_collision(position: np.ndarray, radius: float, rect: tuple[float, float, float, float]) -> bool:
    if isinstance(rect, dict):
        angle = np.deg2rad(rect['rotation'])
        delta = np.asarray(position) - np.asarray(rect['position'])
        position = np.array([np.cos(angle)*delta[0]+np.sin(angle)*delta[1],
                             -np.sin(angle)*delta[0]+np.cos(angle)*delta[1]])
        w, h = rect['size']
        rect = (-w/2, -h/2, w, h)
    x, y, width, height = rect
    closest = np.array([
        min(max(position[0], x), x + width),
        min(max(position[1], y), y + height),
    ])
    return float(np.linalg.norm(position - closest)) < radius - 1e-9


def valid_position(position: np.ndarray, radius: float, width: float, height: float,
                   obstacles: list[tuple[float, float, float, float]]) -> bool:
    if position[0] < radius or position[0] > width - radius:
        return False
    if position[1] < radius or position[1] > height - radius:
        return False
    return not any(circle_rectangle_collision(position, radius, obstacle) for obstacle in obstacles)


def swept_minimum_separation(a0: np.ndarray, a1: np.ndarray, b0: np.ndarray, b1: np.ndarray) -> float:
    relative_start = a0 - b0
    relative_step = (a1 - a0) - (b1 - b0)
    denominator = float(np.dot(relative_step, relative_step))
    t = 0.0 if denominator < 1e-12 else float(np.clip(-np.dot(relative_start, relative_step) / denominator, 0.0, 1.0))
    return float(np.linalg.norm(relative_start + t * relative_step))
