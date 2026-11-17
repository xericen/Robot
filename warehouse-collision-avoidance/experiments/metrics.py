from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from simulator.agents import Agent, ControlledRobot
from simulator.physics import swept_minimum_separation


@dataclass
class MetricsRecorder:
    safety_distance: float
    computation_times_ms: list[float] = field(default_factory=list)
    path_length: float = 0.0
    collision_count: int = 0
    safety_violations: int = 0
    stop_time: float = 0.0
    minimum_separation: float = float("inf")
    neighbor_checks: int = 0
    candidate_checks: int = 0
    constraints: int = 0
    _active_collisions: set[str] = field(default_factory=set)
    _active_violations: set[str] = field(default_factory=set)

    def record_step(self, robot: ControlledRobot, old_robot: np.ndarray, agents: list[Agent],
                    old_agents: dict[str, np.ndarray], dt: float, computation_ms: float,
                    diagnostics) -> None:
        self.computation_times_ms.append(computation_ms)
        self.path_length += float(np.linalg.norm(robot.position - old_robot))
        if np.linalg.norm(robot.velocity) < 0.05:
            self.stop_time += dt
        current_collisions: set[str] = set()
        current_violations: set[str] = set()
        for agent in agents:
            separation = swept_minimum_separation(old_robot, robot.position, old_agents[agent.identifier], agent.position)
            self.minimum_separation = min(self.minimum_separation, separation)
            collision_limit = robot.radius + agent.radius
            if separation < collision_limit:
                current_collisions.add(agent.identifier)
            if separation < collision_limit + self.safety_distance:
                current_violations.add(agent.identifier)
        self.collision_count += len(current_collisions - self._active_collisions)
        self.safety_violations += len(current_violations - self._active_violations)
        self._active_collisions = current_collisions
        self._active_violations = current_violations
        self.neighbor_checks += diagnostics.neighbor_checks
        self.candidate_checks += diagnostics.candidate_checks
        self.constraints += diagnostics.constraints

    def result(self, success: bool, elapsed: float, timeout: float) -> dict[str, float | int | bool | None]:
        values = np.asarray(self.computation_times_ms or [0.0], dtype=float)
        return {
            "success": success,
            "goal_reaching_time_s": round(elapsed, 4) if success else None,
            "elapsed_physics_time_s": round(min(elapsed, timeout), 4),
            "path_length_m": round(self.path_length, 4),
            "collision_count": self.collision_count,
            "safety_violations": self.safety_violations,
            "algorithm_time_total_ms": round(float(values.sum()), 6),
            "algorithm_time_mean_ms": round(float(values.mean()), 6),
            "algorithm_time_p95_ms": round(float(np.percentile(values, 95)), 6),
            "robot_stop_time_s": round(self.stop_time, 4),
            "minimum_separation_m": None if self.minimum_separation == float("inf") else round(self.minimum_separation, 4),
            "neighbor_checks": self.neighbor_checks,
            "candidate_checks": self.candidate_checks,
            "orca_constraints": self.constraints,
        }
