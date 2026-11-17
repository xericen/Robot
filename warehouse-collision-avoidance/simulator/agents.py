from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np


AgentKind = Literal["robot", "worker"]


@dataclass
class Agent:
    identifier: str
    position: np.ndarray
    velocity: np.ndarray
    goal: np.ndarray
    radius: float = 0.3
    max_speed: float = 1.0
    kind: AgentKind = "worker"
    cooperative: bool = False
    origin: np.ndarray = field(default_factory=lambda: np.zeros(2, dtype=float))

    def __post_init__(self) -> None:
        self.position = np.asarray(self.position, dtype=float)
        self.velocity = np.asarray(self.velocity, dtype=float)
        self.goal = np.asarray(self.goal, dtype=float)
        if not np.any(self.origin):
            self.origin = self.position.copy()
        else:
            self.origin = np.asarray(self.origin, dtype=float)

    def preferred_velocity(self) -> np.ndarray:
        delta = self.goal - self.position
        distance = float(np.linalg.norm(delta))
        if distance < 1e-9:
            return np.zeros(2, dtype=float)
        return delta / distance * min(self.max_speed, distance)

    def advance_patrol_goal(self) -> None:
        if np.linalg.norm(self.goal - self.position) > 0.25:
            return
        old_goal = self.goal.copy()
        self.goal = self.origin.copy()
        self.origin = old_goal


@dataclass
class ControlledRobot(Agent):
    kind: AgentKind = "robot"
    max_speed: float = 1.2
    status: str = "ready"
    path: list[np.ndarray] = field(default_factory=list)
    waypoint_index: int = 0
    trajectory: list[np.ndarray] = field(default_factory=list)

    def current_waypoint(self) -> np.ndarray:
        if not self.path:
            return self.goal
        self.waypoint_index = min(self.waypoint_index, len(self.path) - 1)
        waypoint = self.path[self.waypoint_index]
        if np.linalg.norm(waypoint - self.position) < 0.35 and self.waypoint_index < len(self.path) - 1:
            self.waypoint_index += 1
            waypoint = self.path[self.waypoint_index]
        return waypoint

    def preferred_velocity(self) -> np.ndarray:
        target = self.current_waypoint()
        delta = target - self.position
        distance = float(np.linalg.norm(delta))
        if distance < 1e-9:
            return np.zeros(2, dtype=float)
        return delta / distance * min(self.max_speed, distance / 0.1)
