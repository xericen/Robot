"""CPU integration checks for Newton -> telemetry -> Viser transforms."""
import json
import numpy as np
import pytest

pytest.importorskip("newton")
import newton_warehouse as engine
from newton_live import LiveBridge


class TestBridge(LiveBridge):
    __test__ = False

    def before_frame(self):
        self.phase = "running"

    def after_frame(self, frame, state):
        super().after_frame(frame, state)
        packed = self.viewer._packed_shape_world_xforms.numpy()
        shapes = self.viewer._slot_to_shape_wp.numpy()
        bodies = self.model.shape_body.numpy()
        # All dynamic shapes in this scene have identity local transforms.
        for slot, shape in enumerate(shapes):
            body = bodies[shape]
            if body >= 0:
                np.testing.assert_allclose(packed[slot, :3], frame["body_q"][body][:3], atol=1e-6)
        np.testing.assert_allclose(self.replay_state.body_q.numpy(), frame["body_q"], atol=1e-6)


def test_contacts_and_exact_3d_pose(tmp_path, monkeypatch):
    factory = engine.create_scenario

    def overlapping(*args, **kwargs):
        scene = factory(*args, **kwargs)
        scene.agents[0].position = np.array([1.7, 8.0])
        return scene

    monkeypatch.setattr(engine, "create_scenario", overlapping)
    bridge = TestBridge(tmp_path, {"frames": 5})
    try:
        result = engine.run(agent_count=1, scenario_name="basic", frames=5,
                            trace_stride=1, bridge=bridge)
        assert result["device"] == "cpu"
        assert result["collisions"] > 0
        assert any(f["contact_shapes"] and f["risk"] for f in result["frames"])
        assert all(f["robot"] == f["body_q"][0][:2] for f in result["frames"])
        assert all(f["velocity"] == f["body_qd"][0][:2] for f in result["frames"])
        assert result["physics_runtime_ms"] > 0
        assert result["algorithm_runtime_ms"] > 0
        # Retain a small actual collision record for manual/browser verification.
        (tmp_path / "collision-record.json").write_text(json.dumps(result))
    finally:
        bridge.transport.shutdown()
        bridge.viewer.close()


@pytest.mark.parametrize("method", ["naive", "vo", "orca"])
def test_real_algorithm_dispatch(method):
    result = engine.run(algorithm_name=method, agent_count=1, frames=3, trace_stride=1)
    assert result["algorithm"].lower() == method
    assert result["algorithm_runtime_ms"] > 0
    assert result["frames"][-1]["robot"] != result["start"]
    assert any(np.linalg.norm(f["target_velocity"]) > 0 for f in result["frames"])
    assert result["neighbor_checks"] + result["candidate_checks"] + result["constraints"] > 0


@pytest.mark.parametrize("method", ["naive", "vo", "orca"])
def test_warehouse_robot_reaches_goal_and_stops(method):
    # The former implementation moved only ~0.013m in 30 simulated seconds.
    result = engine.run(algorithm_name=method, agent_count=8,
                        scenario_name="warehouse", frames=1800, trace_stride=7)
    assert result["status"] == "success"
    assert result["termination_reason"] == "goal_reached"
    assert result["goal_distance_m"] <= .25
    assert np.linalg.norm(result["final_velocity"]) <= .02
    assert result["path_length_m"] > 20
    assert result["frames"][-1]["reached"]
    assert result["frames"][-1]["t"] == pytest.approx(result["sim_time_s"], abs=.001)
    assert result["bodies"][0]["mass_kg"] == pytest.approx(14, rel=1e-5)
    assert all(b["mass_kg"] == pytest.approx(70, rel=1e-5) for b in result["bodies"][1:])


def test_short_run_reports_timeout_not_arrival():
    result = engine.run(agent_count=0, frames=30)
    assert result["status"] == "timeout"
    assert result["termination_reason"] == "frame_limit"
    assert not result["frames"][-1]["reached"]
    assert result["goal_distance_m"] > 20


def test_live_start_extends_legacy_six_second_budget():
    class MissionBridge:
        viewer = engine.make_viewer("null", 1800, 0)
        record = None

        def attach(self, metadata, model, state, initial):
            self.metadata = metadata

        def before_frame(self):
            pass

        def after_frame(self, frame, state):
            self.last = frame

    bridge = MissionBridge()
    try:
        result = engine.run(agent_count=8, frames=180, trace_stride=30, bridge=bridge, goal_directed=True)
        assert result["requested_frame_limit"] == 180
        assert result["frame_budget_extended"]
        assert result["frame_limit"] > 180
        assert result["status"] == "success"
        assert result["sim_time_s"] > 6
        assert bridge.last["reached"]
        assert result["goal_distance_m"] <= .25
        assert np.linalg.norm(result["final_velocity"]) <= .02
    finally:
        bridge.viewer.close()
