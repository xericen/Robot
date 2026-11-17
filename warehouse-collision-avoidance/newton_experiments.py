"""Newton CPU experiments. Run with the project .venv Python."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import pandas as pd
from newton_results import ROOT, result_row, write_rows
from experiments.scenarios import PRESETS

ALGORITHMS = ("naive", "vo", "orca")
SEEDS = (42, 43, 44, 45, 46)
# hard means 7 workers + 2 other AMRs. R0 is excluded from input size.
POPULATIONS = {**{name: sum(counts) for name, counts in PRESETS.items()}, "crowded": 16}


def execute(**kwargs):
    import contextlib
    import io
    from newton_warehouse import run
    with contextlib.redirect_stdout(io.StringIO()):
        result = run(**kwargs, quiet=True, trace_stride=5400)
    row = result_row(result)
    print(f'{row["scenario"]} {row["algorithm"]} seed={row["seed"]} '
          f'avg={row["algo_time_avg_ms"]:.6f}ms max={row["algo_time_max_ms"]:.6f}ms '
          f'steps={row["algo_steps"]} success={row["success"]}', flush=True)
    return row


def summary(rows):
    df = pd.DataFrame(rows)
    print("\n조건별 평균 / 표본 표준편차(ddof=1). 스윕은 시드 간 집계이며 도달 시간은 성공 실행만 포함합니다.")
    keys = ["arrival_time_s", "path_length_m", "collision_count", "safety_violation_count",
            "success", "algo_time_avg_ms", "algo_time_max_ms"]
    print(df.groupby(["map", "scenario", "agent_count", "algorithm"], sort=False)[keys]
          .agg(["count", "mean", "std"]).to_string())
    return df


def sweep(frames=5400):
    rows = []
    for scenario, count in POPULATIONS.items():
        for algorithm in ALGORITHMS:
            for seed in SEEDS:
                row = execute(algorithm_name=algorithm, scenario_name=scenario, agent_count=count,
                              seed=seed, map_id="map1", planner="astar", traffic_mode="dynamic",
                              frames=frames)
                rows.append(row)
                write_rows(ROOT / "sweep_agent_count.csv", rows)
                print(f'{len(rows)}/60', flush=True)
    summary(rows)


def compare(frames=5400, scenario="medium", seed=42):
    rows = []
    for index in range(1, 7):
        for algorithm in ALGORITHMS:
            rows.append(execute(algorithm_name=algorithm, scenario_name=scenario,
                                agent_count=POPULATIONS[scenario], seed=seed,
                                map_id=f"map{index}", planner="astar", traffic_mode="dynamic",
                                common_traffic=True, frames=frames))
            print(f'{len(rows)}/18', flush=True)
    summary(rows)


def reproducibility(frames=5400):
    checks, rows = [], []
    for algorithm in ALGORITHMS:
        for seed in SEEDS:
            kwargs = dict(algorithm_name=algorithm, scenario_name="medium", agent_count=4,
                          seed=seed, map_id="map1", planner="astar", traffic_mode="dynamic",
                          frames=frames, persist=False)
            first, second = execute(**kwargs), execute(**kwargs)
            keys = ("arrival_time_s", "path_length_m", "collision_count")
            differences = {key: [first[key], second[key]] for key in keys if first[key] != second[key]}
            checks.append({"algorithm": algorithm, "seed": seed, "equal": not differences,
                           "differences": differences})
            rows.append(first)
            print(f'재현성 {len(checks)}/15: {checks[-1]}', flush=True)
    ROOT.mkdir(parents=True, exist_ok=True)
    report = {"frames": frames, "checks": checks,
              "diagnosis": {
                  "physics": "newton_warehouse.run: CPU XPBD, 고정 frame_dt / 2 서브스텝. 병렬 리덕션/접촉 순서와 라이브러리 버전 변경은 비결정성 후보.",
                  "spawn": "experiments.scenarios 및 warehouse_maps.apply_map: np.random.default_rng(seed), 시뮬레이션 시작 전 스폰. 벽시계 스폰 없음.",
                  "float_order": "algorithms.orca: 입력 이웃 순서대로 제약 처리. 현재 기본값은 정렬 없이 고정 순서. CPU/NumPy/Warp 버전이 바뀌면 연산 순서 차이 가능.",
                  "excluded": "wall_time/algo_time/planning_time은 실측 실행시간이므로 재현성 동일 비교에서 제외. RRT는 벽시계 제한이 있으므로 이 검증은 A*로 고정.",
              }}
    (ROOT / "reproducibility.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    df = summary(rows)
    print("\n5개 시드 성공률 및 충돌 분산")
    print(df.groupby("algorithm").agg(success_rate=("success", "mean"),
                                      success_variance=("success", "var"),
                                      collision_variance=("collision_count", "var")).to_string())
    return all(check["equal"] for check in checks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("sweep", "compare", "reproducibility"))
    parser.add_argument("--frames", type=int, default=5400)
    args = parser.parse_args()
    if not 1 <= args.frames <= 10800:
        parser.error("frames must be 1..10800")
    if args.mode == "reproducibility":
        return 0 if reproducibility(args.frames) else 1
    (sweep if args.mode == "sweep" else compare)(args.frames)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
