"""Newton-only result schema and atomic CSV persistence (no Pygame writes)."""
from __future__ import annotations
import csv
import math
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parent / "results" / "newton"
PARAMETERS = {
    "orca_neighbor_dist_m": 0.0,  # 0 = unlimited, matching the original all-agent scan
    "orca_max_neighbors": 0,
    "orca_horizon_s": 3.0,
    "time_step_s": 1.0 / 30,
    "vo_horizon_s": 3.0,
    "vo_candidates": 74,
    "naive_stop_margin_m": 0.0,
    "naive_influence_m": 1.2,
}
CORE_FIELDS = [
    "map", "algorithm", "scenario", "seed", "agent_count", "success", "timeout",
    "arrival_time_s", "path_length_m", "collision_count", "safety_violation_count",
    "replan_count", "wall_time_s", "algo_time_avg_ms", "algo_time_max_ms", "algo_steps",
    "worker_count", "other_robot_count", "planner", "traffic_mode", "common_traffic",
    "frame_limit", "observed_time_s", "safety_distance_m", "max_speed_mps",
    *PARAMETERS, "newton_version", "warp_version",
]

EXTRA_FIELDS = ["run_id", "encounter_mode", "population_mode", "scene_hash",
                "collision_free_success", "safe_success", "min_separation_m",
                "min_dynamic_clearance_m", "min_static_clearance_m", "static_safety_violation_count",
                "neighbor_checks", "candidate_checks", "constraints", "orca_audit_frames"]
EXTRA_FIELDS += ["algo_time_median_ms","algo_time_p95_ms","robot_stop_time_s","longest_stop_s",
                 "constraint_evaluations","lp_pair_evaluations","lp_iterations","candidate_velocity_checks",
                 "constraint_violation_count","constraint_violation_frames"]
FIELDS = CORE_FIELDS + EXTRA_FIELDS


def settings(overrides=None):
    values = {**PARAMETERS, **(overrides or {})}
    if set(values) != set(PARAMETERS):
        raise ValueError("알 수 없는 회피 파라미터입니다.")
    values = {k: float(v) for k, v in values.items()}
    if not all(math.isfinite(v) for v in values.values()):
        raise ValueError("파라미터는 유한한 수여야 합니다.")
    for key in ("orca_max_neighbors", "vo_candidates"):
        if values[key] != int(values[key]):
            raise ValueError("이웃 수와 후보 수는 정수여야 합니다.")
        values[key] = int(values[key])
    if not (0 <= values["orca_neighbor_dist_m"] <= 1000 and 0 <= values["orca_max_neighbors"] <= 120
            and .001 <= values["time_step_s"] <= .1
            and .01 <= values["orca_horizon_s"] <= 30 and .01 <= values["vo_horizon_s"] <= 30
            and 2 <= values["vo_candidates"] <= 1000
            and 0 <= values["naive_stop_margin_m"] <= 5 and .01 <= values["naive_influence_m"] <= 10):
        raise ValueError("회피 파라미터 범위를 확인하세요.")
    return values


def result_row(result):
    p = settings(result.get("parameters"))
    row = dict(zip(CORE_FIELDS, [
        result["mapId"], result["algorithm"], result["scenario"], result["seed"],
        result["agent_count"], int(result["status"] == "success"), int(result["status"] == "timeout"),
        result["sim_time_s"] if result["status"] == "success" else None,
        result["path_length_m"], result["collisions"], result["safety_violations"],
        result.get("replanning_count", 0), result["wall_time_s"],
        result["algo_time_avg_ms"], result["algo_time_max_ms"], result["algo_steps"],
        result["worker_count"], result["other_robot_count"], result["planner"],
        result["traffic_mode"], int(result["common_traffic"]), result["frame_limit"],
        result["sim_time_s"], result["safety_distance_m"], result["robot_speed_mps"],
        *p.values(), result["newton_version"], result["warp_version"],
    ], strict=True))
    row.update({key: result.get(key) for key in EXTRA_FIELDS})
    row["static_safety_violation_count"] = result.get("static_safety_violations")
    row["orca_audit_frames"] = len(result.get("diagnostic_events", []))
    return row


def write_rows(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="",
                                         dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            writer = csv.DictWriter(output, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def save_result(result):
    from experiment_archive import archive_result
    run_id = archive_result(result, ROOT)
    result["run_id"] = run_id
    row = result_row(result)
    # The four components originate from validated engine enums/integers.
    components = [str(row[k]).lower() for k in ("map", "algorithm", "scenario", "seed")]
    if any(not c.replace("_", "").isalnum() for c in components):
        raise ValueError("잘못된 결과 파일명입니다.")
    stem = "_".join(components)
    if result.get("encounter_mode", "baseline") != "baseline" or result.get("population_mode", "legacy") != "legacy":
        stem += f'_{result["encounter_mode"]}_{result["population_mode"]}_n{result["agent_count"]}'
    path = ROOT / (stem + ".csv")
    if path.exists():
        import hashlib
        raw=path.read_bytes()
        snapshot=ROOT/"legacy_snapshots"/(hashlib.sha256(raw).hexdigest()+".csv")
        snapshot.parent.mkdir(parents=True,exist_ok=True)
        try:
            with snapshot.open("xb") as f:
                f.write(raw)
        except FileExistsError:
            pass
    archived = ROOT / "runs" / run_id / "metrics.csv"
    # Publish the first compatibility filename atomically; subsequent runs stay append-only.
    # Never replace a user's original CSV, including during concurrent live sessions.
    try:
        os.link(archived, path)
    except FileExistsError:
        return archived
    return path


def load_results(history=False):
    rows = []
    if not ROOT.exists():
        return rows
    paths = sorted(ROOT.glob("map*_*.csv"))
    if history:
        paths += sorted(ROOT.glob("runs/*/metrics.csv"))
        paths += sorted(ROOT.glob("legacy_snapshots/*.csv"))
    seen = set()
    for path in paths:
        if path.parent.parent.name == "runs" and not (path.parent/"complete.json").exists():
            continue
        with path.open(encoding="utf-8", newline="") as source:
            for raw in csv.DictReader(source):
                row = {}
                for key, value in raw.items():
                    if value == "":
                        row[key] = None
                    else:
                        try:
                            row[key] = float(value)
                        except ValueError:
                            row[key] = value
                run_id = row.get("run_id")
                if history and not run_id:
                    import hashlib, json
                    run_id = "legacy_"+hashlib.sha256(json.dumps({k:row.get(k) for k in CORE_FIELDS},sort_keys=True).encode()).hexdigest()[:16]
                    row["run_id"] = run_id
                if run_id and run_id in seen:
                    continue
                if run_id:
                    seen.add(run_id)
                rows.append(row)
    return rows
