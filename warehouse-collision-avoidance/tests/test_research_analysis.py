import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from research_orca import feasible_velocity
from research_statistics import cluster_ci,describe,comparison,paired_differences
from research_data import ROOT,MAIN,PILOT,inputs,assert_originals
from algorithms import create_algorithm
from simulator.agents import Agent,ControlledRobot

@pytest.mark.parametrize("speed,offset,possible",[(1,0.5,True),(1,1.5,False),(1,1,True),(2,1.5,True)])
def test_independent_halfplane_disk_oracle(speed,offset,possible):
    v=feasible_velocity([{"point":[offset,0],"direction":[0,-2]}],speed)
    assert (v is not None)==possible
    if possible:assert v[0]>=offset-1e-7 and np.linalg.norm(v)<=speed+1e-7

def test_mutually_inconsistent_constraints():
    assert feasible_velocity([{"point":[.5,0],"direction":[0,-1]},
                              {"point":[-.5,0],"direction":[0,1]}],2) is None

def test_cluster_bootstrap_does_not_count_duplicate_configurations_as_seeds():
    ci=cluster_ci([0,1],[42,43])
    assert cluster_ci([0,0,1,1],[42,42,43,43])==ci
    assert ci[2]==2
    assert cluster_ci([1],[42])==(None,None,1)

def test_missing_runtime_is_not_imputed_from_average():
    d=describe(pd.DataFrame({"seed":[42,43],"algo_time_avg_ms":[1,2]}),"algo_time_p95_ms")
    assert d["mean"] is None and d["observations"]==0

def test_paired_mismatched_scene_is_rejected():
    rows=[]
    for a,h in [("Naive","a"),("VO","b"),("ORCA","a")]:
        rows.append(dict(algorithm=a,map="map1",encounter_mode="crossing",population_mode="workers",
                         agent_count=2,seed=42,scene_hash=h,success=1))
    with pytest.raises(ValueError,match="scene mismatch"):paired_differences(pd.DataFrame(rows))

@pytest.mark.parametrize("seed",range(10))
def test_orca_feasible_outputs_match_independent_oracle(seed):
    rng=np.random.default_rng(seed)
    robot=ControlledRobot("r",np.zeros(2),np.zeros(2),np.array([10.,0.]))
    agents=[Agent(str(i),rng.uniform(-4,4,2),rng.uniform(-.5,.5,2),np.zeros(2)) for i in range(4)]
    solver=create_algorithm("orca");v,_=solver.choose_velocity(robot,agents,np.array([1.,0.]),.35,1/30)
    lines=[{"point":p,"direction":d} for p,d in solver.last_lines]
    if feasible_velocity(lines,robot.max_speed) is not None:
        assert all((d[0]*(p-v)[1]-d[1]*(p-v)[0])<=1e-7 for p,d in solver.last_lines)

@pytest.mark.skipif(not (MAIN/"measurements.csv").exists(),reason="historical study not installed")
def test_raw_success_denominators_and_goal_safety_distinction():
    main,_=inputs()
    assert len(main)==240
    assert tuple(int(main[c].sum()) for c in ("success","collision_free_success","safe_success"))==(227,152,53)
    assert main.groupby("algorithm").size().tolist()==[80,80,80]
    assert main.groupby(["map","encounter_mode","population_mode","agent_count","seed"]).scene_hash.nunique().eq(1).all()
    assert (main.safe_success<=main.collision_free_success).all()
    assert (main.collision_free_success<=main.success).all()

def test_frame_instrumentation_measures_only_real_steps():
    from newton_warehouse import run
    r=run(algorithm_name="orca",agent_count=2,frames=5,seed=42,persist=False,quiet=True,capture_telemetry=True)
    samples=r["algorithm_samples_ms"]
    assert len(samples)==r["algo_steps"]==len(r["telemetry"])
    assert r["algo_time_p95_ms"]==pytest.approx(np.percentile(samples,95))
    assert r["algo_time_median_ms"]==pytest.approx(np.median(samples))
    assert r["constraint_evaluations"]>0
    assert all("preferred_velocity" in f and "neighbors_before" in f for f in r["telemetry"])
