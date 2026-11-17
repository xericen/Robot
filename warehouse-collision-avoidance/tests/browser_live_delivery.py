"""One real live viewer, compact polling, 3D removal, reset revisions, no state mutation by reads."""
import json,time,uuid
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/"results/newton/validation"/("delivery_"+uuid.uuid4().hex[:8]);OUT.mkdir(parents=True)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path="/root/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome",args=["--no-sandbox"])
    context=browser.new_context(viewport={"width":1600,"height":1100})
    context.add_cookies([{"name":"season-wiz-devmode","value":"true","domain":"localhost","path":"/"}])
    page=context.new_page();tokens=[];errors=[];compact=[]
    page.on("pageerror",lambda e:errors.append(str(e)))
    def seen(response):
        if response.url.endswith("/page.algorithm.run/live_newton"):
            try:
                body=response.json()
                if body["code"]==200:
                    d=body["data"];q=response.request.post_data or ""
                    if "action=create" in q:tokens.append(d["token"])
                    if "action=status" in q:compact.append(d)
            except Exception:pass
    page.on("response",seen)
    def rpc(action,**extra):
        r=context.request.post("http://localhost:3000/wiz/api/page.algorithm.run/live_newton",
            form={"action":action,"token":tokens[-1],"since":"-1",**extra},timeout=30000).json()
        assert r["code"]==200,r
        return r["data"]
    try:
        page.goto("http://localhost:3000/algorithm?section=implementation&public=1")
        page.get_by_role("button",name="선택 알고리즘만 Start",exact=True).click()
        expect(page.locator(".viser-view iframe")).to_have_count(1,timeout=60000)
        frame=page.locator(".viser-view iframe").content_frame
        expect(frame.locator("canvas").first).to_be_visible(timeout=60000)
        page.wait_for_timeout(1200)
        first=rpc("status");assert first["render_fps"]==10 and first["render_3d"]
        page.get_by_role("button",name="2D Top View",exact=True).click()
        expect(page.locator(".viser-view iframe")).to_have_count(0)
        page.wait_for_timeout(600)
        state=rpc("status");assert not state["render_3d"]
        expect(page.locator(".warehouse-view svg")).to_be_visible()
        folder=ROOT/"results/live"/tokens[-1]
        command_before=(folder/"command.json").stat().st_mtime_ns
        for _ in range(3):rpc("status")
        assert (folder/"command.json").stat().st_mtime_ns==command_before
        assert (folder/"heartbeat").is_file()
        page.get_by_role("button",name="Pause",exact=True).click()
        page.wait_for_timeout(300);paused=rpc("status");assert paused["phase"]=="paused"
        before=paused["metadata_version"]
        page.get_by_role("button",name="Reset",exact=True).click()
        page.wait_for_timeout(700);reset=rpc("status")
        assert reset["frame_index"]==0 and reset["metadata_version"]!=before
        page.get_by_role("button",name="3D View",exact=True).click()
        expect(page.locator(".viser-view iframe")).to_have_count(1)
        expect(page.locator(".viser-view iframe").content_frame.locator("canvas").first).to_be_visible(timeout=60000)
        page.wait_for_timeout(300)
        assert rpc("status")["render_3d"]
        assert any("algorithm" not in d and "metadata_version" in d for d in compact)
        assert all("provenance" not in d and "algorithm_samples_ms" not in d for d in compact)
        assert not errors,errors
        page.locator(".unified-dashboard").screenshot(path=str(OUT/"optimized_view.png"))
        (OUT/"browser_validation.json").write_text(json.dumps({"passed":True,"single_live_viewer":True,"render_fps":10,
            "hidden_3d_unmounted":True,"compact_metadata_not_repeated":True,"status_does_not_write_commands":True,
            "reset_revision_refreshed":True,"page_errors":errors},indent=2))
        print(OUT,flush=True)
    finally:
        for token in tokens:
            try:context.request.post("http://localhost:3000/wiz/api/page.algorithm.run/live_newton",form={"token":token,"action":"close"},timeout=10000)
            except Exception:pass
        browser.close()
