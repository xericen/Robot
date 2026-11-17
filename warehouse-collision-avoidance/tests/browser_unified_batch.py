"""All three views must present the same verified study and the same ninety original run IDs."""
import csv,io,json,os
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
BASE=os.getenv("WAREHOUSE_BASE_URL","http://localhost:3000")
BATCH=os.environ["WAREHOUSE_BATCH_ID"]
OUT=Path(os.getenv("WAREHOUSE_UNIFIED_OUTPUT","/tmp/unified-batch-browser"));OUT.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    b=p.chromium.launch(headless=True,**({"executable_path":os.environ["WAREHOUSE_CHROMIUM"]} if os.getenv("WAREHOUSE_CHROMIUM") else {}),args=["--no-sandbox","--enable-unsafe-swiftshader"])
    c=b.new_context(viewport={"width":1500,"height":1100})
    if "localhost" in BASE:c.add_cookies([{"name":"season-wiz-devmode","value":"true","domain":"localhost","path":"/"}])
    page=c.new_page();errors=[]
    page.on("pageerror",lambda e:errors.append(str(e)))
    page.on("console",lambda m:errors.append(m.text) if m.type=="error" else None)
    try:
        page.goto(BASE+"/algorithm?section=implementation&public=1")
        expect(page.locator(".unified-batch")).to_contain_text(BATCH,timeout=30000)
        expect(page.get_by_label("공통 실험 배치",exact=True)).to_have_value(BATCH)
        page.get_by_role("button",name="알고리즘 비교",exact=True).click()
        panel=page.locator('.unified-dashboard section[data-source-batch="'+BATCH+'"]')
        expect(panel.locator(".table-scroll tbody tr")).to_have_count(90,timeout=30000)
        assert len(set(panel.locator(".table-scroll tbody tr td:first-child").all_text_contents()))==6
        panel.locator(".chart-grid").screenshot(path=str(OUT/"comparison.png"))
        page.get_by_role("button",name="실험 결과",exact=True).click()
        result=page.locator(".unified-results")
        expect(result).to_have_attribute("data-source-batch",BATCH)
        expect(result.locator("tbody tr")).to_have_count(3)
        for row in result.locator("tbody tr").all():assert "/ 30" in row.inner_text()
        for image in result.locator("img").all():
            expect(image).to_be_visible()
            page.wait_for_function("img=>img.complete && img.naturalWidth>0",arg=image.element_handle())
        result.screenshot(path=str(OUT/"results.png"))
        page.get_by_role("button",name="연구 분석",exact=True).click()
        research=page.locator(".research-analysis")
        expect(research).to_have_attribute("data-source-batch",BATCH)
        expect(research).to_contain_text("90")
        for label in ["알고리즘 종합","시나리오 분석","계산 비용","ORCA 위반 분석","창고 맵 분석"]:
            page.get_by_role("button",name=label,exact=True).click()
            for image in research.locator("img").all():
                page.wait_for_function("img=>img.complete && img.naturalWidth>0",arg=image.element_handle(),timeout=15000)
            if label=="시나리오 분석":
                assert research.locator("select option").count()==1
        page.get_by_role("button",name="알고리즘 종합",exact=True).click()
        research.screenshot(path=str(OUT/"research.png"))
        api=lambda action:c.request.post(BASE+"/wiz/api/page.algorithm.run/live_newton",form={"action":action,"batch_id":BATCH,"research_id":BATCH}).json()["data"]
        selected=api("unified_status");bundle=api("research_status")
        rows=c.request.post(BASE+"/wiz/api/page.algorithm.run/run_newton",form={"mode":"saved","batch_id":BATCH}).json()["data"]
        assert len(rows)==90 and {r["source_batch_id"] for r in rows}=={BATCH}
        assert set(r["run_id"] for r in rows)==set(bundle["run_ids"])==set(r["run_id"] for r in selected["rows"])
        raw=c.request.get(BASE+"/warehouse-experiments/research/"+BATCH+"/measurements.csv")
        assert raw.status==200
        assert set(r["run_id"] for r in csv.DictReader(io.StringIO(raw.text())))==set(bundle["run_ids"])
        report=c.request.get(BASE+"/warehouse-experiments/research/"+BATCH+"/research_report.md")
        assert report.status==200 and BATCH in report.text()
        assert not errors,errors
        checks={"passed":True,"batch_id":BATCH,"comparison_rows":90,"result_algorithms":3,
                "research_panels":5,"same_run_ids_in_api_csv_and_research":True,"scenario_options":["Crossing"],"errors":errors}
        (OUT/"checks.json").write_text(json.dumps(checks,indent=2));print(json.dumps(checks),flush=True)
    finally:b.close()
