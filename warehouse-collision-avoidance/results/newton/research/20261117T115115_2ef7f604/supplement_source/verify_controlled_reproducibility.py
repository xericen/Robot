"""Repeat the physical encounter, excluding wall-clock measurements from equality checks."""
import argparse
import contextlib
import io
import json
from newton_results import ROOT
from newton_warehouse import run


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--frames",type=int,default=600)
    args=parser.parse_args()
    if not 1<=args.frames<=10800:
        parser.error("프레임 범위는1..10800입니다.")
    records=[]
    for encounter in ("head_on","crossing","narrow_passing"):
        for algorithm in ("naive","vo","orca"):
            pair=[]
            for _ in range(2):
                with contextlib.redirect_stdout(io.StringIO()):
                    r=run(algorithm_name=algorithm,scenario_name="crowded",agent_count=4,seed=42,
                          frames=args.frames,quiet=True,persist=False,trace_stride=args.frames,
                          encounter_mode=encounter,population_mode="workers")
                pair.append({key:r[key] for key in (
                    "scene_hash","status","sim_time_s","path_length_m","collisions","safety_violations",
                    "static_safety_violations","min_separation_m","collision_free_success","safe_success")})
            differences={key:[pair[0][key],pair[1][key]] for key in pair[0] if pair[0][key]!=pair[1][key]}
            records.append({"encounter":encounter,"algorithm":algorithm,"equal":not differences,
                            "differences":differences,"measured_pair":pair})
            print(f'{len(records)}/9 {encounter} {algorithm}: equal={not differences}',flush=True)
    folder=ROOT/"validation"/"controlled";folder.mkdir(parents=True,exist_ok=True)
    (folder/"reproducibility.json").write_text(json.dumps({"frames":args.frames,"seed":42,
        "pairs":records,"all_equal":all(r["equal"] for r in records)},ensure_ascii=False,indent=2))
    return 0 if all(r["equal"] for r in records) else 1


if __name__=="__main__":
    raise SystemExit(main())
