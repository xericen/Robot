"""Plot only measured Newton CSV data, in Korean, 200dpi."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
from matplotlib import font_manager
import matplotlib.pyplot as plt
import pandas as pd
from newton_results import ROOT

FONT = Path(__file__).parent / "fonts" / "NotoSansKR.ttf"
COLORS = {"Naive": "#d97706", "VO": "#2563eb", "ORCA": "#0f766e"}
LABELS = {"Naive": "단순 반응형 (Naive)", "VO": "속도 장애물 (VO)", "ORCA": "최적 상호 회피 (ORCA)"}
PLOTS = [
    ("arrival_time_s", "목적지 도달 시간", "시간 (초)", "01_arrival_time.png"),
    ("path_length_m", "로봇 이동 거리", "거리 (m)", "02_path_length.png"),
    ("risk_events", "충돌 및 안전거리 위반", "사건 수 (회)", "03_collision_safety.png"),
    ("success_pct", "목적지 도달 성공률", "성공률 (%)", "04_success_rate.png"),
    ("algo_time_avg_ms", "프레임당 평균 회피 계산시간", "계산시간 (ms, 로그 척도)", "05_algorithm_time.png"),
]


def plot(source=ROOT / "sweep_agent_count.csv", output=ROOT / "figs"):
    if not FONT.exists():
        raise FileNotFoundError(f"Noto Sans KR 폰트를 설치하세요: {FONT} (README 참조)")
    font_manager.fontManager.addfont(str(FONT))
    plt.rcParams.update({"font.family": font_manager.FontProperties(fname=FONT).get_name(),
                         "axes.unicode_minus": False, "font.size": 10})
    df = pd.read_csv(source)
    if df.duplicated(["map", "scenario", "algorithm", "seed"]).any():
        raise ValueError("중복 실험 키가 있습니다.")
    # Agent-count-only plots require a fixed map/planner/traffic/parameter configuration.
    from newton_results import PARAMETERS
    for key in ("map", "planner", "traffic_mode", "frame_limit", "max_speed_mps",
                "safety_distance_m", *PARAMETERS):
        if df[key].nunique(dropna=False) != 1:
            raise ValueError(f"혼합 조건을 분리한 후 시각화하세요: {key}")
    df["risk_events"] = df["collision_count"] + df["safety_violation_count"]
    df["success_pct"] = df["success"] * 100
    df.loc[df["success"] != 1, "arrival_time_s"] = float("nan")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    summaries = []
    for key, title, ylabel, filename in PLOTS:
        fig, ax = plt.subplots(figsize=(7.4, 4.5))
        for algorithm, color in COLORS.items():
            group = df[df.algorithm == algorithm].groupby("agent_count")[key].agg(["count", "mean", "std"])
            group["std"] = group["std"].fillna(0)
            ax.errorbar(group.index, group["mean"], yerr=group["std"], label=LABELS[algorithm],
                        color=color, marker="o", linewidth=1.8, capsize=4)
            for count, row in group.iterrows():
                summaries.append({"metric": key, "algorithm": algorithm, "agent_count": int(count),
                                  "runs": int(row["count"]), "mean": None if pd.isna(row["mean"]) else float(row["mean"]),
                                  "std": float(row["std"])})
        ax.set(title=title, xlabel="이동 에이전트 수 (R0 제외)", ylabel=ylabel)
        ax.set_xticks(sorted(df.agent_count.unique()))
        if key == "algo_time_avg_ms":
            ax.set_yscale("log")
        ax.grid(color="#d1d5db", alpha=.65, linewidth=.6, which="both")
        ax.legend(frameon=False)
        fig.text(.01, .01, "오차막대: 시드 간 표본 표준편차 · 도달 시간: 성공 실행만 집계 · 결측값은 표시하지 않음", fontsize=8)
        fig.tight_layout(rect=(0, .04, 1, 1))
        fig.savefig(output / filename, dpi=200)
        plt.close(fig)
        print(output / filename)
    (output / "summary.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2))
    print(pd.DataFrame(summaries).to_string(index=False))
    return summaries


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=ROOT / "sweep_agent_count.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "figs")
    args = parser.parse_args()
    plot(args.csv, args.output)
