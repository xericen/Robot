"""Newton-backed warehouse simulation using the existing A*/Naive/VO/ORCA code.

The existing algorithms consume positions/velocities read from Newton and return
target planar velocities.  A shared force controller applies those targets to
Newton rigid bodies; no body position is advanced manually.
"""

from __future__ import annotations

import argparse
import json
import math
import time

import newton
import numpy as np
import warp as wp

from algorithms import create_algorithm
from algorithms.pathfinding import astar_path
from algorithms.planners import plan
from experiments.scenarios import SCENARIOS, Scenario, create_scenario
from simulator.agents import Agent, ControlledRobot
from warehouse_maps import shelf_geometry, get_map
from newton_results import settings, save_result


def make_viewer(name: str, frames: int, port: int):
    if name == "null":
        return newton.viewer.ViewerNull(num_frames=frames)
    if name == "viser":
        return newton.viewer.ViewerViser(port=port, verbose=False)
    raise ValueError(f"지원하지 않는 뷰어: {name}")


def _bounded_force(target: np.ndarray, velocity: np.ndarray, mass: float, gain: float = 8.0) -> np.ndarray:
    force = mass * gain * (target - velocity)
    length = float(np.linalg.norm(force))
    return force if length <= 80.0 else force / length * 80.0


def _upright_torque(pose, velocity, target, worker):
    """Physical stabilizer/heading servo; never overwrites a body's pose."""
    x, y, z, w = pose[3:7]
    up = np.array([2*(x*z + w*y), 2*(y*z - w*x), 1-2*(x*x+y*y)])
    stiffness, damping = (1200.0, 180.0) if worker else (55.0, 12.0)
    torque = stiffness * np.cross(up, np.array([0., 0., 1.])) - damping * velocity[3:6]
    yaw = math.atan2(2*(w*z+x*y), 1-2*(y*y+z*z))
    yaw_error = 0.0
    if np.linalg.norm(target) > .05:
        wanted = math.atan2(target[1], target[0])
        yaw_error = math.atan2(math.sin(wanted-yaw), math.cos(wanted-yaw))
    torque[2] = (20 if worker else 8) * yaw_error - (10 if worker else 3) * velocity[5]
    length = float(np.linalg.norm(torque))
    limit = 600 if worker else 40
    return torque if length <= limit else torque / length * limit


