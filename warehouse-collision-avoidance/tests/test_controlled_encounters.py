import contextlib
import io
import json
from pathlib import Path
import numpy as np
import pytest
from encounter_scenarios import configure, scene_fingerprint
from experiments.scenarios import create_scenario
from newton_safety import clearances, rectangle_distance
from simulator.physics import valid_position
from algorithms.planners import plan


def scene(mode="crossing", population="workers", n=4, seed=42, map_id="map1"):
    s=create_scenario("crowded",n,seed,map_id=map_id)
    config=configure(s,mode,population,n,seed,.35,1.2,"astar",42)
    return s,config


@pytest.mark.parametrize("mode",["head_on","crossing","narrow_passing"])
@pytest.mark.parametrize("seed",[42,43,44])
def test_seeded_valid_encounters(mode,seed):
    s,a=scene(mode=mode,seed=seed)
    t,b=scene(mode=mode,seed=seed)
    assert a==b
    assert len(a["actors"])==4
    for agent in s.agents:
        assert valid_position(agent.position,agent.radius+.15,s.width,s.height,s.obstacles)
        assert agent.release_time_s>=0
    path,_=plan("astar",s.start,s.goal,s.width,s.height,s.obstacles,.77,42)
    assert len(path)>=2
    if mode=="narrow_passing":
        assert len(a["barriers"])==2 and a["passage_width_m"]==2.8


@pytest.mark.parametrize("map_id",["map1","map2","map3","map4","map5","map6"])
def test_crossing_valid_for_all_maps(map_id):
    scene(map_id=map_id)


def test_seed_changes_encounter_and_worker_cohort_is_nested():
    _,a=scene(n=2)
    _,b=scene(n=8)
    _,c=scene(n=2,seed=43)
    assert a["actors"]==b["actors"][:2]
    assert a["actors"]!=c["actors"]
    assert all(a["kind"]=="worker" for a in b["actors"])
    _,mixed=scene(population="mixed",n=8)
    assert sum(a["kind"]=="robot" for a in mixed["actors"])==2


def test_signed_distance_handles_rotation_and_penetration():
    assert rectangle_distance(np.array([0.,0.]),[-1,-1,2,2]) == -1
    assert rectangle_distance(np.array([3.,0.]),[-1,-1,2,2]) == 2
    assert rectangle_distance(np.array([0.,0.]),{"position":[0,0],"size":[2,2],"rotation":45})==pytest.approx(-1)


@pytest.mark.parametrize("mode",["head_on","crossing","narrow_passing"])
def test_actual_engine_identical_scene_across_algorithms(mode):
    from newton_warehouse import run
    hashes=[]
    for algorithm in ("naive","vo","orca"):
        with contextlib.redirect_stdout(io.StringIO()):
            r=run(algorithm_name=algorithm,scenario_name="crowded",agent_count=4,frames=3,
                  encounter_mode=mode,population_mode="workers",quiet=True,persist=False)
        hashes.append(r["scene_hash"])
        assert r["success"] if "success" in r else r["status"]=="timeout"
        assert r["safe_success"]==0 and r["collision_free_success"]==0
        assert r["min_separation_m"] is not None
        assert len(r["shelf_poses"])==(8 if mode=="narrow_passing" else 6)
    assert len(set(hashes))==1


def test_run_archive_preserves_both_executions(tmp_path,monkeypatch):
    import newton_results
    from newton_warehouse import run
    monkeypatch.setattr(newton_results,"ROOT",tmp_path)
    with contextlib.redirect_stdout(io.StringIO()):
        first=run(scenario_name="medium",agent_count=4,frames=2,quiet=True)
        original=(tmp_path/"map1_orca_medium_42.csv").read_bytes()
        second=run(scenario_name="medium",agent_count=4,frames=2,quiet=True)
        assert (tmp_path/"map1_orca_medium_42.csv").read_bytes()==original
    assert first["run_id"]!=second["run_id"]
    for r in (first,second):
        folder=tmp_path/"runs"/r["run_id"]
        for name in ("metrics.csv","configuration.json","initial_state.json","provenance.json",
                     "orca_diagnostics.jsonl","result.json","complete.json"):
            assert (folder/name).exists()
        p=json.loads((folder/"provenance.json").read_text())
        assert p["source_sha256"] and p["dependencies"]
    assert len(list((tmp_path/"legacy_snapshots").glob("*.csv")))==1
    assert len(newton_results.load_results(history=True))==2
    import csv
    staging=tmp_path/"runs"/"unfinished";staging.mkdir()
    row=next(csv.DictReader((tmp_path/"runs"/first["run_id"]/"metrics.csv").open()))
    row["run_id"]="unfinished"
    newton_results.write_rows(staging/"metrics.csv",[row])
    assert len(newton_results.load_results(history=True))==2


def test_controlled_traffic_is_not_mislabelled_as_legacy_corner_patrols():
    from newton_warehouse import run
    hashes=[]
    for common in (True,False):
        r=run(scenario_name="crowded",agent_count=4,frames=2,quiet=True,persist=False,
              encounter_mode="crossing",population_mode="workers",common_traffic=common)
        hashes.append(r["scene_hash"])
        assert r["common_traffic"] is False
    assert len(set(hashes))==1
