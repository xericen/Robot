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
    if df.duplicated(["map", "scenario", "algorithm", "seed", "agent_count"]).any():
        raise ValueError("중복 실험 키가 있습니다.")
    # Agent-count-only plots require a fixed map/planner/traffic/parameter configuration.
    from newton_results import PARAMETERS
    for key in ("map", "planner", "traffic_mode", "frame_limit", "max_speed_mps",
                "safety_distance_m", *PARAMETERS):
        if df[key].nunique(dropna=False) != 1:
            raise ValueError(f"혼합 조건을 분리한 후 시각화하세요: {key}")
    for key in ("encounter_mode","population_mode"):
        if key in df and df[key].nunique(dropna=False) != 1:
            raise ValueError(f"서로 다른 실험 집단을 분리하세요: {key}")
    df["risk_events"] = df["collision_count"] + df["safety_violation_count"]
    if "static_safety_violation_count" in df:
        df["risk_events"] += df["static_safety_violation_count"].fillna(0)
    df["success_pct"] = df["success"] * 100
    df.loc[df["success"] != 1, "arrival_time_s"] = float("nan")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    summaries = []
    specifications = list(PLOTS)
    if "safe_success" in df:
        df["safe_success_pct"] = df["safe_success"]*100
        df["collision_free_pct"] = df["collision_free_success"]*100
        specifications += [
            ("safe_success_pct","안전거리 준수 도달률","도달률 (%)","06_safe_success.png"),
            ("collision_free_pct","무충돌 도달률","도달률 (%)","07_collision_free.png"),
            ("min_separation_m","최소 표면 이격거리","거리 (m)","08_minimum_clearance.png")]
    for key, title, ylabel, filename in specifications:
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
    if all(key in df for key in ("neighbor_checks","candidate_checks","constraints","algo_steps")):
        for key in ("neighbor_checks","candidate_checks","constraints"):
            df[key+"_per_step"] = df[key]/df["algo_steps"]
        fig,axes=plt.subplots(2,2,figsize=(10,7))
        panels=[("algo_time_avg_ms","회피 계산시간 (ms/프레임)"),
                ("neighbor_checks_per_step","이웃 검사 (회/프레임)"),
                ("candidate_checks_per_step","후보·제약 검사 (회/프레임)"),
                ("constraints_per_step","생성 제약 (개/프레임)")]
        for ax,(key,title) in zip(axes.flat,panels):
            for algorithm,color in COLORS.items():
                g=df[df.algorithm==algorithm].groupby("agent_count")[key].agg(["mean","std"])
                ax.errorbar(g.index,g["mean"],yerr=g["std"].fillna(0),label=LABELS[algorithm],
                            color=color,marker="o",capsize=3)
            ax.set(title=title,xlabel="이동 에이전트 수 (R0 제외)")
            if key=="algo_time_avg_ms": ax.set_yscale("log")
            ax.grid(color="#d1d5db",alpha=.65)
        axes[0,0].legend(fontsize=8)
        fig.suptitle("입력 크기에 따른 계산량과 실행시간")
        fig.tight_layout()
        fig.savefig(output/"09_complexity.png",dpi=200);plt.close(fig)
        print(output/"09_complexity.png")
    (output / "summary.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2))
    print(pd.DataFrame(summaries).to_string(index=False))
    return summaries


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=ROOT / "sweep_agent_count.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "figs")
    args = parser.parse_args()
    plot(args.csv, args.output)
