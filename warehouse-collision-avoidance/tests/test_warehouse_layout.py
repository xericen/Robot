"""Layout and render/physics registration regressions for the expanded warehouse."""
import contextlib
import io
import numpy as np
import pytest

from experiments.scenarios import create_scenario
from algorithms.pathfinding import astar_path
from simulator.physics import valid_position


@pytest.mark.parametrize("name,workers,robots", [
    ("easy", 2, 1), ("medium", 4, 1), ("hard", 7, 3), ("crowded", 12, 5)])
@pytest.mark.parametrize("seed", [0, 7, 42, 123])
def test_safe_population_and_connected_aisles(name, workers, robots, seed):
    scenario = create_scenario(name, 16, seed)
    assert (scenario.width, scenario.height) == (38, 26)
    assert sum(a.kind == "worker" for a in scenario.agents) == workers
    assert sum(a.kind == "robot" for a in scenario.agents) + 1 == robots
    positions = [(scenario.start, .42)] + [(a.position, a.radius) for a in scenario.agents]
    for i, (p, radius) in enumerate(positions):
        assert valid_position(p, radius + .25, scenario.width, scenario.height, scenario.obstacles)
        for q, other_radius in positions[i + 1:]:
            assert np.linalg.norm(p-q) >= radius + other_radius + .35
    crossing = 0
    for agent in scenario.agents:
        assert all(np.linalg.norm(agent.position-p) >= scenario.protected_radius + agent.radius
                   for p in (scenario.start, scenario.goal))
        for t in np.linspace(0, 1, 60):
            assert valid_position(agent.position*(1-t)+agent.goal*t, agent.radius,
                                  scenario.width, scenario.height, scenario.obstacles)
        if agent.kind == "worker" and (agent.position[1]-13)*(agent.goal[1]-13) < 0:
            crossing += 1
    assert 0 < crossing < workers
    path = astar_path(scenario.start, scenario.goal, scenario.width, scenario.height,
                      scenario.obstacles, .42 + .35)
    for a, b in zip(path, path[1:]):
        for t in np.linspace(0, 1, 100):
            assert valid_position(a*(1-t)+b*t, .42+.35, scenario.width, scenario.height, scenario.obstacles)
    repeated = create_scenario(name, 16, seed)
    np.testing.assert_allclose([a.position for a in scenario.agents], [a.position for a in repeated.agents])


def test_crowded_manual_count_is_preserved():
    for count in (0, 12, 40, 80, 120):
        assert len(create_scenario("crowded", count, 42).agents) == count


def test_visual_meshes_fit_reviewed_collision_footprints():
    from warehouse_visuals import amr_mesh, worker_mesh, rack_mesh
    robot = amr_mesh(.42, .26)
    worker = worker_mesh(.30, .55)
    assert np.linalg.norm(robot.vertices[:, :2], axis=1).max() <= .42
    assert np.max(np.abs(robot.vertices[:, 2])) <= .260001
    assert np.linalg.norm(worker.vertices[:, :2], axis=1).max() <= .30
    assert np.max(np.abs(worker.vertices[:, 2])) <= .850001
    rack = rack_mesh(3, 7, 3.2)
    assert np.max(np.abs(rack.vertices[:, 0])) <= 1.5
    assert np.max(np.abs(rack.vertices[:, 1])) <= 3.5
    assert rack.bounds[0, 2] >= 0 and rack.bounds[1, 2] <= 3.2


@pytest.mark.parametrize("method", ["naive", "vo", "orca"])
def test_expanded_medium_physically_avoids_and_arrives(method):
    import newton_warehouse as engine
    with contextlib.redirect_stdout(io.StringIO()):
        result = engine.run(algorithm_name=method, scenario_name="medium", frames=1800, trace_stride=5)
    assert result["status"] == "success"
    assert result["goal_distance_m"] <= .25
    assert result["worker_count"] == 4 and result["other_robot_count"] == 0
    assert result["collisions"] == 0
    assert max(abs(f["target_velocity"][1]) for f in result["frames"]) > .1
    assert max(abs(f["robot"][1]-13) for f in result["frames"]) > .1
    assert min(1-2*(q[3]**2+q[4]**2) for f in result["frames"] for q in f["body_q"][1:]) > .97


def test_visual_roots_follow_full_newton_pose_without_extra_colliders(tmp_path):
    import newton_warehouse as engine
    from newton_live import LiveBridge

    class Probe(LiveBridge):
        def before_frame(self):
            self.phase = "running"

        def after_frame(self, frame, state):
            super().after_frame(frame, state)
            for b in self.meta["bodies"]:
                q = np.asarray(frame["body_q"][b["body"]])
                root = self.visuals.roots[b["id"]]
                np.testing.assert_allclose(root.position, q[:3], atol=1e-6)
                np.testing.assert_allclose(root.wxyz, q[[6, 3, 4, 5]], atol=1e-6)

    bridge = Probe(tmp_path, {"frames": 3})
    try:
        result = engine.run(scenario_name="easy", frames=3, trace_stride=1, bridge=bridge)
        assert bridge.model.body_count == 3
        assert bridge.model.shape_count == 14  # ground + 4 walls + 6 racks + 3 simple bodies
        assert len(bridge.visuals.roots) == 3
        assert not bridge.viewer.show_visual and not bridge.viewer.show_collision
    finally:
        bridge.transport.shutdown()
        bridge.viewer.close()


def test_old_record_uses_recorded_geometry_and_agent_types(tmp_path):
    import newton_warehouse as engine
    from newton_live import LiveBridge
    with contextlib.redirect_stdout(io.StringIO()):
        record = engine.run(scenario_name="warehouse", agent_count=2, frames=3)

    class Attached(Exception):
        pass

    class ReplayProbe(LiveBridge):
        def before_frame(self):
            raise Attached()

    bridge = ReplayProbe(tmp_path, {"frames": 3, "record": record})
    try:
        with pytest.raises(Attached):
            engine.run(scenario_name="medium", agent_count=4, frames=3, bridge=bridge)
        assert bridge.meta["width"] == 24 and bridge.meta["height"] == 16
        assert bridge.model.body_count == 3
        np.testing.assert_allclose(bridge.replay_state.body_q.numpy(), record["frames"][0]["body_q"])
    finally:
        bridge.transport.shutdown()
        bridge.viewer.close()


def test_scripted_amrs_do_not_claim_reciprocal_avoidance():
    import newton_warehouse as engine
    with contextlib.redirect_stdout(io.StringIO()):
        result = engine.run(scenario_name="hard", frames=3)
    assert result["other_robot_count"] == 2
    assert all(not b["cooperative"] for b in result["bodies"][1:])
