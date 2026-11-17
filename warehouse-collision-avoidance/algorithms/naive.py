from __future__ import annotations

import numpy as np

from .base import AlgorithmDiagnostics, AvoidanceAlgorithm
from simulator.agents import Agent, ControlledRobot


class NaiveAvoidance(AvoidanceAlgorithm):
    """Current-distance-only reactive avoidance; it never predicts future positions."""

    name = "Naive"
    stop_margin = 0.0
    influence = 1.2

    def choose_velocity(self, robot: ControlledRobot, neighbors: list[Agent], preferred: np.ndarray,
                        safety_distance: float, dt: float) -> tuple[np.ndarray, AlgorithmDiagnostics]:
        diagnostics = AlgorithmDiagnostics()
        repulsion = np.zeros(2, dtype=float)
        emergency = False
        for other in neighbors:
            diagnostics.neighbor_checks += 1
            offset = robot.position - other.position
            distance = float(np.linalg.norm(offset))
            required = robot.radius + other.radius + safety_distance
            if distance < required + self.stop_margin:
                emergency = True
            if distance < required + self.influence:
                direction = offset / max(distance, 1e-9)
                repulsion += direction * (required + self.influence - distance) / self.influence
        if emergency and np.linalg.norm(repulsion) < 1e-9:
            return np.zeros(2), diagnostics
        velocity = preferred * (0.25 if emergency else 1.0) + repulsion * robot.max_speed
        return self.limit_speed(velocity, robot.max_speed), diagnostics
