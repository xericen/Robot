import numpy as np

from algorithms.base import AlgorithmDiagnostics
from experiments.metrics import MetricsRecorder
from simulator.agents import Agent, ControlledRobot


def test_collision_and_safety_violation_are_separate_entries():
    robot = ControlledRobot("robot", np.array([0.2, 0.0]), np.array([1.0, 0.0]), np.array([5.0, 0.0]), radius=0.3)
    person = Agent("person", np.array([0.75, 0.0]), np.zeros(2), np.array([0.75, 1.0]), radius=0.3)
    recorder = MetricsRecorder(0.3)
    recorder.record_step(robot, np.array([0.0, 0.0]), [person], {"person": np.array([0.75, 0.0])},
                         0.1, 0.2, AlgorithmDiagnostics(neighbor_checks=1))
    result = recorder.result(False, 0.1, 60.0)
    assert result["collision_count"] == 1
    assert result["safety_violations"] == 1
    assert result["goal_reaching_time_s"] is None
    assert result["algorithm_time_mean_ms"] == 0.2
