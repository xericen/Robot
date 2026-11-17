"""Real six-map Naive/VO/ORCA comparison and recorded-map replay regression."""
import os,json,math
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
BASE=os.getenv("WAREHOUSE_BASE_URL","http://localhost:3000")
OUT=Path(os.getenv("WAREHOUSE_COMPARE_OUTPUT","/tmp/warehouse-six-map-comparison"));OUT.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    b=p.chromium.launch(headless=True,**({"executable_path":os.environ["WAREHOUSE_CHROMIUM"]} if os.getenv("WAREHOUSE_CHROMIUM") else {}),args=["--no-sandbox","--enable-unsafe-swiftshader"])
    c=b.new_context(viewport={"width":1500,"height":1100})
    if "localhost" in BASE:c.add_cookies([{"name":"season-wiz-devmode","value":"true","domain":"localhost","path":"/"}])
    page=c.new_page();errors=[];batches=[];live={};tokens=set()
    page.on("pageerror",lambda e:errors.append(str(e)))
    page.on("console",lambda m:errors.append(m.text) if m.type=="error" else None)
    def response(r):
        if "page.algorithm.run" not in r.url:return
        try:data=r.json()
        except:return
        if data.get("code")!=200:return
        payload=data.get("data")
        if "run_newton" in r.url and isinstance(payload,list):
            batches.append(payload);(OUT/"captured-batches.json").write_text(json.dumps(batches,ensure_ascii=False));print("Received",payload[0]["mapId"],len(payload),flush=True)
        if "live_newton" in r.url and isinstance(payload,dict) and "current" in payload:
            live.clear();live.update(payload);tokens.add(payload["token"])
    page.on("response",response)
    try:
        page.goto(BASE+"/algorithm?section=implementation&public=1")
        page.get_by_role("button",name="환경 설정",exact=True).click()
        page.locator(".settings-grid input").last.fill("3600")
        page.get_by_role("button",name="알고리즘 비교",exact=True).click()
        expect(page.get_by_label("비교 범위",exact=True)).to_have_value("all")
        page.get_by_role("button",name="6개 맵 · 18조건 비교 실행",exact=True).click()
        expect(page.locator(".unified-dashboard > .status")).to_contain_text("18건.",timeout=600000)
        expect(page.locator(".unified-dashboard .table-scroll tbody tr")).to_have_count(18)
        rows=[r for batch in batches for r in batch]
        assert len(rows)==18
        assert {(r["mapId"],r["algorithm"]) for r in rows}=={(f"map{i}",a) for i in range(1,7) for a in ["Naive","VO","ORCA"]}
        for row in rows:
            assert row["worker_count"]==4 and row["common_traffic"] and row["planner"]=="astar"
            assert row["start"]==[2.5,13] and row["goal"]==[35.5,13]
            assert row["status"] in ("success","timeout")
            assert len(row["shelf_poses"])==6
        (OUT/"full-records.json").write_text(json.dumps(rows,ensure_ascii=False))
        keys=["mapId","mapName","algorithm","status","sim_time_s","path_length_m","collisions","safety_violations","goal_distance_m","common_traffic","planner","worker_count"]
        summary=[{k:r[k] for k in keys} for r in rows]
        (OUT/"measurements.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2))
        page.locator(".unified-dashboard .table-scroll").screenshot(path=str(OUT/"all-map-results.png"))
        for map_id in ("map6","map1"):
            row=page.locator(".unified-dashboard .table-scroll tbody tr").filter(has_text="Map 6: Fishbone" if map_id=="map6" else "Map 1: Standard").filter(has_text="ORCA")
            row.get_by_role("button",name="ORCA",exact=True).click()
            expect(page.locator(".mode-badge")).to_have_text("저장 기록 정지",timeout=30000)
            expect(page.locator(".control-card").get_by_role("button",name="Start",exact=True)).to_be_enabled(timeout=30000)
            assert live["mapId"]==map_id and live["common_traffic"]
            viewer=page.frame_locator('iframe[title="Newton ViewerViser 3D Warehouse"]')
            viewer.locator("canvas[data-engine]").wait_for()
            if map_id=="map6":page.locator(".viewer-card").screenshot(path=str(OUT/"fishbone-replay.png"))
            if map_id=="map1":
                page.locator(".control-card").get_by_role("button",name="Reset",exact=True).click()
                expect(page.locator(".control-card").get_by_role("button",name="Start",exact=True)).to_be_enabled(timeout=30000)
                page.wait_for_timeout(300)
                assert live["phase"]=="paused" and live["current"]["t"]==0 and live["common_traffic"]
                assert live["current"]["workers"]==[[35,3],[3,23],[35,23],[3,3]]
            page.get_by_role("button",name="알고리즘 비교",exact=True).click()
            expect(page.locator(".unified-dashboard .table-scroll tbody tr")).to_have_count(18)
        # The old selected-map action remains available; short run must report timeout.
        page.get_by_role("button",name="환경 설정",exact=True).click()
        page.locator(".settings-grid input").last.fill("30")
        page.get_by_role("button",name="알고리즘 비교",exact=True).click()
        page.get_by_label("비교 범위",exact=True).select_option("selected")
        page.get_by_role("button",name="선택 맵 · 세 알고리즘 실행",exact=True).click()
        expect(page.locator(".unified-dashboard > .status")).to_contain_text("3건.",timeout=60000)
        expect(page.locator(".unified-dashboard .table-scroll tbody tr")).to_have_count(3)
        assert len(batches)==7 and all(r["mapId"]=="map1" and r["status"]=="timeout" for r in batches[-1])
        page.get_by_role("button",name="실험 결과",exact=True).click()
        assert page.locator(".unified-dashboard .summary-grid article").count()>=21
        assert not errors,errors
        checks={"passed":True,"six_map_conditions":18,"all_map_methods":3,"replay_maps":["map6","map1"],"reset_common_spawns":True,"single_map_preserved":True,"previous_results_retained":True,"errors":errors}
        (OUT/"checks.json").write_text(json.dumps(checks,indent=2))
        print("PASS",checks,flush=True)
    finally:
        for token in tokens:
            try:c.request.post(BASE+"/wiz/api/page.algorithm.run/live_newton",form={"action":"close","token":token})
            except:pass
        b.close()
