"""Controlled Newton study: isolated population cohorts, seeded encounters, immutable batches."""
from __future__ import annotations
import argparse
import csv
import fcntl
import signal
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid
import pandas as pd
from newton_results import ROOT, write_rows, result_row
from newton_experiments import execute

ALGORITHMS=("naive","vo","orca")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", type=Path, help="동일 배치의 완료 행을 유지하고 나머지만 실행")
    parser.add_argument("--repeats",type=int,default=10)
    parser.add_argument("--counts",default="2,4,8,16")
    parser.add_argument("--populations",default="workers,mixed")
    parser.add_argument("--encounters",default="crossing")
    parser.add_argument("--maps",default="map1")
    parser.add_argument("--frames",type=int,default=5400)
    parser.add_argument("--seed",type=int,default=42)
    args=parser.parse_args()
    if args.resume:
        folder=args.resume.resolve()
        if folder.parent != (ROOT/"studies").resolve():
            parser.error("현재 프로젝트의 studies 배치만 재개할 수 있습니다.")
        saved=json.loads((folder/"configuration.json").read_text())
        args=argparse.Namespace(**{**saved,"resume":folder})
    from encounter_scenarios import ENCOUNTERS
    from warehouse_maps import map_catalog
    counts=[int(x) for x in args.counts.split(",")]
    populations=args.populations.split(",");encounters=args.encounters.split(",");maps=args.maps.split(",")
    if not (all(len(items)==len(set(items)) for items in (counts,populations,encounters,maps))
            and 0<=args.seed and args.seed+args.repeats-1<=999999
            and 2<=args.repeats<=100 and 1<=args.frames<=10800 and all(1<=n<=40 for n in counts)
            and set(populations)<={"workers","mixed"} and set(encounters)<=set(ENCOUNTERS)-{"baseline"}
            and set(maps)<={m["mapId"] for m in map_catalog()}):
        parser.error("실험 구성 범위를 확인하세요.")
    if "narrow_passing" in encounters and maps!=["map1"]:
        parser.error("좁은 교행 통제 실험은 Map1을 별도 배치로 실행하세요.")
    batch_id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+"_"+uuid.uuid4().hex[:8]
    if args.resume:
        folder=args.resume
        batch_id=folder.name
    else:
        folder=ROOT/"studies"/batch_id;folder.mkdir(parents=True,exist_ok=False)
        (folder/"configuration.json").write_text(json.dumps(vars(args),ensure_ascii=False,indent=2))
    lock=(folder/".lock").open("a")
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        parser.error("이 배치는 다른 프로세스에서 실행 중입니다.")
    def interrupted(signum, frame):
        raise KeyboardInterrupt("실험 중단 신호")
    previous_handler=signal.signal(signal.SIGTERM,interrupted)
    rows=list(csv.DictReader((folder/"measurements.csv").open())) if (folder/"measurements.csv").exists() else []
    def key(row):
        return (row["map"],row["encounter_mode"],row["population_mode"],int(row["agent_count"]),int(row["seed"]),row["algorithm"].lower())
    completed={key(row):row for row in rows}
    total=len(counts)*len(populations)*len(encounters)*len(maps)*len(ALGORITHMS)*args.repeats
    status={"batch_id":batch_id,"total":total,"completed":len(rows),"phase":"running"}
    def progress():
        (folder/"progress.json").write_text(json.dumps(status,ensure_ascii=False,indent=2))
    progress()
    try:
        for map_id in maps:
            for encounter in encounters:
                for population in populations:
                    for count in counts:
                        for seed in range(args.seed,args.seed+args.repeats):
                            fingerprints=[]
                            for algorithm in ALGORITHMS:
                                identity=(map_id,encounter,population,count,seed,algorithm)
                                if identity in completed:
                                    fingerprints.append(completed[identity]["scene_hash"])
                                    continue
                                row=execute(algorithm_name=algorithm,scenario_name="crowded",agent_count=count,
                                            map_id=map_id,seed=seed,planner="astar",traffic_mode="dynamic",
                                            encounter_mode=encounter,population_mode=population,frames=args.frames)
                                fingerprints.append(row["scene_hash"])
                                rows.append(row)
                                write_rows(folder/"measurements.csv",rows)
                                status["completed"]=len(rows);progress()
                                print(f'{len(rows)}/{total} {map_id} {encounter} {population} n={count} seed={seed}',flush=True)
                            if len(set(fingerprints))!=1:
                                raise RuntimeError("알고리즘 사이 초기 상태 해시가 다릅니다.")
        df=pd.DataFrame(rows)
        for column in ("agent_count","arrival_time_s","path_length_m","collision_count","safety_violation_count",
                       "success","collision_free_success","safe_success","min_separation_m","algo_time_avg_ms",
                       "neighbor_checks","candidate_checks","constraints"):
            df[column]=pd.to_numeric(df[column],errors="coerce")
        group=df.groupby(["map","encounter_mode","population_mode","agent_count","algorithm"])
        summary=group[["arrival_time_s","path_length_m","collision_count","safety_violation_count",
                       "success","collision_free_success","safe_success","min_separation_m",
                       "algo_time_avg_ms","neighbor_checks","candidate_checks","constraints"]].agg(["mean","std","count"])
        summary.to_csv(folder/"summary.csv")
        print(summary.to_string())
        status["phase"]="complete";progress()
        (ROOT/"latest_controlled_study.json").write_text(json.dumps({"batch_id":batch_id,"folder":str(folder)}))
        print("STUDY_FOLDER="+str(folder),flush=True)
    except BaseException as error:
        status.update(phase="interrupted" if isinstance(error,KeyboardInterrupt) else "error",error=str(error));progress();raise
    finally:
        signal.signal(signal.SIGTERM,previous_handler)
        lock.close()


if __name__=="__main__":
    main()
