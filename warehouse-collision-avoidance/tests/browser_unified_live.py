"""Actual live bridge obeys the same explicit contract and frame limit as batch runs."""
import csv,json,os,sys,time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from unified_batch import CONTRACT
BASE=os.getenv("WAREHOUSE_BASE_URL","http://localhost:3000")
BATCH=os.environ["WAREHOUSE_BATCH_ID"]
with sync_playwright() as p:
    request=p.request.new_context(base_url=BASE,extra_http_headers={"Cookie":"season-wiz-devmode=true"})
    token=None
    def call(action,**data):
        r=request.post("/wiz/api/page.algorithm.run/live_newton",form={"action":action,**data}).json()
        assert r["code"]==200,r
        return r["data"]
    try:
        c=CONTRACT
        live=call("create",algorithm="orca",scenario=c["scenario"],agents=str(c["agent_count"]),seed="42",
                  safety=str(c["safety"]),speed=str(c["speed"]),frames="30",map_id="map1",planner=c["planner"],
                  traffic_mode=c["traffic_mode"],encounter_mode=c["encounter_mode"],population_mode=c["population_mode"],
                  common_traffic="false",parameters=json.dumps(c["parameters"]),render_3d="false")
        token=live["token"]
        row=next(r for r in csv.DictReader((ROOT/"results/newton/studies"/BATCH/"measurements.csv").open())
                 if r["map"]=="map1" and r["algorithm"]=="ORCA" and int(r["seed"])==42)
        assert live["scene_hash"]==row["scene_hash"]
        assert live["encounter_mode"]=="crossing" and live["population_mode"]=="workers"
        assert live["frame_limit"]==30 and not live["frame_budget_extended"]
        call("resume",token=token)
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            time.sleep(.2);live=call("status",token=token)
            if live["phase"]=="replay_paused":break
        assert live["status"]=="timeout" and live["frame_limit"]==30 and live["sim_time_s"]<=1.001,live
        result={"passed":True,"batch_id":BATCH,"same_scene_hash":row["scene_hash"],"explicit_crossing_workers":True,
                "strict_live_frame_limit":30,"observed_time_s":live["sim_time_s"],"no_silent_extension":True}
        Path("/tmp/unified-live-check.json").write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
    finally:
        if token:call("close",token=token)
        request.dispose()
