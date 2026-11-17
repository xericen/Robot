"""Independent comparisons share seeded crossing traffic; every worker crosses the R0 route."""
import contextlib,io,json,time
import numpy as np
import pytest
from experiments.scenarios import create_scenario
from encounter_scenarios import configure
from algorithms.planners import plan
from warehouse_maps import segment_clear
from newton_live import LiveBridge
from simulator.agents import Agent

def segment_distance(p,a,b):
    d=b-a
    return np.linalg.norm(p-(a+np.clip(np.dot(p-a,d)/np.dot(d,d),0,1)*d))

@pytest.mark.parametrize("map_id",[f"map{i}" for i in range(1,7)])
def test_all_workers_cross_and_reverse_on_each_map(map_id):
    s=create_scenario("crowded",4,42,map_id=map_id)
    encounter=configure(s,"crossing","workers",4,42,.35,1.2,"astar",42)
    path,_=plan("astar",s.start,s.goal,s.width,s.height,s.obstacles,.77,42)
    assert [a.identifier for a in s.agents]==[f"worker-{i}" for i in range(4)]
    for a in s.agents:
        # Their route midpoint lies on the actual R0 path; no corner-only spectator patrols.
        midpoint=(a.position+a.goal)/2
        assert min(segment_distance(midpoint,x,y) for x,y in zip(path,path[1:]))<1e-7
        assert segment_clear(a.position,a.goal,a.radius+.15,s.width,s.height,s.obstacles)
        start=a.position.copy();goal=a.goal.copy()
        a.position=goal.copy();a.advance_patrol_goal()
        assert np.array_equal(a.goal,start)
        a.position=start.copy();a.advance_patrol_goal()
        assert np.array_equal(a.goal,goal)
    assert len(encounter["actors"])==4

@pytest.mark.parametrize("map_id",[f"map{i}" for i in range(1,7)])
def test_three_actual_algorithms_have_same_initial_scene_on_each_map(map_id):
    from newton_warehouse import run
    hashes=[]
    for algorithm in ("naive","vo","orca"):
        with contextlib.redirect_stdout(io.StringIO()):
            r=run(algorithm_name=algorithm,scenario_name="medium",agent_count=4,seed=42,map_id=map_id,
                  encounter_mode="crossing",population_mode="workers",frames=3,persist=False,quiet=True)
        hashes.append(r["scene_hash"])
        assert r["algorithm"].lower()==algorithm
        assert r["worker_count"]==4 and r["algo_steps"]==3
    assert len(set(hashes))==1

def test_live_resume_honors_common_future_start_time(tmp_path):
    bridge=LiveBridge.__new__(LiveBridge)
    bridge.folder=tmp_path;bridge.command_id="";bridge.finished=False;bridge.phase="paused"
    bridge.publish=lambda:None
    when=time.time()+.1
    (tmp_path/"command.json").write_text(json.dumps({"id":"resume-all","action":"resume","start_at":when}))
    bridge.command()
    assert bridge.phase=="running" and bridge.resume_at==when
    bridge.before_frame()
    assert time.time()>=when

@pytest.mark.parametrize("worker_index",range(4))
def test_every_worker_has_real_newton_contact_with_r0(worker_index,monkeypatch):
    import newton_warehouse as engine
    factory=engine.create_scenario
    def overlapping(*args,**kwargs):
        scene=factory(*args,**kwargs)
        worker=scene.agents[worker_index]
        worker.position=scene.start+np.array([.25,0.])
        worker.origin=worker.position.copy();worker.goal=worker.position.copy()
        return scene
    monkeypatch.setattr(engine,"create_scenario",overlapping)
    with contextlib.redirect_stdout(io.StringIO()):
        r=engine.run(scenario_name="medium",agent_count=4,frames=3,trace_stride=1,traffic_mode="static",persist=False,quiet=True,capture_telemetry=True)
    assert r["collisions"]>0
    assert any(f"worker-{worker_index}_shape" in f["contact_labels"] for f in r["telemetry"])
