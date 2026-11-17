"""Map catalogue, A* clearance, traffic and renderer/collider pose regressions."""
import contextlib
import io
import numpy as np
import pytest

from algorithms.pathfinding import astar_path
from experiments.scenarios import create_scenario
from warehouse_maps import map_catalog, get_map, validate_map, segment_clear, shelf_geometry


def test_six_distinct_maps_and_unchanged_baseline():
    maps = map_catalog()
    assert [m["mapId"] for m in maps] == [f"map{i}" for i in range(1, 7)]
    required = {"mapId", "mapName", "description", "shelfPositions", "shelfRotations",
                "startPosition", "goalPosition", "robotSpawnPosition", "workerSpawnPositions"}
    assert all(required <= m.keys() for m in maps)
    assert len({str(shelf_geometry(m)) for m in maps}) == 6
    baseline = create_scenario("medium", 4, 42)
    mapped = create_scenario("medium", 4, 42, map_id="map1")
    assert mapped.obstacles == baseline.obstacles
    np.testing.assert_allclose(mapped.start, baseline.start)
    np.testing.assert_allclose(mapped.goal, baseline.goal)
    np.testing.assert_allclose([a.position for a in mapped.agents],
                               [a.position for a in baseline.agents])


@pytest.mark.parametrize("map_id", [f"map{i}" for i in range(1, 7)])
@pytest.mark.parametrize("safety", [0, .35, 1])
def test_valid_six_shelves_and_connected_clearance(map_id, safety):
    config = get_map(map_id)
    geometry, path = validate_map(config, safety=safety)
    assert len(geometry) == 6
    np.testing.assert_allclose(path[0], config["robotSpawnPosition"])
    np.testing.assert_allclose(path[-1], config["goalPosition"])
    if map_id in ("map2", "map3", "map4", "map6"):
        assert not segment_clear(np.array(config["startPosition"]), np.array(config["goalPosition"]),
                                 .42+safety, 38, 26, [g["obstacle"] for g in geometry])


@pytest.mark.parametrize("map_id", [f"map{i}" for i in range(1, 7)])
@pytest.mark.parametrize("profile,count", [("medium", 4), ("hard", 16), ("crowded", 24)])
def test_preserved_workers_and_reproducible_safe_patrols(map_id, profile, count):
    scene = create_scenario(profile, count, 42, map_id=map_id)
    assert {f"worker-{i}" for i in range(4)} <= {a.identifier for a in scene.agents}
    positions = [(scene.start, .42)] + [(a.position, a.radius) for a in scene.agents]
    for i, (p, radius) in enumerate(positions):
        assert segment_clear(p, p, radius+.25, 38, 26, scene.obstacles)
        for q, other in positions[i+1:]:
            assert np.linalg.norm(p-q) >= radius+other+.35-1e-9
    for agent in scene.agents:
        assert segment_clear(agent.position, agent.goal, agent.radius+.15, 38, 26, scene.obstacles)
    repeat = create_scenario(profile, count, 42, map_id=map_id)
    np.testing.assert_allclose([a.position for a in scene.agents], [a.position for a in repeat.agents])


@pytest.mark.parametrize("map_id,via", [("map2", [19, 8]), ("map2", [19, 16]),
                                       ("map4", [16, 4]), ("map4", [16, 23])])
def test_alternative_routes(map_id, via):
    config = get_map(map_id)
    obstacles = [g["obstacle"] for g in shelf_geometry(config)]
    points = [config["startPosition"], via, config["goalPosition"]]
    for a, b in zip(points, points[1:]):
        path = astar_path(np.array(a), np.array(b), 38, 26, obstacles, .77)
        assert all(segment_clear(p, q, .77, 38, 26, obstacles) for p, q in zip(path, path[1:]))


@pytest.mark.parametrize("map_id", [f"map{i}" for i in range(1, 7)])
def test_rotated_shelf_collider_matches_render_and_navigation(map_id, tmp_path):
    import newton_warehouse as engine
    from newton_live import LiveBridge

    class Probe(LiveBridge):
        def before_frame(self):
            self.phase = "running"

        def after_frame(self, frame, state):
            super().after_frame(frame, state)
            transforms = self.model.shape_transform.numpy()
            for i, pose in enumerate(self.meta["shelf_poses"]):
                shape = self.model.shape_label.index(f"shelf_{i}")
                np.testing.assert_allclose(transforms[shape][:2], pose["position"], atol=1e-6)
                yaw = np.deg2rad(pose["rotation"])
                # Newton xyzw and Viser wxyz rotations describe the same shelf.
                np.testing.assert_allclose(transforms[shape][3:],
                                           [0, 0, np.sin(yaw/2), np.cos(yaw/2)], atol=1e-6)
                handle = self.visuals.racks[i]
                np.testing.assert_allclose(handle.position[:2], pose["position"], atol=1e-6)
                np.testing.assert_allclose(handle.wxyz, [np.cos(yaw/2), 0, 0, np.sin(yaw/2)], atol=1e-6)

    # Real Viser attach creates procedural rack meshes; no browser is required for pose checks.
    bridge = Probe(tmp_path, {"frames": 1})
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            result = engine.run(scenario_name="medium", agent_count=4, map_id=map_id,
                                frames=1, bridge=bridge)
        assert len(result["shelves"]) == 6
        assert result["mapId"] == map_id
    finally:
        bridge.transport.shutdown()
        bridge.viewer.close()


def test_unknown_map_and_diagonal_footprint():
    with pytest.raises(ValueError):
        get_map("missing")
    config = get_map("map1")
    config["shelfRotations"][0] = 45
    geometry, path = validate_map(config)
    assert isinstance(geometry[0]["obstacle"], dict)
    assert len(path) >= 2
