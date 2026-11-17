"""Canonical six-map experiment contract, immutable serial execution and batch readers."""
from __future__ import annotations
import argparse,csv,hashlib,json,os,re,signal,uuid
from datetime import datetime,timezone
from pathlib import Path
from newton_results import PARAMETERS,write_rows,result_row
ROOT=Path(__file__).resolve().parent
STORE=ROOT/"results/newton"
PATTERN=r"[0-9]{8}T[0-9]{6}_[a-f0-9]{8}"
CONTRACT={"schema":1,"scenario":"medium","agent_count":4,"population_mode":"workers",
 "encounter_mode":"crossing","planner":"astar","traffic_mode":"dynamic","common_traffic":False,
 "frames":5400,"safety":.35,"speed":1.2,"parameters":PARAMETERS,
 "maps":[f"map{i}" for i in range(1,7)],"algorithms":["naive","vo","orca"],"seeds":[42,43,44,45,46],
 "execution":"serial CPU","scope":"six layouts, one population n=4 and Crossing; no density/other-encounter inference"}
def atomic(path,value):
    temp=path.with_suffix(".tmp");temp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False));os.replace(temp,path)
def hashes():
    names=["newton_warehouse.py","newton_safety.py","encounter_scenarios.py","newton_results.py",
           "experiment_archive.py","warehouse_maps.py","warehouse_maps.json","experiments/scenarios.py",
           "simulator/agents.py","simulator/physics.py"]
    names += [str(p.relative_to(ROOT)) for p in sorted((ROOT/"algorithms").glob("*.py"))]
    return {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}
def study_folder(batch_id):
    if not re.fullmatch(PATTERN,batch_id):raise ValueError("잘못된 통일 배치 ID입니다.")
    folder=STORE/"studies"/batch_id
    if not (folder/"configuration.json").exists():raise ValueError("통일 배치가 없습니다.")
    if json.loads((folder/"configuration.json").read_text()).get("kind")!="unified-six-map":raise ValueError("통일 배치가 아닙니다.")
    return folder
def read_rows(batch_id):
    folder=study_folder(batch_id);rows=[]
    if not (folder/"measurements.csv").exists():return rows
    for item in csv.DictReader((folder/"measurements.csv").open()):
        row={}
        for key,value in item.items():
            if not value or value=="N/A":row[key]=None
            else:
                try:row[key]=float(value)
                except ValueError:row[key]=value
        row["source_batch_id"]=batch_id;rows.append(row)
    return rows
def active_status(batch_id=""):
    available=[]
    for p in (STORE/"studies").glob("*/configuration.json"):
        try:
            c=json.loads(p.read_text());state=json.loads(p.with_name("progress.json").read_text())
            if c.get("kind")=="unified-six-map" and state.get("phase")=="complete" and (STORE/"research"/p.parent.name/"verification.json").exists() and json.loads((STORE/"research"/p.parent.name/"verification.json").read_text()).get("passed") is True:available.append(p.parent.name)
        except (OSError,ValueError):pass
    if not batch_id:
        path=STORE/"active_batch.json"
        batch_id=json.loads(path.read_text()).get("batch_id","") if path.exists() else ""
    if not batch_id:return {"status":"missing","available":sorted(available)}
    if batch_id not in available:raise ValueError("실험·분석·검증이 완료된 배치만 선택할 수 있습니다.")
    folder=study_folder(batch_id)
    config=json.loads((folder/"configuration.json").read_text())
    state=json.loads((folder/"progress.json").read_text())
    return {"id":batch_id,"status":state["phase"],"available":sorted(available),"config":config["contract"],
            "completed":state["completed"],"total":state["total"],"engine_match":config["engine_sha256"]==hashes(),"rows":read_rows(batch_id)}
def main():
    parser=argparse.ArgumentParser();parser.add_argument("--resume");args=parser.parse_args()
    import fcntl,contextlib,io
    from newton_warehouse import run
    current=hashes()
    if args.resume:
        folder=study_folder(args.resume);config=json.loads((folder/"configuration.json").read_text())
        if config["engine_sha256"]!=current:raise RuntimeError("물리/알고리즘 소스가 달라 같은 배치를 재개할 수 없습니다.")
    else:
        batch_id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")+"_"+uuid.uuid4().hex[:8]
        folder=STORE/"studies"/batch_id;folder.mkdir(parents=True,exist_ok=False)
        config={"kind":"unified-six-map","contract":CONTRACT,"engine_sha256":current,"created_at":datetime.now(timezone.utc).isoformat()}
        atomic(folder/"configuration.json",config)
        # Prior archives are retained; never pool old-condition or unverified timing contexts.
        atomic(folder/"reuse_policy.json",{"reused":0,"reason":"Historical Map1/crowded or baseline runs are not the medium/Crossing/five-seed six-map contract. Live timing context is not pooled with the serial study."})
    lock=(folder/".lock").open("a");fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt()))
    rows=read_rows(folder.name)
    for r in rows:r.pop("source_batch_id",None)
    key=lambda r:(r["map"],int(r["seed"]),r["algorithm"].lower())
    done={key(r) for r in rows}
    if len(done)!=len(rows):raise ValueError("배치에 중복 조건이 있습니다.")
    state={"batch_id":folder.name,"total":90,"completed":len(rows),"phase":"running"}
    atomic(folder/"progress.json",state)
    print("BATCH_ID="+folder.name,flush=True)
    try:
        c=config["contract"]
        for map_id in c["maps"]:
            for seed in c["seeds"]:
                fingerprints=[]
                for algorithm in c["algorithms"]:
                    identity=(map_id,seed,algorithm)
                    if identity in done:
                        fingerprints.append(next(r["scene_hash"] for r in rows if key(r)==identity));continue
                    if hashes()!=config["engine_sha256"]:raise RuntimeError("실험 중 물리 소스가 변경되었습니다.")
                    with contextlib.redirect_stdout(io.StringIO()):
                        result=run(algorithm_name=algorithm,scenario_name=c["scenario"],agent_count=c["agent_count"],
                                   map_id=map_id,seed=seed,planner=c["planner"],traffic_mode=c["traffic_mode"],
                                   encounter_mode=c["encounter_mode"],population_mode=c["population_mode"],
                                   safety_distance=c["safety"],robot_speed=c["speed"],parameters=c["parameters"],
                                   frames=c["frames"],common_traffic=c["common_traffic"],quiet=True,trace_stride=30)
                    row=result_row(result);rows.append(row);done.add(identity);fingerprints.append(row["scene_hash"])
                    write_rows(folder/"measurements.csv",rows);state["completed"]=len(rows);atomic(folder/"progress.json",state)
                    print(f'{len(rows)}/90 {map_id} seed={seed} {algorithm} success={row["success"]} collisions={row["collision_count"]}',flush=True)
                if len(set(fingerprints))!=1:raise RuntimeError("세 알고리즘의 실제 초기 상태가 다릅니다.")
        state["phase"]="complete";atomic(folder/"progress.json",state)
        print("COMPLETE="+folder.name,flush=True)
    except BaseException as error:
        state.update(phase="interrupted" if isinstance(error,KeyboardInterrupt) else "error",error=str(error))
        atomic(folder/"progress.json",state);raise
    finally:lock.close()
if __name__=="__main__":main()
