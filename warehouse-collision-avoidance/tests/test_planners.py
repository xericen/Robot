import numpy as np
import pytest
from algorithms.planners import plan, edge_clear
from warehouse_maps import get_map, shelf_geometry
from simulator.physics import circle_rectangle_collision

@pytest.mark.parametrize("map_id",[f"map{i}" for i in range(1,7)])
def test_same_clearance_and_optimal_grid_cost(map_id):
    config=get_map(map_id);obs=[g["obstacle"] for g in shelf_geometry(config)]
    paths=[]
    for planner in ("astar","dijkstra","rrt"):
        path,metrics=plan(planner,config["startPosition"],config["goalPosition"],38,26,obs,.77,42)
        assert all(edge_clear(a,b,.77,38,26,obs) for a,b in zip(path,path[1:]))
        assert metrics["planning_time_ms"]>0
        assert metrics["replanning_count"]==0
        assert (metrics["expanded_nodes"] is None)==(planner=="rrt")
        paths.append(metrics["planned_path_length_m"])
    assert paths[0]==pytest.approx(paths[1])

def test_oriented_collision_does_not_use_aabb_as_obstacle():
    rect={"position":[10,10],"size":[3,7],"rotation":45}
    assert circle_rectangle_collision(np.array([10,10]),.1,rect)
    local=np.array([2,3])
    angle=np.pi/4
    point=np.array([10,10])+np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])@local
    assert not circle_rectangle_collision(point,.1,rect)

def test_rrt_seed_reproducibility():
    c=get_map("map6");obs=[g["obstacle"] for g in shelf_geometry(c)]
    p,a=plan("rrt",c["startPosition"],c["goalPosition"],38,26,obs,.77,43)
    q,b=plan("rrt",c["startPosition"],c["goalPosition"],38,26,obs,.77,43)
    np.testing.assert_allclose(p,q);assert a["iterations"]==b["iterations"]
