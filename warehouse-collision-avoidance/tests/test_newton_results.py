import csv
import importlib.util
from pathlib import Path
import numpy as np
import pytest

from newton_results import FIELDS, PARAMETERS, load_results, result_row, settings, write_rows
from algorithms import create_algorithm
from simulator.agents import Agent, ControlledRobot


def test_timeout_is_not_an_arrival_and_atomic_roundtrip(tmp_path):
    row = dict.fromkeys(FIELDS, None)
    row.update(map="map1", algorithm="ORCA", scenario="medium", seed=42,
               success=0, timeout=1, path_length_m=12.5)
    target = tmp_path / "map1_orca_medium_42.csv"
    write_rows(target, [row])
    with target.open() as handle:
        saved = next(csv.DictReader(handle))
    assert saved["arrival_time_s"] == ""
    assert saved["success"] == "0" and saved["timeout"] == "1"
    assert not list(tmp_path.glob("tmp*"))


def test_settings_reject_invalid_and_keep_original_defaults():
    assert settings() == PARAMETERS
    for overrides in ({"vo_candidates": 1}, {"vo_candidates": 4.5}, {"time_step_s": 0},
                      {"orca_neighbor_dist_m": float("nan")}, {"unknown": 1}):
        with pytest.raises(ValueError):
            settings(overrides)


def test_vo_default_candidates_and_parameterized_count():
    robot = ControlledRobot("r", np.array([0., 0.]), np.zeros(2), np.array([10., 0.]))
    person = Agent("p", np.array([50., 50.]), np.zeros(2), np.array([0., 0.]))
    algorithm = create_algorithm("vo")
    _, stats = algorithm.choose_velocity(robot, [person], np.array([1., 0.]), .35, 1/30)
    assert stats.candidate_checks == 74
    algorithm.candidate_count = 11
    _, stats = algorithm.choose_velocity(robot, [person], np.array([1., 0.]), .35, 1/30)
    assert stats.candidate_checks == 11


def test_orca_neighbor_limits_are_optional():
    robot = ControlledRobot("r", np.array([0., 0.]), np.zeros(2), np.array([10., 0.]))
    agents = [Agent(str(i), np.array([float(i+2), 1.]), np.zeros(2), np.zeros(2)) for i in range(4)]
    algorithm = create_algorithm("orca")
    _, stats = algorithm.choose_velocity(robot, agents, np.array([1., 0.]), .35, 1/30)
    assert stats.constraints == 4
    algorithm.neighbor_dist = 3
    algorithm.max_neighbors = 1
    _, stats = algorithm.choose_velocity(robot, agents, np.array([1., 0.]), .35, 1/30)
    assert stats.constraints == 1


@pytest.mark.parametrize("algorithm", ["naive", "vo", "orca"])
def test_newton_csv_matches_measured_steps_and_population(algorithm, tmp_path, monkeypatch):
    import newton_results
    from newton_warehouse import run
    monkeypatch.setattr(newton_results, "ROOT", tmp_path)
    result = run(algorithm_name=algorithm, scenario_name="easy", agent_count=8,
                 frames=3, quiet=True)
    assert result["agent_count"] == 2  # preset population, not ignored CLI argument
    assert result["algo_steps"] == 3
    assert result["algo_time_max_ms"] >= result["algo_time_avg_ms"] > 0
    assert result["wall_time_s"] > 0
    saved = result_row(result)
    assert saved["success"] == 0 and saved["timeout"] == 1
    assert saved["arrival_time_s"] is None
    assert saved["replan_count"] == 0
    files = list(tmp_path.glob("*.csv"))
    assert len(files) == 1
    assert next(csv.DictReader(files[0].open()))["algo_steps"] == "3"


def test_engine_applies_candidate_count_and_common_timestep():
    from newton_warehouse import run
    result = run(algorithm_name="vo", scenario_name="easy", agent_count=2, frames=3,
                 parameters={"vo_candidates": 11, "time_step_s": .02}, quiet=True)
    assert result["candidate_checks"] == 3 * 11 * 2
    assert result["sim_time_s"] == pytest.approx(.06)
    assert result["parameters"]["vo_candidates"] == 11


def test_engine_applies_orca_neighbor_limit():
    from newton_warehouse import run
    result = run(algorithm_name="orca", scenario_name="easy", agent_count=2, frames=3,
                 parameters={"orca_max_neighbors": 1}, quiet=True)
    assert result["constraints"] == 3
