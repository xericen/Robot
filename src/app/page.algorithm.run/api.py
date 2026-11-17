def run():
    try:
        n = int(wiz.request.query("n", "20"))
        seed = int(wiz.request.query("seed", "42"))
        safety = float(wiz.request.query("safety", ".3"))
        pattern = wiz.request.query("pattern", "cross")
        mode = wiz.request.query("mode", "single")
        if not 0 <= n <= 100 or not 0 <= seed <= 999999 or not 0 <= safety <= 1:
            raise ValueError("군중 0~100명, 시드 0~999999, 안전 여유 0~1m를 입력하세요.")
        if pattern not in ["cross", "random"] or mode not in ["single", "batch"]:
            raise ValueError("잘못된 실험 조건입니다.")
        simulation = wiz.model("newton")
        sizes = sorted(set([0, n//4, n//2, n])) if mode == "batch" else [n]
        results = [simulation.run(size, seed, safety, pattern, method, mode == "single")
                   for size in sizes for method in ["Naive", "VO", "ORCA"]]
    except (ValueError, TypeError) as e:
        wiz.response.status(400, message=str(e))
    wiz.response.status(200, results)


def run_newton():
    import json
    import os
    import subprocess

    # Read persisted summaries without importing Newton into WIZ's interpreter.
    if wiz.request.query("mode", "single") == "saved":
        batch_id = wiz.request.query("batch_id", "")
        try:
            root = os.path.join(wiz.project.path(), "warehouse-collision-avoidance")
            completed = subprocess.run(
                [os.path.join(root, ".venv/bin/python"), "-c",
                 ("import json,sys; from unified_batch import active_status; print(json.dumps(active_status(sys.argv[1])['rows']))"
                  if batch_id else "import json,sys; from newton_results import load_results; print(json.dumps(load_results(sys.argv[1]=='true')))"),
                 batch_id or wiz.request.query("history", "false")],
                cwd=root, capture_output=True, text=True, timeout=15, check=True)
            rows = json.loads(completed.stdout)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            wiz.response.status(400, message=str(error))
        wiz.response.status(200, rows)
    try:
        algorithm = wiz.request.query("algorithm", "orca").lower()
        mode = wiz.request.query("mode", "single")
        parameters = json.loads(wiz.request.query("parameters", "{}"))
        if not isinstance(parameters, dict):
            raise ValueError("파라미터는 JSON 객체여야 합니다.")
        encounter_mode = wiz.request.query("encounter_mode", "baseline")
        population_mode = wiz.request.query("population_mode", "legacy")
        if encounter_mode not in ("baseline","head_on","crossing","narrow_passing") or population_mode not in ("legacy","workers","mixed"):
            raise ValueError("지원하지 않는 만남 조건/인구 구성입니다.")
        scenario = wiz.request.query("scenario", "medium")
        map_id = wiz.request.query("map_id", "map1")
        planner = wiz.request.query("planner", "astar")
        traffic_mode = wiz.request.query("traffic_mode", "dynamic")
        common_traffic = wiz.request.query("common_traffic", "false") == "true"
        if planner not in ("astar","dijkstra","rrt") or traffic_mode not in ("static","dynamic"):
            raise ValueError("지원하지 않는 경로 탐색/작업자 모드입니다.")
        agents = int(wiz.request.query("agents", "4"))
        seed = int(wiz.request.query("seed", "42"))
        safety = float(wiz.request.query("safety", ".35"))
        speed = float(wiz.request.query("speed", "1.2"))
        frames = int(wiz.request.query("frames", "5400"))
        if algorithm not in ["naive", "vo", "orca"] or mode not in ["single", "compare"]:
            raise ValueError("지원하지 않는 알고리즘 또는 실행 모드입니다.")
        if scenario not in ["easy", "medium", "hard", "crowded", "basic", "warehouse", "crossing", "multi_robot"]:
            raise ValueError("지원하지 않는 물류창고 시나리오입니다.")
        if not 0 <= agents <= 40 or not 0 <= seed <= 999999 or not 0 <= safety <= 1:
            raise ValueError("에이전트 0~40명, 시드 0~999999, 안전거리 0~1m를 입력하세요.")
        if not .2 <= speed <= 2 or not 30 <= frames <= 10800:
            raise ValueError("속도 0.2~2m/s, 프레임 30~10800 범위를 사용하세요.")

        catalog = json.load(open(os.path.join(wiz.project.path(), "warehouse-collision-avoidance", "warehouse_maps.json")))
        if map_id not in [m["mapId"] for m in catalog]:
            raise ValueError("지원하지 않는 선반 맵입니다.")
        project_path = wiz.project.path()
        simulator_path = os.path.join(project_path, "warehouse-collision-avoidance")
        python_path = os.path.join(simulator_path, ".venv", "bin", "python")
        script_path = os.path.join(simulator_path, "newton_warehouse.py")
        if not os.path.isfile(python_path) or not os.path.isfile(script_path):
            raise RuntimeError("Newton 독립 실행환경 또는 통합 스크립트를 찾을 수 없습니다.")

        methods = ["naive", "vo", "orca"] if mode == "compare" else [algorithm]
        results = []
        for method in methods:
            command = [
                python_path, script_path,
                "--algorithm", method,
                "--agents", str(agents),
                "--seed", str(seed),
                "--safety", str(safety),
                "--speed", str(speed),
                "--scenario", scenario,
                "--frames", str(frames),
                "--viewer", "null", "--map", map_id, "--planner", planner, "--traffic-mode", traffic_mode,
            ]
            command.extend(["--parameters", json.dumps(parameters), "--encounter", encounter_mode, "--population", population_mode])
            if common_traffic:
                command.append("--common-traffic")
            completed = subprocess.run(
                command,
                cwd=simulator_path,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            marker = next((line for line in reversed(completed.stdout.splitlines()) if line.startswith("RESULT_JSON=")), "")
            if completed.returncode != 0 or not marker:
                detail = (completed.stderr or completed.stdout or "Newton 실행 결과가 없습니다.")[-1200:]
                raise RuntimeError("Newton 실행 실패: " + detail)
            results.append(json.loads(marker[len("RESULT_JSON="):]))
    except (ValueError, TypeError, RuntimeError, subprocess.TimeoutExpired) as e:
        wiz.response.status(400, message=str(e))
    wiz.response.status(200, results)


def live_newton():
    """Capability-token session API; the Python 3.12 worker alone owns Newton."""
    import fcntl
    import json
    import os
    from pathlib import Path
    import re
    import subprocess
    import time
    import uuid

    root = Path(wiz.project.path()) / "warehouse-collision-avoidance"
    study_action = wiz.request.query("action", "status")
    if study_action == "unified_status":
        try:
            done = subprocess.run([str(root / ".venv/bin/python"), "-c",
                "import json,sys; from unified_batch import active_status; print(json.dumps(active_status(sys.argv[1])))",
                wiz.request.query("batch_id", "")],cwd=root,capture_output=True,text=True,timeout=15,check=True)
            selected = json.loads(done.stdout)
        except (OSError,ValueError,subprocess.SubprocessError) as error:
            wiz.response.status(400, message=str(error))
        wiz.response.status(200, selected)
    if study_action == "research_status":
        research_root = root / "results/newton/research"
        available = sorted(p.parent.name for p in research_root.glob("*/dashboard.json")
                           if re.fullmatch(r"[0-9]{8}T[0-9]{6}_[a-f0-9]{8}", p.parent.name)
                           and (json.loads(p.read_text()).get("schema",1)<2 or (p.parent/"verification.json").exists()))
        active = root / "results/newton/active_batch.json"
        preferred = json.loads(active.read_text()).get("research_id", "") if active.exists() else ""
        batch = wiz.request.query("research_id", "") or preferred or (available[-1] if available else "")
        if batch and batch not in available:
            wiz.response.status(400, message="지원하지 않는 연구 분석입니다.")
        data = json.loads((research_root / batch / "dashboard.json").read_text()) if batch else {"status":"missing"}
        data["available"] = available
        wiz.response.status(200, data)
    if study_action == "controlled_status":
        import csv
        batches=[]
        study_root=root/"results/newton/studies"
        try:
            for path in sorted(study_root.glob("*/progress.json")):
                if not re.fullmatch(r"[0-9]{8}T[0-9]{12}Z_[a-f0-9]{8}",path.parent.name):
                    continue
                state=json.loads(path.read_text())
                batches.append({key:state.get(key) for key in ("batch_id","phase","completed","total")})
            batch=wiz.request.query("batch_id", "") or (batches[-1]["batch_id"] if batches else "")
            if batch and (not re.fullmatch(r"[0-9]{8}T[0-9]{12}Z_[a-f0-9]{8}",batch)
                          or batch not in [b["batch_id"] for b in batches]):
                raise ValueError("지원하지 않는 실험 배치입니다.")
            result={"batches":batches,"phase":"idle","rows":[],"figures":[],"batch_id":batch}
            if batch:
                folder=study_root/batch
                result.update(json.loads((folder/"progress.json").read_text()))
                result["configuration"]=json.loads((folder/"configuration.json").read_text())
                summary=folder/"safety_summary.csv"
                if summary.exists():
                    with summary.open() as source:
                        result["rows"]=[{k:(None if v=="" else v) for k,v in row.items()} for row in csv.DictReader(source)]
                if result["phase"]=="complete":
                    result["figures"]=[{"group":p.parent.name,"name":p.name,
                        "url":"/warehouse-experiments/"+batch+"/"+p.parent.name+"/"+p.name}
                        for p in sorted((folder/"figs").glob("*/*.png"))]
        except (OSError,ValueError) as error:
            wiz.response.status(400,message=str(error))
        wiz.response.status(200,result)
    if study_action in ("study_start", "study_status"):
        study_result = None
        try:
            study_dir = root / "results" / "planning"
            study_dir.mkdir(parents=True, exist_ok=True)
            if study_action == "study_start":
                with (study_dir / ".lock").open("a") as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX)
                    running = False
                    try:
                        pid = int((study_dir / "pid").read_text())
                        os.kill(pid, 0)
                        state = Path("/proc") / str(pid) / "stat"
                        running = state.exists() and not state.read_text().split(") ",1)[1].startswith("Z")
                    except (OSError,ValueError):
                        pass
                    if not running:
                        temporary = study_dir / "admission.tmp"
                        temporary.write_text(json.dumps({"phase":"starting","rows":[],"summary":[],"completed":0,"total":60}))
                        os.replace(temporary, study_dir / "progress.json")
                        process = subprocess.Popen([str(root / ".venv/bin/python"),str(root / "planning_study.py")],
                                                     cwd=root,stdout=(study_dir / "worker.log").open("w"),
                                                     stderr=subprocess.STDOUT,start_new_session=True)
                        (study_dir / "pid").write_text(str(process.pid))
                        study_result = {"phase":"starting","rows":[],"summary":[],"completed":0,"total":60}

            path = study_dir / "progress.json"
            if study_result is None:
                study_result = json.loads(path.read_text()) if path.exists() else {"phase":"idle","rows":[],"summary":[]}
            if study_result.get("phase") in ("running","starting") and (study_dir / "pid").exists():
                try:
                    study_pid = int((study_dir / "pid").read_text())
                    os.kill(study_pid, 0)
                    state = Path("/proc") / str(study_pid) / "stat"
                    if state.exists() and state.read_text().split(") ",1)[1].startswith("Z"):
                        raise ProcessLookupError()
                except (ProcessLookupError,ValueError):
                    study_result.update(phase="error",error="실험 프로세스가 종료되었습니다. 완료된 최신 결과는 보존됩니다.")
        except (OSError,ValueError) as error:
            wiz.response.status(400, message=str(error))
        wiz.response.status(200, study_result)
    if wiz.request.query("action", "status") == "maps":
        try:
            catalog = json.loads((root / "warehouse_maps.json").read_text())
        except (OSError, ValueError) as error:
            wiz.response.status(400, message=str(error))
        wiz.response.status(200, catalog)
    created_process = None
    try:
        root = Path(wiz.project.path()) / "warehouse-collision-avoidance"
        sessions = root / "results" / "live"
        sessions.mkdir(parents=True, exist_ok=True)
        action = wiz.request.query("action", "status")
        token = wiz.request.query("token", "")
        if action in ("create", "load"):
            algorithm = wiz.request.query("algorithm", "orca").lower()
            scenario = wiz.request.query("scenario", "medium")
            config = {
                "encounter_mode": wiz.request.query("encounter_mode", "baseline"),
                "population_mode": wiz.request.query("population_mode", "legacy"),
                "parameters": json.loads(wiz.request.query("parameters", "{}")),
                "algorithm_name": algorithm, "scenario_name": scenario,
                "strict_comparison": True,
                "common_traffic": wiz.request.query("common_traffic", "false") == "true",
                "render_fps": 10,
                "viewer_sync": True,
                "render_3d": wiz.request.query("render_3d", "true") == "true",
                "map_id": wiz.request.query("map_id", "map1"),
                "planner": wiz.request.query("planner", "astar"),
                "traffic_mode": wiz.request.query("traffic_mode", "dynamic"),
                "agent_count": int(wiz.request.query("agents", "4")),
                "seed": int(wiz.request.query("seed", "42")),
                "safety_distance": float(wiz.request.query("safety", ".35")),
                "robot_speed": float(wiz.request.query("speed", "1.2")),
                "frames": int(wiz.request.query("frames", "5400")),
            }
            if algorithm not in ("naive", "vo", "orca") or scenario not in ("easy", "medium", "hard", "crowded", "basic", "warehouse", "crossing", "multi_robot"):
                raise ValueError("지원하지 않는 알고리즘/환경입니다.")
            if not (0 <= config["agent_count"] <= 40 and 0 <= config["seed"] <= 999999
                    and 0 <= config["safety_distance"] <= 1 and .2 <= config["robot_speed"] <= 2
                    and 30 <= config["frames"] <= 10800):
                raise ValueError("에이전트·시드·안전거리·속도·프레임 범위를 확인하세요.")
            if config["planner"] not in ("astar","dijkstra","rrt") or config["traffic_mode"] not in ("static","dynamic"):
                raise ValueError("지원하지 않는 경로 탐색/작업자 모드입니다.")
            catalog = json.loads((root / "warehouse_maps.json").read_text())
            if config["map_id"] not in [m["mapId"] for m in catalog]:
                raise ValueError("지원하지 않는 선반 맵입니다.")
            if action == "load":
                record = json.loads(wiz.request.query("record", "{}"))
                if not record.get("frames") or not record["frames"][0].get("body_q"):
                    raise ValueError("3D 강체 상태가 없는 기록입니다. 다시 비교 실행하세요.")
                config["common_traffic"] = bool(record.get("common_traffic", False))
                config["record"] = record
            # Serialize admission across WIZ workers; at most four active viewers.
            with (sessions / ".lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                active = 0
                for pidfile in sessions.glob("*/pid"):
                    try:
                        pid = int(pidfile.read_text())
                        os.kill(pid, 0)
                        process_state = Path("/proc") / str(pid) / "stat"
                        if process_state.exists() and process_state.read_text().split(") ", 1)[1].startswith("Z"):
                            continue
                        active += 1
                    except (ProcessLookupError, ValueError):
                        pass
                if active >= 4:
                    raise ValueError("동시 Newton 뷰어 4개가 실행 중입니다. 기존 세션을 종료하거나 만료 후 재시도하세요.")
                token = uuid.uuid4().hex
                folder = sessions / token
                folder.mkdir(mode=0o700)
                (folder / "config.json").write_text(json.dumps(config))
                with (folder / "worker.log").open("w") as log:
                    process = subprocess.Popen(
                        [str(root / ".venv/bin/python"), str(root / "newton_live.py"), str(folder)],
                        cwd=root, stdout=log, stderr=log, start_new_session=True)
                created_process = process
                (folder / "pid").write_text(str(process.pid))
            deadline = time.monotonic() + 40
            while not (folder / "status.json").exists():
                if (folder / "error.json").exists():
                    raise RuntimeError(json.loads((folder / "error.json").read_text())["message"])
                if time.monotonic() > deadline:
                    raise RuntimeError("Newton 초기화 시간이 초과되었습니다.")
                time.sleep(.05)
        if not re.fullmatch(r"[a-f0-9]{32}", token):
            raise ValueError("올바른 세션 토큰이 필요합니다.")
        folder = sessions / token
        if not (folder / "status.json").exists():
            raise ValueError("세션을 찾을 수 없습니다.")
        if action not in ("create", "load", "status", "pause", "resume", "reset", "seek", "display", "close"):
            raise ValueError("지원하지 않는 제어입니다.")
        import importlib.util
        spec = importlib.util.spec_from_file_location("live_payload",str(root/"live_payload.py"))
        live_payload = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(live_payload)
        compact = wiz.request.query("compact","false") == "true"
        version = wiz.request.query("metadata_version","")
        since = int(wiz.request.query("since","-1"))
        presented=int(wiz.request.query("presented_frame","-1"))
        if presented>=0:
            state=json.loads((folder/"status.json").read_text())
            if version==state.get("metadata_version"):
                ack={"frame":min(presented,state["frame_count"]-1),"metadata_version":version}
                temporary=folder/(uuid.uuid4().hex+".acktmp")
                temporary.write_text(json.dumps(ack))
                os.replace(temporary,folder/"presented.json")

        if action == "status" and "metadata_version" in json.loads((folder/"status.json").read_text()):
            (folder/"heartbeat").touch()
            result = live_payload.read_snapshot(folder,since,compact,version)
            wiz.response.status(200,result)
        # Serialize control and polling for the same worker across requests/tabs.
        with (folder / ".command.lock").open("a") as command_lock:
            fcntl.flock(command_lock, fcntl.LOCK_EX)
            # Heartbeat is also a command so an abandoned process expires in 15 minutes.
            request_id = uuid.uuid4().hex
            command = {"id": request_id, "action": "touch" if action in ("create", "load", "status") else action}
            if action == "resume":
                start_at = float(wiz.request.query("start_at", "0"))
                if not 0 <= start_at <= time.time()+5:
                    raise ValueError("시작 예약 시간이 유효하지 않습니다.")
                command["start_at"] = start_at
            if action == "seek":
                command["frame"] = int(wiz.request.query("frame", "0"))
            if action == "display":
                command.update(path=wiz.request.query("path", "true") == "true",
                               risk=wiz.request.query("risk", "true") == "true",
                               render_3d=wiz.request.query("render_3d", "true") == "true")
            temporary = folder / (request_id + ".tmp")
            temporary.write_text(json.dumps(command))
            os.replace(temporary, folder / "command.json")
            if action == "close":
                # Release the viewer slot before a map change creates the next three workers.
                deadline = time.monotonic()+5
                while time.monotonic()<deadline:
                    try:
                        pid = int((folder/"pid").read_text())
                        os.kill(pid,0)
                        state = Path("/proc")/str(pid)/"stat"
                        if not state.exists() or state.read_text().split(") ",1)[1].startswith("Z"):
                            break
                    except (OSError,ValueError):
                        break
                    time.sleep(.02)
                result = {"token": token, "phase": "closed"}
            else:
                deadline = time.monotonic() + (10 if action == "reset" else 4)
                while True:
                    if (folder / "error.json").exists():
                        raise RuntimeError(json.loads((folder / "error.json").read_text())["message"])
                    result = json.loads((folder / "status.json").read_text())
                    if result["ack"] == request_id:
                        break
                    if time.monotonic() > deadline:
                        raise RuntimeError("Newton 제어 응답이 없습니다. 세션을 다시 시작하세요.")
                    time.sleep(.02)
                result = live_payload.read_snapshot(folder,since,compact,version,action in ("reset","create","load"))
    except (ValueError, TypeError, OSError, RuntimeError, KeyError) as error:
        if created_process is not None:
            created_process.terminate()
        wiz.response.status(400, message=str(error))
    wiz.response.status(200, result)
