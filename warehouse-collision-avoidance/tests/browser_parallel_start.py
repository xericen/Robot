"""Actual 3-process/3-viewer test on all six maps; close only sessions created by this test."""
import json,time,uuid
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"results/newton/validation"/("parallel_"+uuid.uuid4().hex[:8])
OUT.mkdir(parents=True)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path="/root/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome",args=["--no-sandbox"])
    context=browser.new_context(viewport={"width":1800,"height":1200})
    context.add_cookies([{"name":"season-wiz-devmode","value":"true","domain":"localhost","path":"/"}])
    page=context.new_page();errors=[];created=[];latest={}
    page.on("pageerror",lambda error:errors.append(str(error)))
    def response_seen(response):
        if response.url.endswith("/page.algorithm.run/live_newton") and response.request.post_data and "action=create" in response.request.post_data:
            try:
                body=response.json()
                if body["code"]==200:
                    d=body["data"];created.append(d["token"]);latest[d["algorithm"]]=d
            except Exception:pass
    page.on("response",response_seen)
    def rpc(token,action="status"):
        response=context.request.post("http://localhost:3000/wiz/api/page.algorithm.run/live_newton",
            form={"action":action,"token":token,"since":"-1"},timeout=60000)
        body=response.json()
        assert body["code"]==200,body
        return body["data"]
    results=[]
    try:
        page.goto("http://localhost:3000/algorithm?section=implementation&public=1")
        page.get_by_role("button",name="Start · 3개 알고리즘 함께",exact=True).click()
        comparison=page.locator(".parallel-comparison")
        expect(comparison.locator(".parallel-run iframe")).to_have_count(3,timeout=120000)
        expect(comparison.locator(".parallel-run").first.locator("header span")).to_have_text("running",timeout=60000)
        assert len(latest)==3,latest
        first=[rpc(d["token"]) for d in latest.values()]
        assert len({d["scene_hash"] for d in first})==1
        assert all(d["encounter_mode"]=="crossing" and d["worker_count"]==4 for d in first)
        # The three 3D iframes load actual Viser clients.
        for iframe in comparison.locator("iframe").all():
            frame=iframe.content_frame
            expect(frame.locator("canvas").first).to_be_visible(timeout=60000)
        comparison.screenshot(path=str(OUT/"three_algorithms_3d.png"))
        comparison.get_by_role("button",name="2D 나란히 보기",exact=True).click()
        expect(comparison.locator(".parallel-run svg:visible")).to_have_count(3)
        for number in range(1,7):
            map_id=f"map{number}"
            if number>1:
                comparison.locator(".map-buttons button").nth(number-1).click()
                expect(comparison.locator(".parallel-run").first.locator("header span")).to_have_text("paused",timeout=120000)
                # Complete creation of all three before reading the group.
                expect(comparison.get_by_role("button",name="함께 Resume",exact=True)).to_be_enabled(timeout=120000)
                comparison.get_by_role("button",name="함께 Resume",exact=True).click()
                expect(comparison.locator(".parallel-run").first.locator("header span")).to_have_text("running",timeout=60000)
            statuses=[rpc(d["token"]) for d in latest.values()]
            deadline=time.monotonic()+30
            while not all(s["frame_count"]>5 for s in statuses) and time.monotonic()<deadline:
                page.wait_for_timeout(150)
                statuses=[rpc(d["token"]) for d in latest.values()]
            assert all(s["frame_count"]>5 for s in statuses),statuses
            assert len(statuses)==3 and all(s["mapId"]==map_id for s in statuses)
            assert len({s["scene_hash"] for s in statuses})==1
            assert {s["algorithm"] for s in statuses}=={"Naive","VO","ORCA"}
            comparison.get_by_role("button",name="함께 Pause",exact=True).click()
            expect(comparison.locator(".parallel-run").first.locator("header span")).to_have_text("paused",timeout=60000)
            paused=[rpc(d["token"]) for d in latest.values()]
            times=[s["current"]["t"] for s in paused]
            page.wait_for_timeout(300)
            assert times==[rpc(d["token"])["current"]["t"] for d in latest.values()]
            assert all(s["worker_count"]==4 and len(s["encounter"]["actors"])==4 for s in paused)
            results.append({"map":map_id,"algorithms":[s["algorithm"] for s in paused],"same_scene":True,"pause_times":times,
                            "worker_ids":[a["id"] for a in paused[0]["encounter"]["actors"]]})
            comparison.screenshot(path=str(OUT/(map_id+"_three_algorithms_2d.png")))
        comparison.get_by_role("button",name="함께 Reset",exact=True).click()
        expect(comparison.get_by_role("button",name="함께 Resume",exact=True)).to_be_enabled(timeout=60000)
        reset=[rpc(d["token"]) for d in latest.values()]
        assert all(s["frame_index"]==0 and s["phase"]=="paused" for s in reset)
        comparison.get_by_role("button",name="동시 비교 종료",exact=True).click()
        expect(comparison).to_have_count(0,timeout=30000)
        assert not errors,errors
        (OUT/"browser_validation.json").write_text(json.dumps({"passed":True,"maps":results,"created_sessions":len(created),
            "three_viser_canvases_loaded":True,"group_reset":True,"page_errors":errors},ensure_ascii=False,indent=2))
        print("PASS",OUT)
    finally:
        for token in created:
            try:rpc(token,"close")
            except Exception:pass
        browser.close()
