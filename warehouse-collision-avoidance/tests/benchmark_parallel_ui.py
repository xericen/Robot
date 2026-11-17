"""Short real-browser delivery benchmark; no fabricated experiment outcomes."""
import json,sys,time,uuid
from pathlib import Path
from urllib.parse import parse_qs
from playwright.sync_api import sync_playwright,expect
OUT=Path(__file__).resolve().parents[1]/"results/newton/validation"/("lag_"+sys.argv[1]+"_"+uuid.uuid4().hex[:8])
OUT.mkdir(parents=True)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path="/root/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome",args=["--no-sandbox"])
    context=browser.new_context(viewport={"width":1600,"height":1100})
    context.add_cookies([{"name":"season-wiz-devmode","value":"true","domain":"localhost","path":"/"}])
    page=context.new_page();tokens=[];measurements=[];collect=False;last={}
    def response_seen(response):
        global collect
        if not response.url.endswith("/page.algorithm.run/live_newton"):return
        q=parse_qs(response.request.post_data or "")
        try:
            body=response.json()
            if body["code"]!=200:return
            d=body["data"]
            if q.get("action")==["create"]:tokens.append(d["token"])
            if q.get("action")==["status"]:
                last[d["token"]]=d["current"]["t"]
                if collect:measurements.append({"bytes":len(response.body()),"ms":response.request.timing["responseEnd"]-response.request.timing["requestStart"]})
        except Exception:pass
    page.on("response",response_seen)
    try:
        page.goto("http://localhost:3000/algorithm?section=implementation&public=1")
        page.get_by_role("button",name="Start · 3개 알고리즘 함께",exact=True).click()
        panel=page.locator(".parallel-comparison")
        expect(panel.locator(".parallel-run").first.locator("header span")).to_have_text("running",timeout=120000)
        for mode in ("2d","3d"):
            panel.get_by_role("button",name=("2D 나란히 보기" if mode=="2d" else "3D 나란히 보기"),exact=True).click()
            page.wait_for_timeout(2000)
            before=dict(last);measurements.clear();collect=True
            page.wait_for_timeout(6000)
            collect=False
            result={"mode":mode,"window_s":6,"status_responses":len(measurements),
                "total_status_bytes":sum(r["bytes"] for r in measurements),
                "mean_status_bytes":sum(r["bytes"] for r in measurements)/max(1,len(measurements)),
                "mean_status_request_ms":sum(r["ms"] for r in measurements)/max(1,len(measurements)),
                "simulation_advance_s":{t:last[t]-before.get(t,last[t]) for t in last},
                "mounted_iframes":panel.locator("iframe").count()}
            (OUT/(mode+".json")).write_text(json.dumps(result,indent=2))
        panel.get_by_role("button",name="동시 비교 종료",exact=True).click()
        expect(panel).to_have_count(0,timeout=30000)
        print(OUT,flush=True)
    finally:
        for token in tokens:
            try:context.request.post("http://localhost:3000/wiz/api/page.algorithm.run/live_newton",form={"token":token,"action":"close"},timeout=10000)
            except Exception:pass
        browser.close()
