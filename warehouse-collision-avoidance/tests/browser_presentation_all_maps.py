"""Six real 3D triplets; delayed Map2 VO load and blocked dashboard regression."""
import json,re,time,uuid,threading
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"results/newton/validation"/("presentation_"+uuid.uuid4().hex[:8]);OUT.mkdir(parents=True)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path="/root/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome",args=["--no-sandbox"])
    context=browser.new_context(viewport={"width":1800,"height":1300})
    context.add_cookies([{"name":"season-wiz-devmode","value":"true","domain":"localhost","path":"/"}])
    page=context.new_page();created=[];latest={};errors=[];binary=[];delayed=[]
    page.on("pageerror",lambda e:errors.append(str(e)))
    def seen(response):
        if "/warehouse-viewer/" in response.url and "/poll/" in response.url and response.status==200:
            binary.append(response.headers.get("content-type",""))
        if response.url.endswith("/page.algorithm.run/live_newton"):
            try:
                d=response.json()
                if d["code"]==200 and "action=create" in (response.request.post_data or ""):
                    created.append(d["data"]["token"]);latest[d["data"]["algorithm"]]=d["data"]
            except Exception:pass
    context.on("response",seen)
    def statuses():
        return [json.loads((ROOT/"results/live"/d["token"]/"status.json").read_text()) for d in latest.values()]
    def delay_vo(route):
        tail=route.request.url.split("/warehouse-viewer/",1)[-1].split("?",1)[0].strip("/")
        if "/" in tail:
            route.continue_();return
        token=tail
        try:
            cfg=json.loads((ROOT/"results/live"/token/"config.json").read_text())
            d={"algorithm":cfg["algorithm_name"].upper(),"mapId":cfg["map_id"]}
        except (OSError,ValueError,KeyError):d=None
        if d and d["algorithm"]=="VO" and d["mapId"]=="map2":
            folders=[p.parent for p in (ROOT/"results/live").glob("*/config.json")
                     if p.stat().st_mtime>=started and json.loads(p.read_text()).get("map_id")=="map2"]
            before=[json.loads((f/"status.json").read_text())["frame_index"] for f in folders if (f/"status.json").exists()]
            time.sleep(2)
            after=[json.loads((f/"status.json").read_text())["frame_index"] for f in folders if (f/"status.json").exists()]
            assert len(after)==3 and all(x==0 for x in before+after),(before,after)
            delayed.append({"map":"map2","delay_s":2,"before":before,"after":after})
        route.continue_()
    started=time.time()
    page.route("**/warehouse-viewer/**",delay_vo)
    try:
        page.goto("http://localhost:3000/algorithm?section=implementation&public=1")
        page.evaluate("""() => {
          window.frameSamples=[];
          new MutationObserver(records=>{for(const r of records)if(r.type==='attributes'){
            const el=r.target;window.frameSamples.push({map:el.dataset.map,algorithm:el.dataset.algorithm,t:Number(el.dataset.frame),wall:performance.now()});
          }}).observe(document.body,{subtree:true,attributes:true,attributeFilter:['data-frame']});
        }""")
        page.get_by_label("동시 실행 시작 화면",exact=True).select_option("3d")
        page.get_by_role("button",name="Start · 3개 알고리즘 함께",exact=True).click()
        panel=page.locator(".parallel-comparison")
        expect(panel.get_by_role("button",name="함께 Pause",exact=True)).to_be_enabled(timeout=90000)
        panel.get_by_role("button",name="3D 나란히 보기",exact=True).click()
        results=[]
        for number in range(1,7):
            if number>1:
                panel.locator(".map-buttons button").nth(number-1).click()
            expect(panel.get_by_role("button",name="함께 Resume",exact=True)).to_be_enabled(timeout=90000)
            expect(panel.locator("iframe")).to_have_count(3,timeout=60000)
            deadline=time.monotonic()+60
            while not all(s.get("viewer_ready") for s in statuses()) and time.monotonic()<deadline:page.wait_for_timeout(100)
            state=statuses();assert all(s["viewer_ready"] for s in state),state
            if number==1:
                token=next(iter(latest.values()))["token"]
                base="http://localhost:3000/warehouse-viewer/"+token+"/bridge/"
                probe=context.request.post(base+"open").json()["id"]
                response=context.request.post(base+"poll/"+probe,headers={"X-Warehouse-Binary":"1"})
                assert response.status==200
                assert "application/octet-stream" in response.headers["content-type"]
                binary.append(response.headers["content-type"])
                context.request.post(base+"close/"+probe)
            if number>1:
                assert all(s["frame_index"]==0 for s in state),state
                panel.get_by_role("button",name="함께 Resume",exact=True).click()
            deadline=time.monotonic()+30
            while min(s["frame_index"] for s in statuses())<12 and time.monotonic()<deadline:page.wait_for_timeout(150)
            state=statuses();assert min(s["frame_index"] for s in state)>=12,state
            if number==2:
                blocked=[]
                def sample_block():
                    time.sleep(.45)
                    for d in latest.values():
                        folder=ROOT/"results/live"/d["token"]
                        s=json.loads((folder/"status.json").read_text())
                        ack=json.loads((folder/"presented.json").read_text())
                        blocked.append({"frame":s["frame_index"],"presented":ack["frame"]})
                thread=threading.Thread(target=sample_block);thread.start()
                page.evaluate("() => {const until=performance.now()+1000;while(performance.now()<until){};}")
                thread.join()
                assert all(x["frame"]-x["presented"]<=6 for x in blocked),blocked
                (OUT/"blocked_dashboard.json").write_text(json.dumps(blocked,indent=2))
            panel.get_by_role("button",name="함께 Pause",exact=True).click()
            expect(panel.get_by_role("button",name="함께 Resume",exact=True)).to_be_enabled(timeout=60000)
            state=statuses()
            assert all(s["phase"]=="paused" for s in state)
            assert all(s["frame_index"]-s["rendered_frame"]<=6 for s in state),state
            for iframe in panel.locator("iframe").all():
                expect(iframe.content_frame.locator("canvas").first).to_be_visible(timeout=30000)
            panel.screenshot(path=str(OUT/(f"map{number}_3d.png")))
            print("validated",number,flush=True)
            results.append({"map":f"map{number}","frames":[s["frame_index"] for s in state],"rendered":[s["rendered_frame"] for s in state],"ready":True})
        samples=page.evaluate("window.frameSamples")
        for key in {(x.get("map"),x.get("algorithm")) for x in samples}:
            seq=[x["t"] for x in samples if (x.get("map"),x.get("algorithm"))==key]
            assert all(b-a<=.20001 for a,b in zip(seq,seq[1:])),(key,seq)
        (OUT/"observations.json").write_text(json.dumps({"delayed":delayed,"binary":binary[:5],"results":results},indent=2))
        assert delayed and any("application/octet-stream" in x for x in binary)
        assert not errors,errors
        (OUT/"browser_validation.json").write_text(json.dumps({"passed":True,"maps":results,"delayed_vo":delayed,"binary_polls":len(binary),"display_samples":len(samples),"page_errors":errors},indent=2))
        print("PASS",OUT,flush=True)
    finally:
        for token in created:
            try:context.request.post("http://localhost:3000/wiz/api/page.algorithm.run/live_newton",form={"action":"close","token":token},timeout=10000)
            except Exception:pass
        browser.close()
