from simulator.environment import WarehouseSimulation
from simulator.physics import valid_position


def stable_projection(result):
    ignored = {"algorithm_time_total_ms", "algorithm_time_mean_ms", "algorithm_time_p95_ms"}
    return {key: value for key, value in result.items() if key not in ignored}


def test_robot_reaches_goal_without_agents_for_all_algorithms():
    for algorithm in ("naive", "vo", "orca"):
        result = WarehouseSimulation("warehouse", algorithm, 0, 7).run()
        assert result["success"], algorithm
        assert result["goal_reaching_time_s"] is not None


def test_robot_never_enters_static_obstacle():
    simulation = WarehouseSimulation("warehouse", "orca", 5, 42)
    simulation.run()
    assert all(valid_position(point, simulation.robot.radius, simulation.scenario.width,
                              simulation.scenario.height, simulation.scenario.obstacles)
               for point in simulation.robot.trajectory)


def test_same_seed_reproduces_physical_results():
    first = WarehouseSimulation("crossing", "vo", 10, 91).run()
    second = WarehouseSimulation("crossing", "vo", 10, 91).run()
    assert stable_projection(first) == stable_projection(second)


def test_timeout_is_not_reported_as_success():
    result = WarehouseSimulation("crowded", "naive", 20, 42, timeout=0.2).run()
    assert result["success"] is False
    assert result["goal_reaching_time_s"] is None
