from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


COLORS = {"Naive": "#f59e0b", "VO": "#2563eb", "ORCA": "#0f766e"}
MARKERS = {"Naive": "o", "VO": "s", "ORCA": "^"}
LINESTYLES = {"Naive": "-", "VO": "--", "ORCA": ":"}


def _line_chart(frame: pd.DataFrame, metric: str, ylabel: str, target: Path,
                successful_only: bool = False) -> None:
    data = frame[frame["success"]] if successful_only else frame
    grouped = data.groupby(["algorithm", "agent_count"])[metric].agg(["mean", "std"]).reset_index()
    figure, axis = plt.subplots(figsize=(7.2, 4.5))
    for algorithm, group in grouped.groupby("algorithm"):
        group = group.sort_values("agent_count")
        axis.errorbar(group["agent_count"], group["mean"], yerr=group["std"].fillna(0),
                      marker=MARKERS.get(algorithm, "o"), linestyle=LINESTYLES.get(algorithm, "-"),
                      capsize=3, label=algorithm, color=COLORS.get(algorithm))
    axis.set_xlabel("Agent count (n)")
    axis.set_ylabel(ylabel)
    axis.grid(alpha=0.25)
    if metric == "success":
        axis.set_ylim(-0.03, 1.05)
    axis.legend()
    figure.tight_layout()
    figure.savefig(target, dpi=160)
    plt.close(figure)


def create_figures(results_csv: Path, trajectories_csv: Path, output: Path) -> list[Path]:
    frame = pd.read_csv(results_csv)
    trajectories = pd.read_csv(trajectories_csv)
    output.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    charts = [
        ("goal_reaching_time_s", "Mean goal reaching time (s)", "01_goal_time.png", True),
        ("collision_count", "Mean collision entries", "02_collisions.png", False),
        ("success", "Success rate", "03_success_rate.png", False),
        ("algorithm_time_mean_ms", "Mean algorithm time per step (ms)", "04_runtime.png", False),
    ]
    for metric, label, filename, success_only in charts:
        target = output / filename
        _line_chart(frame, metric, label, target, success_only)
        created.append(target)

    target = output / "05_path_length.png"
    pivot = frame.groupby("algorithm")["path_length_m"].agg(["mean", "std"])
    axis = pivot["mean"].plot(kind="bar", yerr=pivot["std"].fillna(0), color=[COLORS.get(x) for x in pivot.index],
                              figsize=(6.5, 4.2), capsize=4)
    axis.set_ylabel("Path length (m)")
    axis.set_xlabel("Algorithm")
    axis.figure.tight_layout()
    axis.figure.savefig(target, dpi=160)
    plt.close(axis.figure)
    created.append(target)

    target = output / "06_trajectories.png"
    first = trajectories.sort_values(["agent_count", "repeat"]).groupby("algorithm", as_index=False).first()
    figure, axis = plt.subplots(figsize=(7.2, 4.5))
    for _, selector in first.iterrows():
        subset = trajectories[
            (trajectories["algorithm"] == selector["algorithm"]) &
            (trajectories["agent_count"] == selector["agent_count"]) &
            (trajectories["repeat"] == selector["repeat"])
        ]
        axis.plot(subset["x_m"], subset["y_m"], label=selector["algorithm"], color=COLORS.get(selector["algorithm"]))
    axis.set_xlabel("x (m)")
    axis.set_ylabel("y (m)")
    axis.set_aspect("equal", adjustable="box")
    axis.grid(alpha=0.25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(target, dpi=160)
    plt.close(figure)
    created.append(target)
    return created


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=Path("results/csv/experiment_results.csv"))
    parser.add_argument("--trajectories", type=Path, default=Path("results/csv/trajectories.csv"))
    parser.add_argument("--output", type=Path, default=Path("results/figures"))
    args = parser.parse_args()
    for path in create_figures(args.results, args.trajectories, args.output):
        print(path)
