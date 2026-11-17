from __future__ import annotations

import math

import numpy as np

from .base import AlgorithmDiagnostics, AvoidanceAlgorithm
from simulator.agents import Agent, ControlledRobot


def collision_within_horizon(relative_position: np.ndarray, relative_velocity: np.ndarray,
                             combined_radius: float, horizon: float) -> bool:
    c = float(np.dot(relative_position, relative_position) - combined_radius ** 2)
    if c <= 0:
        return True
    a = float(np.dot(relative_velocity, relative_velocity))
    if a < 1e-12:
        return False
    b = float(2 * np.dot(relative_position, relative_velocity))
    discriminant = b * b - 4 * a * c
    if discriminant < 0:
        return False
    root = math.sqrt(discriminant)
    entry = (-b - root) / (2 * a)
    exit_time = (-b + root) / (2 * a)
    return exit_time >= 0 and entry <= horizon


class VelocityObstacleAvoidance(AvoidanceAlgorithm):
    name = "VO"

    def __init__(self, horizon: float = 3.0, angular_samples: int = 24) -> None:
        self.horizon = horizon
        self.angular_samples = angular_samples
        self.candidate_count = 2 + 3 * angular_samples

    def choose_velocity(self, robot: ControlledRobot, neighbors: list[Agent], preferred: np.ndarray,
                        safety_distance: float, dt: float) -> tuple[np.ndarray, AlgorithmDiagnostics]:
        diagnostics = AlgorithmDiagnostics()
        candidates = [preferred.copy(), np.zeros(2, dtype=float)]
        remaining = self.candidate_count - 2
        for ring, speed_fraction in enumerate((0.35, 0.65, 1.0)):
            count = remaining // 3 + int(ring < remaining % 3)
            for index in range(count):
                angle = 2 * math.pi * index / count
                candidates.append(np.array([math.cos(angle), math.sin(angle)]) * robot.max_speed * speed_fraction)
        best = np.zeros(2, dtype=float)
        best_cost = float("inf")
        for candidate in candidates:
            diagnostics.candidate_velocity_checks += 1
            safe = True
            for other in neighbors:
                diagnostics.neighbor_checks += 1
                diagnostics.candidate_checks += 1
                relative_position = other.position - robot.position
                relative_velocity = other.velocity - candidate
                radius = robot.radius + other.radius + safety_distance
                if collision_within_horizon(relative_position, relative_velocity, radius, self.horizon):
                    safe = False
                    break
            if not safe:
                continue
            cost = float(np.dot(candidate - preferred, candidate - preferred))
            if cost < best_cost:
                best, best_cost = candidate, cost
        return self.limit_speed(best, robot.max_speed), diagnostics
