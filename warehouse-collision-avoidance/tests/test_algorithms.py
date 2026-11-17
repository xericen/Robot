import numpy as np

from algorithms.naive import NaiveAvoidance
from algorithms.orca import ORCAAvoidance
from algorithms.velocity_obstacle import VelocityObstacleAvoidance, collision_within_horizon
from simulator.agents import Agent, ControlledRobot


def make_agents():
    robot = ControlledRobot("robot", np.array([0.0, 0.0]), np.zeros(2), np.array([10.0, 0.0]), radius=0.3)
    person = Agent("worker", np.array([0.7, 0.0]), np.array([-0.2, 0.0]), np.array([-5.0, 0.0]), radius=0.3)
    return robot, person


def test_naive_changes_velocity_inside_safety_zone():
    robot, person = make_agents()
    velocity, diagnostics = NaiveAvoidance().choose_velocity(robot, [person], np.array([1.0, 0.0]), 0.3, 0.1)
    assert diagnostics.neighbor_checks == 1
    assert velocity[0] < 1.0


def test_vo_uses_future_relative_motion():
    assert collision_within_horizon(np.array([2.0, 0.0]), np.array([-1.0, 0.0]), 0.6, 3.0)
    assert not collision_within_horizon(np.array([2.0, 0.0]), np.array([1.0, 0.0]), 0.6, 3.0)
    robot, person = make_agents()
    _, diagnostics = VelocityObstacleAvoidance().choose_velocity(robot, [person], np.array([1.0, 0.0]), 0.3, 0.1)
    assert diagnostics.candidate_checks > 1


def test_orca_builds_half_plane_and_bounded_velocity():
    robot, person = make_agents()
    velocity, diagnostics = ORCAAvoidance().choose_velocity(robot, [person], np.array([1.0, 0.0]), 0.3, 0.1)
    assert diagnostics.constraints == 1
    assert np.isfinite(velocity).all()
    assert np.linalg.norm(velocity) <= robot.max_speed + 1e-9
