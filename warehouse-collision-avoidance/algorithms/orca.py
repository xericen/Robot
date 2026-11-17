from __future__ import annotations

import math

import numpy as np

from .base import AlgorithmDiagnostics, AvoidanceAlgorithm
from simulator.agents import Agent, ControlledRobot


def det(a: np.ndarray, b: np.ndarray) -> float:
    return float(a[0] * b[1] - a[1] * b[0])


class ORCAAvoidance(AvoidanceAlgorithm):
    """Two-dimensional ORCA half-plane construction with sequential linear programming."""

    name = "ORCA"

    def __init__(self, horizon: float = 3.0) -> None:
        self.horizon = horizon
        self.neighbor_dist = 0.0
        self.max_neighbors = 0

    def choose_velocity(self, robot: ControlledRobot, neighbors: list[Agent], preferred: np.ndarray,
                        safety_distance: float, dt: float) -> tuple[np.ndarray, AlgorithmDiagnostics]:
        diagnostics = AlgorithmDiagnostics()
        lines: list[tuple[np.ndarray, np.ndarray]] = []
        # Unlimited defaults preserve the original iteration order and behavior.
        if self.neighbor_dist > 0:
            neighbors = [a for a in neighbors if np.linalg.norm(a.position - robot.position) <= self.neighbor_dist]
        if self.max_neighbors > 0:
            neighbors = sorted(neighbors, key=lambda a: float(np.linalg.norm(a.position - robot.position)))[:self.max_neighbors]
        for other in neighbors:
            diagnostics.neighbor_checks += 1
            relative_position = other.position - robot.position
            relative_velocity = robot.velocity - other.velocity
            radius = robot.radius + other.radius + safety_distance
            distance_sq = float(np.dot(relative_position, relative_position))
            radius_sq = radius * radius
            if distance_sq > radius_sq:
                w = relative_velocity - relative_position / self.horizon
                w_length_sq = float(np.dot(w, w))
                dot_product = float(np.dot(w, relative_position))
                if dot_product < 0 and dot_product * dot_product > radius_sq * w_length_sq:
                    w_length = math.sqrt(max(w_length_sq, 1e-12))
                    unit_w = w / w_length
                    direction = np.array([unit_w[1], -unit_w[0]])
                    correction = (radius / self.horizon - w_length) * unit_w
                else:
                    leg = math.sqrt(max(0.0, distance_sq - radius_sq))
                    if det(relative_position, w) > 0:
                        direction = np.array([
                            relative_position[0] * leg - relative_position[1] * radius,
                            relative_position[0] * radius + relative_position[1] * leg,
                        ]) / distance_sq
                    else:
                        direction = -np.array([
                            relative_position[0] * leg + relative_position[1] * radius,
                            -relative_position[0] * radius + relative_position[1] * leg,
                        ]) / distance_sq
                    correction = np.dot(relative_velocity, direction) * direction - relative_velocity
            else:
                inverse_dt = 1.0 / max(dt, 1e-6)
                w = relative_velocity - relative_position * inverse_dt
                w_length = float(np.linalg.norm(w))
                unit_w = w / w_length if w_length > 1e-9 else np.array([-1.0, 0.0])
                direction = np.array([unit_w[1], -unit_w[0]])
                correction = (radius * inverse_dt - w_length) * unit_w
            responsibility = 0.5 if other.cooperative else 1.0
            point = robot.velocity + responsibility * correction
            lines.append((point, direction))
            diagnostics.constraints += 1

        result = self.limit_speed(preferred.copy(), robot.max_speed)
        for index, (point, direction) in enumerate(lines):
            diagnostics.candidate_checks += 1
            if det(direction, point - result) <= 1e-9:
                continue
            projected = self._project_line(lines, index, preferred, robot.max_speed)
            if projected is None:
                return np.zeros(2, dtype=float), diagnostics
            result = projected
        return result, diagnostics

    @staticmethod
    def _project_line(lines: list[tuple[np.ndarray, np.ndarray]], line_index: int,
                      preferred: np.ndarray, max_speed: float) -> np.ndarray | None:
        point, direction = lines[line_index]
        dot_product = float(np.dot(point, direction))
        discriminant = dot_product ** 2 + max_speed ** 2 - float(np.dot(point, point))
        if discriminant < 0:
            return None
        root = math.sqrt(discriminant)
        left, right = -dot_product - root, -dot_product + root
        for prior_point, prior_direction in lines[:line_index]:
            denominator = det(direction, prior_direction)
            numerator = det(prior_direction, point - prior_point)
            if abs(denominator) < 1e-9:
                if numerator < 0:
                    return None
                continue
            value = numerator / denominator
            if denominator >= 0:
                right = min(right, value)
            else:
                left = max(left, value)
            if left > right:
                return None
        value = float(np.clip(np.dot(direction, preferred - point), left, right))
        return point + value * direction
