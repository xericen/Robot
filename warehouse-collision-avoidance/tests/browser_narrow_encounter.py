"""Render the actual Newton narrow-passage scene in Viser and the synchronized 2D projection."""
import json,os
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

OUT=Path(__file__).resolve().parents[1]/"results/newton/validation/controlled"
OUT.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    b=p.chromium.launch(headless=True,executable_path=os.getenv("WAREHOUSE_CHROMIUM") or p.chromium.executable_path,
                        args=["--no-sandbox","--enable-unsafe-swiftshader"])
    c=b.new_context(viewport={"width":1500,"height":1050})
    c.add_cookies([{"name":"season-wiz-devmode","value":"true","domain":"localhost","path":"/"}])
    page=c.new_page();data={};errors=[]
    page.on("pageerror",lambda e:errors.append(str(e)))
    def receive(response):
        if "live_newton" not in response.url:return
        try:
            value=response.json().get("data",{})
            if isinstance(value,dict) and "current" in value:data.clear();data.update(value)
        except ValueError:pass
    page.on("response",receive)
    try:
        page.goto("http://localhost:3000/algorithm?section=implementation&public=1")
        page.get_by_role("button",name="환경 설정",exact=True).click()
        page.get_by_label("만남 조건",exact=True).select_option("narrow_passing")
        page.get_by_role("button",name="시뮬레이션",exact=True).click()
        page.get_by_role("button",name="Map 1: Standard",exact=True).click()
        expect(page.locator(".mode-badge")).to_have_text("실시간 물리 정지",timeout=40000)
        page.frame_locator('iframe[title="Newton ViewerViser 3D Warehouse"]').locator("canvas[data-engine]").wait_for(timeout=30000)
        page.locator(".viewer-card").screenshot(path=str(OUT/"narrow-3d.png"))
        assert data["encounter_mode"]=="narrow_passing" and len(data["shelf_poses"])==8
        assert sum(s.get("kind")=="barrier" for s in data["shelf_poses"])==2
        assert data["encounter"]["passage_width_m"]==2.8 and len(data["encounter"]["actors"])==4
        page.get_by_role("button",name="2D Top View",exact=True).click()
        expect(page.locator("rect.shelf")).to_have_count(8)
        page.locator(".viewer-card").screenshot(path=str(OUT/"narrow-2d.png"))
        assert not errors,errors
        page.get_by_role("button",name="환경 설정",exact=True).click()
        page.get_by_label("만남 조건",exact=True).select_option("head_on")
        expect(page.get_by_role("button",name="설정으로 실행",exact=True)).to_be_enabled(timeout=30000)
        assert data["encounter_mode"]=="head_on" and len(data["shelf_poses"])==6
        page.get_by_label("만남 조건",exact=True).select_option("narrow_passing")
        expect(page.get_by_role("button",name="설정으로 실행",exact=True)).to_be_enabled(timeout=30000)
        assert data["encounter_mode"]=="narrow_passing" and len(data["shelf_poses"])==8
        result={"passed":True,"live_condition_switch":True,"racks":6,"physical_barriers":2,"two_dimensional_obstacles":8,
                "actors":4,"passage_width_m":2.8,"phase":data["phase"],"page_errors":errors}
        (OUT/"narrow-browser.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
        print(result)
    finally:
        if data.get("token"):c.request.post("http://localhost:3000/wiz/api/page.algorithm.run/live_newton",form={"action":"close","token":data["token"]})
        b.close()
