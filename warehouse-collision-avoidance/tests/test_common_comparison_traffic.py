"""Common comparison spawns affect workers without moving scripted AMRs onto them."""
import contextlib,io
import numpy as np
import pytest
from newton_warehouse import run

@pytest.mark.parametrize("map_id",[f"map{i}" for i in range(1,7)])
def test_hard_comparison_keeps_distinct_amrs_and_common_workers(map_id):
    with contextlib.redirect_stdout(io.StringIO()):
        r=run(scenario_name="hard",agent_count=9,map_id=map_id,common_traffic=True,frames=1,trace_stride=1)
    assert r["worker_count"]==7 and r["other_robot_count"]==2
    bodies={b["id"]:b for b in r["bodies"]};q=r["frames"][0]["body_q"]
    for i,spawn in enumerate([[35,3],[3,23],[35,23],[3,3]]):
        np.testing.assert_allclose(q[bodies[f"worker-{i}"]["body"]][:2],spawn,atol=.003)
    for i,a in enumerate(r["bodies"]):
        for b in r["bodies"][i+1:]:
            assert np.linalg.norm(np.array(q[a["body"]][:2])-q[b["body"]][:2]) >= a["radius"]+b["radius"]+.2
    assert r["common_traffic"]
