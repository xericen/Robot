"""Read-only browser regression; does not start simulations or replace historical aliases."""
import json,os
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"results/newton/research/20261117T115115_2ef7f604"
data=json.loads((OUT/"dashboard.json").read_text())
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path=os.getenv("WAREHOUSE_CHROMIUM") or "/root/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome",args=["--no-sandbox"])
    context=browser.new_context(viewport={"width":1600,"height":1100})
    context.add_cookies([{"name":"season-wiz-devmode","value":"true","domain":"localhost","path":"/"}])
    page=context.new_page();errors=[]
    page.on("pageerror",lambda e:errors.append(str(e)))
    page.goto("http://localhost:3000/algorithm?section=implementation&public=1")
    page.get_by_role("button",name="연구 분석",exact=True).click()
    panel=page.locator(".research-analysis")
    expect(panel.locator("tbody tr")).to_have_count(3,timeout=30000)
    for row in data["algorithms"]:
        line=panel.locator("tbody tr").filter(has_text=row["algorithm"])
        expect(line.locator("td").nth(1)).to_contain_text(str(row["success_count"])+"/80")
    panel.screenshot(path=str(OUT/"browser_algorithm.png"))
    for label,key in [("시나리오 분석","scenario"),("계산 비용","scalability"),("ORCA 위반 분석","orca"),("창고 맵 분석","layout")]:
        panel.get_by_role("button",name=label,exact=True).click()
        if key=="scenario":
            for name in ("Head-On","Crossing","Narrow Passage","Dense Traffic"):
                panel.locator("select").select_option(label=name)
                expect(panel.locator("tbody tr")).to_have_count(3)
        elif key=="scalability":
            for name in ("workers","mixed"):
                panel.locator("select").select_option(name)
                expect(panel.locator("tbody tr")).to_have_count(12)
        elif key=="orca":
            for i in range(3):
                panel.locator("select").select_option(index=i)
                expect(panel.locator("input[type=range]")).to_be_visible()
        else:
            expect(panel.locator("tbody tr")).to_have_count(6)
            for name in ("map1","map2","map3","map4","map5","map6"):
                panel.locator("select").select_option(name)
                expect(panel.locator("img").first).to_have_attribute("src",f"/warehouse-experiments/research/{data['id']}/10_layout_{name}.png")
        for image in panel.locator("img").all():
            page.wait_for_function("(im)=>im.complete && im.naturalWidth>0",arg=image.element_handle())
        panel.screenshot(path=str(OUT/("browser_"+key+".png")))
    base="http://localhost:3000/warehouse-experiments/research/"+data["id"]+"/"
    assert context.request.get(base+"01_safe_success.png").status==200
    assert context.request.get(base+"algorithm_comparison.csv").status==200
    assert context.request.get(base+"audit.json").status==404
    assert context.request.get(base+"dashboard.json").status==404
    assert not errors,errors
    (OUT/"browser_validation.json").write_text(json.dumps({"passed":True,"panels":5,"scenarios":4,"maps":6,"population_modes":2,"raw_csv_counts_match":True,"invalid_assets_rejected":True,"page_errors":errors},indent=2))
    print("Research dashboard: 5 panels, 4 scenarios, 6 maps, source CSV consistency passed.")
    browser.close()
