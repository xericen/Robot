from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np

from simulator.agents import Agent, ControlledRobot


@dataclass
class AlgorithmDiagnostics:
    neighbor_checks: int = 0
    candidate_checks: int = 0
    constraints: int = 0


class AvoidanceAlgorithm(ABC):
    name = "base"

    @abstractmethod
    def choose_velocity(self, robot: ControlledRobot, neighbors: list[Agent], preferred: np.ndarray,
                        safety_distance: float, dt: float) -> tuple[np.ndarray, AlgorithmDiagnostics]:
        raise NotImplementedError

    @staticmethod
    def limit_speed(velocity: np.ndarray, maximum: float) -> np.ndarray:
        speed = float(np.linalg.norm(velocity))
        return velocity if speed <= maximum else velocity / speed * maximum
