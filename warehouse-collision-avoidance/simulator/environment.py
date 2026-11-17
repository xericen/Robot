from __future__ import annotations

import time

import numpy as np

from algorithms import create_algorithm
from algorithms.pathfinding import astar_path
from experiments.metrics import MetricsRecorder
from experiments.scenarios import Scenario, create_scenario
from simulator.agents import Agent, ControlledRobot
from simulator.physics import valid_position


class WarehouseSimulation:
    def __init__(self, scenario_name: str = "warehouse", algorithm_name: str = "orca",
                 agent_count: int = 20, seed: int = 42, safety_distance: float = 0.35,
                 cooperative: bool = False, dt: float = 0.1, timeout: float = 60.0) -> None:
        self.scenario_name = scenario_name
        self.algorithm_name = algorithm_name.lower()
        self.agent_count = agent_count
        self.seed = seed
        self.safety_distance = safety_distance
        self.cooperative = cooperative
        self.dt = dt
        self.timeout = timeout
        self.elapsed = 0.0
        self.scenario: Scenario = create_scenario(scenario_name, agent_count, seed, cooperative)
        self.algorithm = create_algorithm(self.algorithm_name)
        self.robot = ControlledRobot(
            identifier="controlled-robot", position=self.scenario.start.copy(), velocity=np.zeros(2),
            goal=self.scenario.goal.copy(), radius=0.38, max_speed=1.2, cooperative=True,
        )
        self.robot.path = astar_path(
            self.robot.position, self.robot.goal, self.scenario.width, self.scenario.height,
            self.scenario.obstacles, self.robot.radius + 0.05,
        )
        self.robot.trajectory = [self.robot.position.copy()]
        self.metrics = MetricsRecorder(safety_distance)
        self.finished = False

    @property
    def agents(self) -> list[Agent]:
        return self.scenario.agents

    def step(self) -> bool:
        if self.finished:
            return False
        old_robot = self.robot.position.copy()
        old_agents = {agent.identifier: agent.position.copy() for agent in self.agents}
        preferred = self.robot.preferred_velocity()
        started = time.perf_counter_ns()
        velocity, diagnostics = self.algorithm.choose_velocity(
            self.robot, self.agents, preferred, self.safety_distance, self.dt,
        )
        computation_ms = (time.perf_counter_ns() - started) / 1_000_000
        next_robot = self.robot.position + velocity * self.dt
        if valid_position(next_robot, self.robot.radius, self.scenario.width, self.scenario.height, self.scenario.obstacles):
            self.robot.position = next_robot
            self.robot.velocity = velocity
        else:
            self.robot.velocity = np.zeros(2)
        for agent in self.agents:
            agent.advance_patrol_goal()
            desired = agent.preferred_velocity()
            next_position = agent.position + desired * self.dt
            if valid_position(next_position, agent.radius, self.scenario.width, self.scenario.height, self.scenario.obstacles):
                agent.position = next_position
                agent.velocity = desired
            else:
                agent.goal, agent.origin = agent.origin.copy(), agent.goal.copy()
                agent.velocity = -agent.velocity
        self.elapsed += self.dt
        self.robot.trajectory.append(self.robot.position.copy())
        self.metrics.record_step(self.robot, old_robot, self.agents, old_agents, self.dt, computation_ms, diagnostics)
        reached = float(np.linalg.norm(self.robot.goal - self.robot.position)) <= 0.45
        timed_out = self.elapsed >= self.timeout
        if reached or timed_out:
            self.finished = True
            self.robot.status = "success" if reached else "timeout"
        else:
            self.robot.status = "running"
        return not self.finished

    def run(self) -> dict:
        while self.step():
            pass
        result = self.metrics.result(self.robot.status == "success", self.elapsed, self.timeout)
        result.update({
            "scenario": self.scenario_name,
            "algorithm": self.algorithm.name,
            "agent_count": self.agent_count,
            "seed": self.seed,
            "cooperative": self.cooperative,
            "safety_distance_m": self.safety_distance,
            "steps": len(self.metrics.computation_times_ms),
        })
        return result
