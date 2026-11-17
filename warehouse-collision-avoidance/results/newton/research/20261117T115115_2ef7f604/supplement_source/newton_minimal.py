"""Minimal Newton 3-D warehouse physics smoke test.

This intentionally covers only the physics/runtime integration.  Naive, VO,
and ORCA remain in the existing simulator and are not reimplemented here.
"""

from __future__ import annotations

import argparse
import json
import math

import newton
import warp as wp


def make_viewer(name: str, frames: int, port: int):
    if name == "null":
        return newton.viewer.ViewerNull(num_frames=frames)
    if name == "viser":
        return newton.viewer.ViewerViser(port=port, verbose=False)
    if name == "gl":
        return newton.viewer.ViewerGL(num_frames=frames)
    raise ValueError(f"Unknown viewer: {name}")


def run(viewer_name: str, frames: int, port: int) -> dict[str, object]:
    wp.init()
    wp.set_device("cpu")

    builder = newton.ModelBuilder()
    builder.default_shape_cfg.mu = 0.8
    ground_shape = builder.add_ground_plane(label="ground")

    # Two fixed shelf-like obstacles.  Body index -1 attaches shapes to the world.
    shelf_a = builder.add_shape_box(
        -1,
        xform=wp.transform((3.2, 1.4, 0.75), wp.quat_identity()),
        hx=0.8,
        hy=0.35,
        hz=0.75,
        color=wp.vec3(0.35, 0.38, 0.42),
        label="shelf_a",
    )
    shelf_b = builder.add_shape_box(
        -1,
        xform=wp.transform((3.2, -1.4, 0.75), wp.quat_identity()),
        hx=0.8,
        hy=0.35,
        hz=0.75,
        color=wp.vec3(0.35, 0.38, 0.42),
        label="shelf_b",
    )

    start = (-3.0, 0.0, 0.35)
    goal = (1.5, 0.0)
    robot_body = builder.add_body(
        xform=wp.transform(start, wp.quat_identity()),
        mass=12.0,
        label="mobile_robot",
    )
    robot_shape = builder.add_shape_sphere(
        robot_body,
        radius=0.35,
        color=wp.vec3(0.1, 0.45, 0.95),
        label="mobile_robot_shape",
    )

    model = builder.finalize(device="cpu")
    solver = newton.solvers.SolverXPBD(model, iterations=8)
    state_0 = model.state()
    state_1 = model.state()
    control = model.control()
    pipeline = newton.CollisionPipeline(model)
    contacts = pipeline.contacts()
    viewer = make_viewer(viewer_name, frames, port)
    viewer.set_model(model)
    viewer.set_camera(pos=wp.vec3(8.0, -9.0, 7.0), pitch=-25.0, yaw=140.0)

    frame_dt = 1.0 / 60.0
    substeps = 4
    sim_dt = frame_dt / substeps
    sim_time = 0.0
    max_contact_count = 0
    robot_contact_labels: set[str] = set()
    reached = False

    try:
        for _ in range(frames):
            for _ in range(substeps):
                state_0.clear_forces()
                pose = state_0.body_q.numpy()[robot_body]
                velocity = state_0.body_qd.numpy()[robot_body]
                dx = goal[0] - float(pose[0])
                dy = goal[1] - float(pose[1])
                distance = math.hypot(dx, dy)

                # A bounded planar PD wrench drives a real Newton rigid body.
                force_x = max(-45.0, min(45.0, 24.0 * dx - 14.0 * float(velocity[0])))
                force_y = max(-45.0, min(45.0, 24.0 * dy - 14.0 * float(velocity[1])))
                state_0.body_f[robot_body : robot_body + 1].fill_(
                    wp.spatial_vector(force_x, force_y, 0.0, 0.0, 0.0, 0.0)
                )

                pipeline.collide(state_0, contacts)
                contact_count = int(contacts.rigid_contact_count.numpy()[0])
                max_contact_count = max(max_contact_count, contact_count)
                shape_0 = contacts.rigid_contact_shape0.numpy()[:contact_count]
                shape_1 = contacts.rigid_contact_shape1.numpy()[:contact_count]
                for left, right in zip(shape_0, shape_1, strict=True):
                    if robot_shape in (int(left), int(right)):
                        other = int(right) if int(left) == robot_shape else int(left)
                        robot_contact_labels.add("world" if other < 0 else model.shape_label[other])

                solver.step(state_0, state_1, control, contacts, sim_dt)
                state_0, state_1 = state_1, state_0
                sim_time += sim_dt

            viewer.begin_frame(sim_time)
            viewer.log_state(state_0)
            viewer.log_contacts(contacts, state_0)
            viewer.end_frame()

            pose = state_0.body_q.numpy()[robot_body]
            if math.hypot(goal[0] - float(pose[0]), goal[1] - float(pose[1])) < 0.25:
                reached = True
                break
    finally:
        viewer.close()

    pose = state_0.body_q.numpy()[robot_body]
    velocity = state_0.body_qd.numpy()[robot_body]
    result = {
        "newton_version": newton.__version__,
        "warp_version": wp.__version__,
        "device": str(wp.get_device()),
        "viewer": viewer_name,
        "frames_executed": round(sim_time / frame_dt),
        "sim_time_s": round(sim_time, 4),
        "start_xy": list(start[:2]),
        "goal_xy": list(goal),
        "final_xy": [round(float(pose[0]), 4), round(float(pose[1]), 4)],
        "final_velocity_xy": [round(float(velocity[0]), 4), round(float(velocity[1]), 4)],
        "goal_reached": reached,
        "max_rigid_contacts": max_contact_count,
        "robot_contact_labels": sorted(robot_contact_labels),
        "shape_indices": {
            "ground": ground_shape,
            "shelf_a": shelf_a,
            "shelf_b": shelf_b,
            "robot": robot_shape,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--viewer", choices=("null", "viser", "gl"), default="null")
    parser.add_argument("--frames", type=int, default=720)
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    result = run(args.viewer, args.frames, args.port)
    return 0 if result["goal_reached"] and result["max_rigid_contacts"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
