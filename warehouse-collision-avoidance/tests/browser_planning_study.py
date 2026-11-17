"""Real browser controls, rotated obstacles and actual study tables/charts."""
import os,json,time
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
BASE=os.getenv("WAREHOUSE_BASE_URL","http://localhost:3000")
OUT=Path(os.getenv("WAREHOUSE_MAP_OUTPUT","/tmp/planning-study-browser"));OUT.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    b=p.chromium.launch(headless=True,**({"executable_path":os.environ["WAREHOUSE_CHROMIUM"]} if os.getenv("WAREHOUSE_CHROMIUM") else {}),args=["--no-sandbox","--enable-unsafe-swiftshader"])
    c=b.new_context(viewport={"width":1500,"height":1100})
    if "localhost" in BASE:c.add_cookies([{"name":"season-wiz-devmode","value":"true","domain":"localhost","path":"/"}])
    page=c.new_page();errors=[];latest={};tokens=set();checks=[]
    page.on("pageerror",lambda e:errors.append(str(e)))
    page.on("console",lambda m:errors.append(m.text) if m.type=="error" else None)
    def capture(r):
        if "live_newton" in r.url:
            try:
                data=r.json()["data"]
                if isinstance(data,dict) and "current" in data:latest.clear();latest.update(data);tokens.add(data["token"])
            except:pass
    page.on("response",capture)
    try:
        page.goto(BASE+"/algorithm?section=implementation&public=1")
        page.locator(".control-card select").nth(0).select_option("dijkstra")
        page.get_by_role("button",name="Map 6: Fishbone",exact=True).click()
        expect(page.locator(".mode-badge")).to_have_text("실시간 물리 정지",timeout=30000)
        assert latest["planner"]=="dijkstra" and latest["expanded_nodes"]>0
        assert latest["start"]==[2.5,13] and latest["goal"]==[35.5,13]
        page.get_by_role("button",name="2D Top View",exact=True).click()
        rects=page.locator("rect.shelf")
        assert rects.count()==6
        assert "45" in rects.first.get_attribute("transform")
        path=page.locator("polyline.planned").get_attribute("points")
        assert len(path.split())==len(latest["astar_path"])
        page.get_by_role("button",name="3D View",exact=True).click()
        viewer=page.frame_locator('iframe[title="Newton ViewerViser 3D Warehouse"]')
        viewer.locator("canvas[data-engine]").wait_for()
        page.locator(".control-card").get_by_role("button",name="Resume",exact=True).click()
        page.wait_for_timeout(1800)
        page.locator(".control-card").get_by_role("button",name="Pause",exact=True).click()
        expect(page.locator(".mode-badge")).to_have_text("실시간 물리 정지")
        expect(page.locator(".control-card").get_by_role("button",name="Start",exact=True)).to_be_enabled()
        page.wait_for_timeout(300)
        assert latest["phase"]=="paused"
        t=latest["current"]["t"];assert t>0
        page.wait_for_timeout(800);assert latest["current"]["t"]==t
        assert latest["current"]["robot"]==latest["current"]["body_q"][latest["bodies"][0]["body"]][:2]
        page.locator(".control-card").get_by_role("button",name="Reset",exact=True).click()
        expect(page.locator(".mode-badge")).to_have_text("실시간 물리 정지")
        expect(page.locator(".control-card").get_by_role("button",name="Start",exact=True)).to_be_enabled(timeout=30000)
        page.wait_for_timeout(300);assert latest["current"]["t"]==0 and latest["planner"]=="dijkstra"
        checks.append("Dijkstra dispatch, rotated 2D/3D, pose telemetry, Resume/Pause/Reset")
        print(checks[-1],flush=True)
        page.locator(".control-card select").nth(0).select_option("rrt")
        page.locator(".control-card").get_by_role("button",name="Start",exact=True).click()
        expect(page.locator(".mode-badge")).to_have_text("실시간 물리 실행",timeout=30000)
        page.locator(".control-card").get_by_role("button",name="Pause",exact=True).click()
        expect(page.locator(".control-card").get_by_role("button",name="Start",exact=True)).to_be_enabled()
        page.wait_for_timeout(300)
        assert latest["planner"]=="rrt" and latest["expanded_nodes"] is None and latest["iterations"]>0
        checks.append("RRT actual live dispatch")
        print("RRT dispatch verified",flush=True)
        page.reload()
        page.get_by_role("button",name="실험 결과",exact=True).click()
        section=page.locator(".planning-study")
        expect(section.locator("tbody tr")).to_have_count(18,timeout=30000)
        expect(section.locator(".planning-charts svg")).to_have_count(3)
        assert section.locator(".planning-charts rect").count()==54
        assert "N/A" in section.locator("tbody tr").filter(has_text="RRT").first.inner_text()
        row=section.locator("tbody tr").filter(has_text="Map 6: Fishbone / RRT")
        row.get_by_role("button").click()
        expect(section.locator(".study-path svg")).to_be_visible()
        assert section.locator(".study-path svg rect").count()==7
        assert section.locator(".study-path polyline").count()==2
        section.screenshot(path=str(OUT/"static-results.png"))
        section.locator("select").select_option("dynamic")
        expect(section.locator("tbody tr")).to_have_count(18)
        assert section.locator(".study-path").count()==0
        section.locator("tbody tr").filter(has_text="Map 6: Fishbone / RRT").get_by_role("button").click()
        section.screenshot(path=str(OUT/"dynamic-results.png"))
        checks.append("Measured static/dynamic 18 rows each, 3 charts, 54 bars, N/A and exact plan/trajectory diagrams")
        assert not errors,errors
        (OUT/"checks.json").write_text(json.dumps({"passed":True,"checks":checks,"errors":errors},indent=2))
        print("PASS",checks,flush=True)
    finally:
        for token in tokens:
            try:c.request.post(BASE+"/wiz/api/page.algorithm.run/live_newton",form={"action":"close","token":token})
            except:pass
        b.close()
