from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from simulator.environment import WarehouseSimulation


def run_experiments(scenarios: list[str], counts: list[int], algorithms: list[str], repeats: int,
                    base_seed: int, safety_distance: float, cooperative: bool,
                    output_directory: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict] = []
    trajectories: list[dict] = []
    for scenario in scenarios:
        for count in counts:
            for repeat in range(repeats):
                seed = base_seed + repeat
                for algorithm in algorithms:
                    simulation = WarehouseSimulation(
                        scenario_name=scenario, algorithm_name=algorithm, agent_count=count,
                        seed=seed, safety_distance=safety_distance, cooperative=cooperative,
                    )
                    result = simulation.run()
                    result["repeat"] = repeat
                    rows.append(result)
                    for step, position in enumerate(simulation.robot.trajectory):
                        trajectories.append({
                            "scenario": scenario, "agent_count": count, "algorithm": result["algorithm"],
                            "seed": seed, "repeat": repeat, "step": step,
                            "x_m": float(position[0]), "y_m": float(position[1]),
                        })
                    print(f"{scenario:12s} n={count:3d} repeat={repeat + 1:2d} {result['algorithm']:5s} "
                          f"success={result['success']} collisions={result['collision_count']}")
    output_directory.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    trajectory_frame = pd.DataFrame(trajectories)
    frame.to_csv(output_directory / "experiment_results.csv", index=False)
    trajectory_frame.to_csv(output_directory / "trajectories.csv", index=False)
    return frame, trajectory_frame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run reproducible warehouse collision-avoidance experiments.")
    parser.add_argument("--scenarios", nargs="+", default=["warehouse"])
    parser.add_argument("--counts", nargs="+", type=int, default=[5, 10, 20, 40, 80])
    parser.add_argument("--algorithms", nargs="+", default=["naive", "vo", "orca"])
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--safety-distance", type=float, default=0.35)
    parser.add_argument("--cooperative", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("results/csv"))
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    run_experiments(arguments.scenarios, arguments.counts, arguments.algorithms, arguments.repeats,
                    arguments.seed, arguments.safety_distance, arguments.cooperative, arguments.output)