def run(
    algorithm_name: str = "orca",
    agent_count: int = 8,
    seed: int = 42,
    safety_distance: float = 0.35,
    robot_speed: float = 1.2,
    scenario_name: str = "warehouse",
    frames: int = 5400,
    viewer_name: str = "null",
    port: int = 8080,
    trace_stride: int = 3,
    bridge=None,
    goal_directed: bool = False,
    map_id: str = "map1",
    planner: str = "astar",
    traffic_mode: str = "dynamic",
    planner_seed: int = 42,
    common_traffic: bool = False,
    parameters: dict | None = None,
    persist: bool = True,
    quiet: bool = False,
) -> dict[str, object]:
    if not 0 <= agent_count <= 40:
        raise ValueError("Newton 웹 검증의 에이전트 수는 0~40 범위여야 합니다.")
    if not 0.0 <= safety_distance <= 1.0:
        raise ValueError("안전거리는 0~1m 범위여야 합니다.")
    if not 0.2 <= robot_speed <= 2.0:
        raise ValueError("로봇 속도는 0.2~2.0m/s 범위여야 합니다.")

    wall_started = time.perf_counter()
    parameters = settings(parameters)
    wp.init()
    wp.set_device("cpu")
    scenario = create_scenario(scenario_name, agent_count, seed, cooperative=False,
                               map_id=map_id, safety_distance=safety_distance)
    if traffic_mode not in ("static", "dynamic"):
        raise ValueError("정적/동적 실험 모드를 확인하세요.")
    if common_traffic and scenario.map_config:
        traffic_config=get_map(map_id)
        common_workers = [agent for agent in scenario.agents if agent.kind == "worker"]
        for agent,p,g in zip(common_workers, traffic_config["workerSpawnPositions"], traffic_config["workerPatrolTargets"]):
            agent.position=np.asarray(p,dtype=float);agent.origin=agent.position.copy();agent.goal=np.asarray(g,dtype=float)
    record = getattr(bridge, "record", None)
    if record:
        # Recorded geometry and body types are authoritative for old scenes.
        first = record["frames"][0]["body_q"]
        restored = [Agent(b["id"], np.array(first[b["body"]][:2]), np.zeros(2),
                          np.array(first[b["body"]][:2]), radius=b["radius"], kind=b["kind"])
                    for b in record["bodies"][1:]]
        scenario = Scenario(record["scenario"], record.get("width", 24.0),
                            record.get("height", 16.0), np.array(record["start"]),
                            np.array(record["goal"]), record["shelves"], restored,
                            "저장 기록", record.get("layout_version", 1),
                            record.get("protected_radius_m", 0.0))
    # Scripted traffic follows patrol targets rather than an avoidance solver.
    # ORCA must therefore take full responsibility, including for other AMRs.
    for traffic in scenario.agents:
        traffic.cooperative = False
    modern = scenario.layout_version >= 2
    robot_radius = record["bodies"][0]["radius"] if record else (.42 if modern else .38)
    robot_half_height = (record["bodies"][0].get("collider_half_height", robot_radius)
                         if record else (.26 if modern else robot_radius))
    shelf_height = record.get("shelf_height_m", 1.5) if record else (3.2 if modern else 1.5)
    algorithm = create_algorithm(algorithm_name)
    if algorithm_name.lower() == "vo":
        algorithm.horizon = parameters["vo_horizon_s"]
        algorithm.candidate_count = parameters["vo_candidates"]
    elif algorithm_name.lower() == "orca":
        algorithm.horizon = parameters["orca_horizon_s"]
        algorithm.neighbor_dist = parameters["orca_neighbor_dist_m"]
        algorithm.max_neighbors = parameters["orca_max_neighbors"]
    else:
        algorithm.stop_margin = parameters["naive_stop_margin_m"]
        algorithm.influence = parameters["naive_influence_m"]
    robot = ControlledRobot(
        identifier="controlled-robot",
        position=scenario.start.copy(),
        velocity=np.zeros(2),
        goal=scenario.goal.copy(),
        radius=robot_radius,
        max_speed=robot_speed,
        cooperative=True,
    )
    robot.path, planning = plan(planner, robot.position, robot.goal, scenario.width, scenario.height,
                                scenario.obstacles, robot.radius+safety_distance, planner_seed)

    requested_frames = frames
    # Live Start is a goal-directed mission. Old/open tabs can still submit the
    # former six-second budget; allow enough travel time before timing out.
    # Batch comparisons and loaded recordings retain their requested intervals.
    if goal_directed and bridge and not getattr(bridge, "record", None):
        path_length = sum(float(np.linalg.norm(b - a)) for a, b in zip(robot.path, robot.path[1:]))
        travel_frames = math.ceil((2.0 * path_length / robot_speed + 10.0) / parameters["time_step_s"])
        frames = max(frames, min(10800, travel_frames))

    builder = newton.ModelBuilder()
    # Low rolling resistance approximates a driven wheeled base, rather than
    # dragging a solid cylinder across a high-friction floor.
    builder.default_shape_cfg.mu = 0.05
    ground_shape = builder.add_ground_plane(label="ground")
    static_shapes: list[int] = []

    # Boundary walls and warehouse shelves are fixed Newton collision shapes.
    wall_height = 0.8
    static_shapes.extend(
        [
            builder.add_shape_box(-1, xform=wp.transform((scenario.width / 2, -0.15, wall_height), wp.quat_identity()), hx=scenario.width / 2, hy=0.15, hz=wall_height, label="wall_south"),
            builder.add_shape_box(-1, xform=wp.transform((scenario.width / 2, scenario.height + 0.15, wall_height), wp.quat_identity()), hx=scenario.width / 2, hy=0.15, hz=wall_height, label="wall_north"),
            builder.add_shape_box(-1, xform=wp.transform((-0.15, scenario.height / 2, wall_height), wp.quat_identity()), hx=0.15, hy=scenario.height / 2, hz=wall_height, label="wall_west"),
            builder.add_shape_box(-1, xform=wp.transform((scenario.width + 0.15, scenario.height / 2, wall_height), wp.quat_identity()), hx=0.15, hy=scenario.height / 2, hz=wall_height, label="wall_east"),
        ]
    )
    shelf_poses = (record.get("shelf_poses") if record else None)
    if shelf_poses is None:
        shelf_poses = (shelf_geometry(scenario.map_config) if scenario.map_config else
                       [{"position":[x+w/2,y+d/2], "rotation":0, "size":[w,d],
                         "obstacle":[x,y,w,d]} for x,y,w,d in scenario.obstacles])
    for index, shelf in enumerate(shelf_poses):
        cx, cy = shelf["position"]
        width, height = shelf["size"]
        yaw = math.radians(shelf["rotation"])
        static_shapes.append(
            builder.add_shape_box(
                -1,
                xform=wp.transform((cx, cy, shelf_height / 2), wp.quat_from_axis_angle(wp.vec3(0,0,1), yaw)),
                hx=width / 2,
                hy=height / 2,
                hz=shelf_height / 2,
                color=wp.vec3(0.34, 0.38, 0.42),
                label=f"shelf_{index}",
            )
        )

    robot_body = builder.add_body(
        xform=wp.transform((float(robot.position[0]), float(robot.position[1]), robot_half_height), wp.quat_identity()),
        mass=0.0,
        label="controlled_robot",
    )
    robot_shape = builder.add_shape_cylinder(
        robot_body,
        radius=robot.radius,
        half_height=robot_half_height,
        cfg=newton.ModelBuilder.ShapeConfig(
            density=14.0 / (math.pi * robot.radius**2 * 2 * robot_half_height), mu=0.05),
        color=wp.vec3(0.08, 0.44, 0.88),
        label="controlled_robot_shape",
    )

    agent_bodies: list[int] = []
    agent_shapes: list[int] = []
    agent_masses: list[float] = []
    agent_half_heights: list[float] = []
    for index, agent in enumerate(scenario.agents):
        half_height = ((.55 if agent.kind == "worker" else .26) if modern
                       else (.3 if agent.kind == "worker" else agent.radius))
        if record:
            half_height = record["bodies"][index + 1].get("collider_half_height", half_height)
        agent_half_heights.append(half_height)
        mass = 12.0 if agent.kind == "robot" else 70.0
        body = builder.add_body(
            xform=wp.transform((float(agent.position[0]), float(agent.position[1]), half_height + (agent.radius if agent.kind == "worker" else 0.0)), wp.quat_identity()),
            mass=0.0,
            label=agent.identifier,
        )
        shape_fn = builder.add_shape_capsule if agent.kind == "worker" else builder.add_shape_cylinder
        volume = (math.pi * agent.radius**2 * 2 * half_height + 4 * math.pi * agent.radius**3 / 3
                  if agent.kind == "worker" else 2 * math.pi * agent.radius**2 * half_height)
        shape = shape_fn(
            body,
            radius=agent.radius,
            half_height=half_height,
            cfg=newton.ModelBuilder.ShapeConfig(density=mass / volume, mu=0.05),
            color=wp.vec3(0.95, 0.55, 0.18) if agent.kind == "worker" else wp.vec3(0.35, 0.55, 0.88),
            label=f"{agent.identifier}_shape",
        )
        agent_bodies.append(body)
        agent_shapes.append(shape)
        agent_masses.append(mass)

    model = builder.finalize(device="cpu")
    solver = newton.solvers.SolverXPBD(model, iterations=8)
    state_0, state_1 = model.state(), model.state()
    control = model.control()
    pipeline = newton.CollisionPipeline(model)
    contacts = pipeline.contacts()
    viewer = bridge.viewer if bridge else make_viewer(viewer_name, frames, port)
    viewer.set_model(model)
    camera_pos = (scenario.width, -scenario.height*.75, scenario.width*.90)
    delta = np.array([scenario.width/2, scenario.height/2, 1.0]) - camera_pos
    viewer.set_camera(pos=wp.vec3(*camera_pos),
                      pitch=math.degrees(math.atan2(delta[2], np.linalg.norm(delta[:2]))),
                      yaw=math.degrees(math.atan2(delta[1], delta[0])))

    frame_dt, substeps = parameters["time_step_s"], 2
    sim_dt = frame_dt / substeps
    sim_time = 0.0
    computation_ms = 0.0
    algorithm_max_ms = 0.0
    algo_steps = 0
    physics_ms = 0.0
    neighbor_checks = candidate_checks = constraints = 0
    collision_events = 0
    safety_events = 0
    active_collisions: set[int] = set()
    active_safety: set[int] = set()
    contact_labels: set[str] = set()
    traces: list[dict[str, object]] = []
    path_length = 0.0
    previous_robot = robot.position.copy()
    status = "timeout"

    metadata = {
        "parameters": parameters,
        **planning, "traffic_mode":traffic_mode, "common_traffic":common_traffic,
        "engine": "NVIDIA Newton", "newton_version": newton.__version__,
        "warp_version": wp.__version__, "device": "cpu", "algorithm": algorithm.name,
        "scenario": scenario_name, "agent_count": len(scenario.agents), "seed": seed,
        "worker_count": sum(a.kind == "worker" for a in scenario.agents),
        "other_robot_count": sum(a.kind == "robot" for a in scenario.agents),
        "safety_distance_m": safety_distance, "robot_speed_mps": robot_speed,
        "width": scenario.width, "height": scenario.height,
        "shelves": [list(g.get("bounds", g["obstacle"])) for g in shelf_poses],
        "shelf_poses": shelf_poses,
        "mapId": (record or {}).get("mapId", (scenario.map_config or {}).get("mapId", "map1")),
        "mapName": (record or {}).get("mapName", (scenario.map_config or {}).get("mapName", "기존 배치")),
        "mapDescription": (record or {}).get("mapDescription", (scenario.map_config or {}).get("description", scenario.description)),
        "map_config": (record or {}).get("map_config", scenario.map_config),
        "layout_version": scenario.layout_version, "protected_radius_m": scenario.protected_radius,
        "shelf_height_m": shelf_height, "wall_height_m": wall_height * 2,
        "crossing_worker_count": int(sum(a.kind == "worker" and (a.position[1] - scenario.height/2) *
                                     (a.goal[1] - scenario.height/2) < 0 for a in scenario.agents)),
        "requested_frame_limit": requested_frames, "frame_limit": frames,
        "frame_budget_extended": frames > requested_frames,
        "start": scenario.start.tolist(), "goal": scenario.goal.tolist(),
        "astar_path": [p.tolist() for p in robot.path],
        "bodies": [{"id": "R0", "kind": "robot", "body": robot_body, "radius": robot.radius, "collider_half_height": robot_half_height, "cooperative": True, "mass_kg": float(model.body_mass.numpy()[robot_body])}]
            + [{"id": a.identifier, "kind": a.kind, "body": b, "radius": a.radius, "collider_half_height": agent_half_heights[i], "cooperative": a.cooperative, "mass_kg": float(model.body_mass.numpy()[b])}
               for i, (a, b) in enumerate(zip(scenario.agents, agent_bodies))],
    }
    def snapshot(target, algo_ms, step_ms):
        q, qd = state_0.body_q.numpy(), state_0.body_qd.numpy()
        return {
            "t": round(sim_time, 6), "robot": q[robot_body, :2].tolist(),
            "velocity": qd[robot_body, :2].tolist(), "target_velocity": list(map(float, target)),
            "body_q": q.tolist(), "body_qd": qd.tolist(),
            "workers": [q[b, :2].tolist() for a, b in zip(scenario.agents, agent_bodies) if a.kind == "worker"],
            "robots": [q[b, :2].tolist() for a, b in zip(scenario.agents, agent_bodies) if a.kind == "robot"],
            "collisions": collision_events, "safety_violations": safety_events,
            "contact_shapes": sorted(active_collisions),
            "risk": bool(active_collisions or active_safety),
            "goal_distance_m": float(np.linalg.norm(robot.goal - q[robot_body, :2])),
            "reached": (float(np.linalg.norm(robot.goal - q[robot_body, :2])) <= .25
                        and float(np.linalg.norm(qd[robot_body, :2])) <= .02),
            "algorithm_ms": algo_ms, "physics_ms": step_ms,
        }
    visuals = None
    if bridge:
        bridge.attach(metadata, model, state_0, snapshot([0, 0], 0, 0))
    elif viewer_name == "viser":
        from warehouse_visuals import WarehouseVisuals
        visuals = WarehouseVisuals(viewer, metadata)
        visuals.update(state_0.body_q.numpy())
    try:
        for frame in range(frames):
            if bridge:
                bridge.before_frame()

            body_q = state_0.body_q.numpy()
            body_qd = state_0.body_qd.numpy()
            robot.position = np.asarray(body_q[robot_body][:2], dtype=float)
            robot.velocity = np.asarray(body_qd[robot_body][:2], dtype=float)
            for index, agent in enumerate(scenario.agents):
                agent.position = np.asarray(body_q[agent_bodies[index]][:2], dtype=float)
                agent.velocity = np.asarray(body_qd[agent_bodies[index]][:2], dtype=float)
                agent.advance_patrol_goal()

            preferred = robot.preferred_velocity()
            # Decelerate before arrival; completion requires actual physical rest.
            preferred_speed = float(np.linalg.norm(preferred))
            braking_speed = 2.0 * float(np.linalg.norm(robot.goal - robot.position))
            if preferred_speed > braking_speed:
                preferred *= braking_speed / preferred_speed
            started = time.perf_counter_ns()
            target_velocity, diagnostics = algorithm.choose_velocity(
                robot, scenario.agents, preferred, safety_distance, frame_dt
            )
            algorithm_ms = (time.perf_counter_ns() - started) / 1_000_000
            computation_ms += algorithm_ms
            algorithm_max_ms = max(algorithm_max_ms, algorithm_ms)
            algo_steps += 1
            neighbor_checks += diagnostics.neighbor_checks
            candidate_checks += diagnostics.candidate_checks
            constraints += diagnostics.constraints
            agent_targets = [agent.preferred_velocity() if traffic_mode == "dynamic" else np.zeros(2) for agent in scenario.agents]

            physics_started = time.perf_counter_ns()
            for _ in range(substeps):
                state_0.clear_forces()
                velocity = np.asarray(state_0.body_qd.numpy()[robot_body][:2], dtype=float)
                poses = state_0.body_q.numpy()
                velocities = state_0.body_qd.numpy()
                robot_force = _bounded_force(target_velocity, velocity, 14.0)
                robot_torque = _upright_torque(poses[robot_body], velocities[robot_body], target_velocity, False)
                state_0.body_f[robot_body : robot_body + 1].fill_(
                    wp.spatial_vector(float(robot_force[0]), float(robot_force[1]), 0.0, *map(float, robot_torque))
                )
                velocities = state_0.body_qd.numpy()
                for index, body in enumerate(agent_bodies):
                    force = _bounded_force(agent_targets[index], np.asarray(velocities[body][:2]), agent_masses[index])
                    torque = _upright_torque(poses[body], velocities[body], agent_targets[index], scenario.agents[index].kind == "worker")
                    state_0.body_f[body : body + 1].fill_(
                        wp.spatial_vector(float(force[0]), float(force[1]), 0.0, *map(float, torque))
                    )
                pipeline.collide(state_0, contacts)
                count = int(contacts.rigid_contact_count.numpy()[0])
                shape_0 = contacts.rigid_contact_shape0.numpy()[:count]
                shape_1 = contacts.rigid_contact_shape1.numpy()[:count]
                current_collisions: set[int] = set()
                for left, right in zip(shape_0, shape_1, strict=True):
                    if robot_shape not in (int(left), int(right)):
                        continue
                    other = int(right) if int(left) == robot_shape else int(left)
                    if other == ground_shape:
                        contact_labels.add("ground")
                    elif other >= 0:
                        contact_labels.add(model.shape_label[other])
                        current_collisions.add(other)
                collision_events += len(current_collisions - active_collisions)
                active_collisions = current_collisions
                solver.step(state_0, state_1, control, contacts, sim_dt)
                state_0, state_1 = state_1, state_0
                sim_time += sim_dt

            # Recompute Contacts at the displayed post-step pose.
            pipeline.collide(state_0, contacts)
            count = int(contacts.rigid_contact_count.numpy()[0])
            active_collisions = {
                int(r) if int(l) == robot_shape else int(l)
                for l, r in zip(contacts.rigid_contact_shape0.numpy()[:count],
                                contacts.rigid_contact_shape1.numpy()[:count])
                if robot_shape in (int(l), int(r))
                and (int(r) if int(l) == robot_shape else int(l)) not in (-1, ground_shape)
            }
            step_ms = (time.perf_counter_ns() - physics_started) / 1_000_000
            physics_ms += step_ms
            body_q = state_0.body_q.numpy()
            body_qd = state_0.body_qd.numpy()
            robot.position = np.asarray(body_q[robot_body][:2], dtype=float)
            robot.velocity = np.asarray(body_qd[robot_body][:2], dtype=float)
            path_length += float(np.linalg.norm(robot.position - previous_robot))
            previous_robot = robot.position.copy()
            current_safety = {
                index
                for index, body in enumerate(agent_bodies)
                if float(np.linalg.norm(robot.position - np.asarray(body_q[body][:2])))
                < robot.radius + scenario.agents[index].radius + safety_distance
            }
            safety_events += len(current_safety - active_safety)
            active_safety = current_safety

            arrived = (float(np.linalg.norm(robot.goal - robot.position)) <= .25
                       and float(np.linalg.norm(robot.velocity)) <= .02)
            viewer.begin_frame(sim_time)
            viewer.log_state(state_0)
            if visuals:
                visuals.update(body_q)
            viewer.log_contacts(contacts, state_0)
            viewer.end_frame()

            if frame % max(1, trace_stride) == 0 or frame == frames - 1 or arrived:
                traces.append(snapshot(target_velocity, algorithm_ms, step_ms))
            if bridge:
                bridge.after_frame(snapshot(target_velocity, algorithm_ms, step_ms), state_0)


            if arrived:
                status = "success"
                break
    finally:
        if not bridge:
            viewer.close()

    result = {
        **metadata,
        "engine": "NVIDIA Newton",
        "newton_version": newton.__version__,
        "warp_version": wp.__version__,
        "device": str(wp.get_device()),
        "viewer": viewer_name,
        "algorithm": algorithm.name,
        "scenario": scenario_name,
        "agent_count": len(scenario.agents),
        "worker_count": sum(agent.kind == "worker" for agent in scenario.agents),
        "other_robot_count": sum(agent.kind == "robot" for agent in scenario.agents),
        "seed": seed,
        "safety_distance_m": safety_distance,
        "robot_speed_mps": robot_speed,
        "status": status,
        "termination_reason": "goal_reached" if status == "success" else "frame_limit",
        "goal_distance_m": float(np.linalg.norm(robot.goal - robot.position)),
        "sim_time_s": round(sim_time, 3),
        "path_length_m": path_length,
        "final_position": [round(float(v), 4) for v in robot.position],
        "final_velocity": [round(float(v), 4) for v in robot.velocity],
        "goal": [round(float(v), 4) for v in robot.goal],
        "collisions": collision_events,
        "safety_violations": safety_events,
        "physics_runtime_ms": round(physics_ms, 4),
        "algorithm_runtime_ms": round(computation_ms, 4),
        "wall_time_s": time.perf_counter() - wall_started,
        "algo_time_avg_ms": computation_ms / max(1, algo_steps),
        "algo_time_max_ms": algorithm_max_ms,
        "algo_steps": algo_steps,
        "algorithm_ms_per_frame": round(computation_ms / max(1, frame + 1), 6),
        "neighbor_checks": neighbor_checks,
        "candidate_checks": candidate_checks,
        "constraints": constraints,
        "contact_labels": sorted(contact_labels),
        "astar_path": [[round(float(v), 3) for v in point] for point in robot.path],
        "frames": traces,
    }
    if persist and not record:
        result["csv_path"] = str(save_result(result))
    if not quiet:
        print(f'{scenario_name} {algorithm.name}: avg={result["algo_time_avg_ms"]:.6f}ms max={algorithm_max_ms:.6f}ms steps={algo_steps}')
    if not bridge and not quiet:
        print("RESULT_JSON=" + json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--algorithm", choices=("naive", "vo", "orca"), default="orca")
    parser.add_argument("--agents", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--safety", type=float, default=0.35)
    parser.add_argument("--speed", type=float, default=1.2)
    parser.add_argument("--scenario", choices=SCENARIOS, default="warehouse")
    parser.add_argument("--frames", type=int, default=5400)
    parser.add_argument("--viewer", choices=("null", "viser"), default="null")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--map", dest="map_id", default="map1")
    parser.add_argument("--planner", choices=("astar","dijkstra","rrt"), default="astar")
    parser.add_argument("--traffic-mode", choices=("static","dynamic"), default="dynamic")
    parser.add_argument("--planner-seed", type=int, default=42)
    parser.add_argument("--common-traffic", action="store_true", help="Use map-configured common patrol spawns")
    parser.add_argument("--parameters", default="{}", help="회피 파라미터 JSON")
    args = parser.parse_args()
    run(args.algorithm, args.agents, args.seed, args.safety, args.speed, args.scenario, args.frames, args.viewer, args.port, map_id=args.map_id, planner=args.planner, traffic_mode=args.traffic_mode, planner_seed=args.planner_seed, common_traffic=args.common_traffic, parameters=json.loads(args.parameters))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
