import numpy as np

from algorithms.pathfinding import astar_path
from simulator.physics import valid_position


def test_astar_avoids_static_shelf():
    obstacles = [(4.0, 0.5, 2.0, 6.5)]
    path = astar_path(np.array([1.0, 4.0]), np.array([9.0, 4.0]), 10.0, 8.0, obstacles, 0.35)
    assert len(path) >= 3
    assert all(valid_position(point, 0.35, 10.0, 8.0, obstacles) for point in path)


def test_astar_reaches_requested_endpoints():
    start, goal = np.array([1.0, 1.0]), np.array([8.0, 6.0])
    path = astar_path(start, goal, 10.0, 8.0, [], 0.35)
    np.testing.assert_allclose(path[0], start)
    np.testing.assert_allclose(path[-1], goal)
