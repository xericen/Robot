"""Single-batch integrity, configuration pairing and incomplete-data rejection."""
import json
import pytest
from unified_batch import CONTRACT
import unified_batch as batch
import unified_analysis as analysis
from newton_results import write_rows

@pytest.fixture
def archive(tmp_path,monkeypatch):
    monkeypatch.setattr(batch,"ROOT",tmp_path);monkeypatch.setattr(batch,"STORE",tmp_path/"results/newton")
    monkeypatch.setattr(analysis,"ROOT",tmp_path);monkeypatch.setattr(analysis,"STORE",tmp_path/"results/newton")
    monkeypatch.setattr(analysis,"hashes",lambda:{})
    identity="20261117T120000_abcdef01";folder=batch.STORE/"studies"/identity;folder.mkdir(parents=True)
    (folder/"configuration.json").write_text(json.dumps({"kind":"unified-six-map","contract":CONTRACT,"engine_sha256":{}}))
    (folder/"progress.json").write_text(json.dumps({"phase":"complete","completed":90,"total":90}))
    rows=[]
    for m in CONTRACT["maps"]:
        for seed in CONTRACT["seeds"]:
            for algorithm in ("Naive","VO","ORCA"):
                rid=f"{m}_{seed}_{algorithm}";run=batch.STORE/"runs"/rid;run.mkdir(parents=True)
                scene=f"{m}_{seed}"
                r={"map":m,"algorithm":algorithm,"seed":seed,"run_id":rid,"scene_hash":scene,"encounter_mode":"crossing",
                   "population_mode":"workers","agent_count":4,"frame_limit":5400,"success":1,
                   "collision_count":0,"safety_violation_count":0,"path_length_m":33,"safe_success":1,"collision_free_success":1,
                   "scenario":CONTRACT["scenario"],"planner":CONTRACT["planner"],"traffic_mode":CONTRACT["traffic_mode"],
                   "max_speed_mps":CONTRACT["speed"],"safety_distance_m":CONTRACT["safety"],"common_traffic":0,**CONTRACT["parameters"]}
                rows.append(r)
                payload={"goal":[1,0],"scene_hash":scene,"collisions":0,"safety_violations":0,"path_length_m":33,"safe_success":1,"collision_free_success":1}
                for name,obj in [("result.json",payload),("complete.json",{"complete":True,"run_id":rid}),("configuration.json",{}),
                                 ("initial_state.json",{}),("provenance.json",{"source_sha256":{}}),
                                 ("trajectory.json",[{"robot":[1,0],"velocity":[0,0]}])]:
                    (run/name).write_text(json.dumps(obj))
                (run/"metrics.csv").write_text("run_id\n"+rid+"\n")
    write_rows(folder/"measurements.csv",rows)
    return identity,folder,rows

def test_ninety_unique_paired_conditions(archive):
    folder,c,df,inputs=analysis.validate(archive[0])
    assert len(df)==90 and df.run_id.nunique()==90 and len(inputs)==540

def test_reject_mismatched_scene(archive):
    identity,folder,rows=archive;rows[0]["scene_hash"]="wrong";write_rows(folder/"measurements.csv",rows)
    with pytest.raises(ValueError,match="초기 상태"):analysis.validate(identity)

def test_reject_missing_condition(archive):
    identity,folder,rows=archive;write_rows(folder/"measurements.csv",rows[:-1])
    with pytest.raises(ValueError,match="중복/누락"):analysis.validate(identity)

def test_reject_missing_completion_marker(archive):
    identity,folder,rows=archive;(batch.STORE/"runs"/rows[0]["run_id"]/"complete.json").unlink()
    with pytest.raises(ValueError,match="미완료"):analysis.validate(identity)

def test_reject_changed_engine(archive,monkeypatch):
    monkeypatch.setattr(analysis,"hashes",lambda:{"engine":"new"})
    with pytest.raises(ValueError,match="소스"):analysis.validate(archive[0])

def test_reject_unfinished_batch(archive):
    identity,folder,_=archive;(folder/"progress.json").write_text(json.dumps({"phase":"running","completed":89}))
    with pytest.raises(ValueError,match="완료"):analysis.validate(identity)

@pytest.mark.parametrize("identity",["../secret","not-a-batch","20261117T120000_abcdef01/../../x"])
def test_batch_path_is_not_arbitrary(identity):
    with pytest.raises(ValueError):batch.study_folder(identity)

def test_reject_different_speed(archive):
    identity,folder,rows=archive;rows[0]["max_speed_mps"]=2;write_rows(folder/"measurements.csv",rows)
    with pytest.raises(ValueError,match="통일 조건"):analysis.validate(identity)

def test_reject_false_completion_flag(archive):
    identity,folder,rows=archive
    (batch.STORE/"runs"/rows[0]["run_id"]/"complete.json").write_text(json.dumps({"complete":False,"run_id":rows[0]["run_id"]}))
    with pytest.raises(ValueError,match="미완료"):analysis.validate(identity)

def test_do_not_offer_unverified_batch(archive):
    with pytest.raises(ValueError,match="완료된 배치"):batch.active_status(archive[0])
