"""Per-session Newton worker. File IPC keeps WIZ's Python isolated from Newton."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import time

import numpy as np
import warp as wp
from newton_warehouse import run, make_viewer
from viewer_transport import start_transport
from warehouse_visuals import WarehouseVisuals


class Restart(Exception):
    pass


def atomic_json(path, value):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    os.replace(temp, path)


class LiveBridge:
    def __init__(self, folder, config):
        self.folder, self.config = folder, config
        self.viewer = make_viewer("viser", config["frames"], 0)
        self.transport = start_transport(self.viewer.server.get_port())
        # Parent dashboard owns the only simulation clock and controls.
        self.viewer.server.gui.reset()
        # Newton 1.7 retains native checkbox references after Viser gui.reset().
        # The dashboard owns those controls, so detach the removed handles.
        self.viewer._viewer_option_handles.clear()
        self.viewer._simulation_gui_handles.clear()
        self.viewer.server.gui.add_markdown("**Newton CPU · Warehouse**\n\n대시보드에서 실행과 시간 상태를 제어합니다.\n\n드래그: 회전 · 휠: 확대 · 우클릭: 이동")
        self.command_id = ""
        self.phase = "paused"
        self.last_touch = time.monotonic()
        self.show_path = self.show_risk = True
        self.record = config.pop("record", None)
        self.sequence = 0

    def attach(self, metadata, model, state, initial):
        self.meta, self.model = metadata, model
        self.replay_state = model.state()
        self.history = [initial]
        self.cursor = 0
        self.finished = bool(self.record)
        if self.record:
            self.meta.update({k: v for k, v in self.record.items() if k != "frames"})
            self.history = self.record["frames"]
            self.phase = "replay_paused"
        self.scene = self.viewer.server.scene
        self.visuals = WarehouseVisuals(self.viewer, self.meta)
        self.scene.add_grid("/warehouse/grid", width=self.meta["width"], height=self.meta["height"], plane="xy",
                            position=(self.meta["width"]/2, self.meta["height"]/2, .015), cell_size=1, section_size=4)
        for key, color in [("start", (20, 184, 166)), ("goal", (34, 197, 94))]:
            p = (*metadata[key], .1)
            self.scene.add_icosphere("/warehouse/" + key, radius=.23, position=p, color=color)
            self.scene.add_label("/warehouse/" + key + "/label", text=key.upper(), position=(0, 0, .4))
        self.labels = {
            b["id"]: self.scene.add_label("/warehouse/ids/" + b["id"], text=b["id"])
            for b in metadata["bodies"]
        }
        self.planned = self.scene.add_line_segments("/warehouse/planned",
            points=self.segments([(*p, .06) for p in metadata["astar_path"]]),
            colors=(100, 140, 135), line_width=2)
        protected = self.meta.get("protected_radius_m", 0)
        if protected:
            angle = np.linspace(0, 2*np.pi, 65)
            for key in ("start", "goal"):
                centre = self.meta[key]
                ring = [(centre[0]+protected*np.cos(a), centre[1]+protected*np.sin(a), .035) for a in angle]
                self.scene.add_line_segments("/warehouse/protected-" + key, points=self.segments(ring),
                                             colors=(65, 172, 147), line_width=2)
        for i, frame in enumerate(self.history):
            atomic_json(self.folder / ("frame-%04d.json" % i), frame)
        self.draw(self.history[0])
        self.publish()

    @staticmethod
    def segments(points):
        if len(points) < 2:
            points = points * 2
        p = np.asarray(points, dtype=np.float32)
        return np.stack((p[:-1], p[1:]), axis=1)

    def draw(self, frame):
        # log_state receives the exact recorded Newton pose, including Z and rotation.
        self.replay_state.body_q.assign(np.asarray(frame["body_q"], dtype=np.float32))
        self.replay_state.body_qd.assign(np.asarray(frame["body_qd"], dtype=np.float32))
        self.viewer.begin_frame(frame["t"])
        self.viewer.log_state(self.replay_state)
        self.visuals.update(frame["body_q"])
        for b in self.meta["bodies"]:
            q = frame["body_q"][b["body"]]
            self.labels[b["id"]].position = (q[0], q[1], q[2] + b["radius"] + .25)
        points = [(*f["robot"], .09) for f in self.history[:self.cursor + 1]]
        if len(points) == 1:
            points.append(points[0])
        handle = self.scene.add_line_segments("/warehouse/actual", points=self.segments(points),
                        colors=(20, 184, 166), line_width=4)
        handle.visible = self.show_path
        self.planned.visible = self.show_path
        # Red ring denotes current Contacts or safety gap violation, not historical totals.
        angle = np.linspace(0, 2 * np.pi, 49)
        radius = self.meta["bodies"][0]["radius"] + self.meta["safety_distance_m"]
        points = [(frame["robot"][0] + radius * np.cos(a),
                   frame["robot"][1] + radius * np.sin(a), .12) for a in angle]
        halo = self.scene.add_line_segments("/warehouse/risk", points=self.segments(points),
                    colors=(239, 68, 68) if frame["risk"] else (20, 184, 166), line_width=5)
        halo.visible = self.show_risk
        self.viewer.end_frame()

    def publish(self):
        self.sequence += 1
        atomic_json(self.folder / "status.json", {
            **self.meta, "phase": self.phase, "frame_index": self.cursor,
            "frame_count": len(self.history), "current": self.history[self.cursor],
            "ack": self.command_id, "port": self.viewer.server.get_port(),
            "sequence": self.sequence, "transport_port": self.transport.server_port,
        })

    def command(self):
        path = self.folder / "command.json"
        if not path.exists():
            return
        data = json.loads(path.read_text())
        if data["id"] == self.command_id:
            return
        self.command_id = data["id"]
        self.last_touch = time.monotonic()
        action = data["action"]
        if action == "close":
            raise SystemExit(0)
        if action == "reset":
            self.phase = "paused"
            self.record = None
            raise Restart()
        if action == "pause":
            self.phase = "replay_paused" if self.finished else "paused"
        elif action == "resume":
            self.phase = "replay" if self.finished else "running"
        elif action == "seek" and self.finished:
            self.cursor = max(0, min(int(data["frame"]), len(self.history) - 1))
            self.phase = "replay_paused"
            self.draw(self.history[self.cursor])
        elif action == "display":
            self.show_path = bool(data["path"])
            self.show_risk = bool(data["risk"])
            self.draw(self.history[self.cursor])
        self.publish()

    def before_frame(self):
        while True:
            self.command()
            if time.monotonic() - self.last_touch > 900:
                raise SystemExit(0)
            if self.phase == "running":
                return
            delay = .025
            if self.phase == "replay":
                if self.cursor < len(self.history) - 1:
                    delay = max(.001, min(.25, self.history[self.cursor + 1]["t"] - self.history[self.cursor]["t"]))
                    self.cursor += 1
                    self.draw(self.history[self.cursor])
                else:
                    self.phase = "replay_paused"
                self.publish()
            time.sleep(delay)

    def after_frame(self, frame, state):
        self.history.append(frame)
        self.cursor = len(self.history) - 1
        atomic_json(self.folder / ("frame-%04d.json" % self.cursor), frame)
        self.draw(frame)
        self.publish()
        time.sleep(1 / 30)

    def finish(self, result):
        result["frames"] = self.history
        atomic_json(self.folder / "record.json", result)
        self.meta.update({k: v for k, v in result.items() if k != "frames"})
        self.finished = True
        self.phase = "replay_paused"
        self.publish()
        self.before_frame()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder")
    args = parser.parse_args()
    folder = Path(args.folder)
    config = json.loads((folder / "config.json").read_text())
    bridge = None
    try:
        bridge = LiveBridge(folder, config)
        while True:
            try:
                result = run(**config, bridge=bridge, trace_stride=1, goal_directed=True)
                bridge.finish(result)
            except Restart:
                continue
    except Exception as error:
        atomic_json(folder / "error.json", {"message": type(error).__name__ + ": " + str(error)})
        raise
    finally:
        if bridge:
            bridge.transport.shutdown()
            bridge.viewer.close()


if __name__ == "__main__":
    main()
