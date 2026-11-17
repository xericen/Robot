import numpy as np

from simulator.physics import circle_rectangle_collision, swept_minimum_separation


def test_circle_rectangle_collision_is_geometric():
    shelf = (2.0, 2.0, 2.0, 2.0)
    assert circle_rectangle_collision(np.array([1.8, 3.0]), 0.3, shelf)
    assert not circle_rectangle_collision(np.array([1.0, 3.0]), 0.3, shelf)


def test_swept_collision_detects_between_frames():
    separation = swept_minimum_separation(
        np.array([0.0, 0.0]), np.array([2.0, 0.0]),
        np.array([1.0, -1.0]), np.array([1.0, 1.0]),
    )
    assert separation == 0.0
