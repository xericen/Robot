"""Read the completed CSV summaries and nine graph types in the actual results tab."""
import json,os
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
OUT=Path(__file__).resolve().parents[1]/"results/newton/validation/controlled"
OUT.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path=os.getenv("WAREHOUSE_CHROMIUM") or p.chromium.executable_path,args=["--no-sandbox"])
    context=browser.new_context(viewport={"width":1600,"height":1100})
    context.add_cookies([{"name":"season-wiz-devmode","value":"true","domain":"localhost","path":"/"}])
    page=context.new_page();errors=[]
    page.on("pageerror",lambda e:errors.append(str(e)))
    page.goto("http://localhost:3000/algorithm?section=implementation&public=1")
    page.get_by_role("button",name="실험 결과",exact=True).click()
    batch=os.getenv("WAREHOUSE_STUDY_BATCH","20261117T093838421883Z_01843a5b")
    full=bool(os.getenv("WAREHOUSE_STUDY_BATCH"))
    expected_figures=18 if full else 27
    expected_rows=24 if full else 9
    page.get_by_label("통제 실험 배치",exact=True).select_option(batch)
    images=page.locator('img[src^="/warehouse-experiments/"]')
    expect(images).to_have_count(expected_figures,timeout=30000)
    expect(page.locator("table").filter(has_text="안전 도달률 95% 구간").locator("tbody tr")).to_have_count(expected_rows)
    image=images.first;image.scroll_into_view_if_needed()
    page.wait_for_function("(im)=>im.complete && im.naturalWidth>0",arg=image.element_handle())
    response=context.request.get("http://localhost:3000"+image.get_attribute("src"))
    assert response.status==200 and response.headers["content-type"]=="image/png"
    invalid=context.request.get("http://localhost:3000/warehouse-experiments/"+batch+"/invalid/provenance.json")
    assert invalid.status==404
    page.locator("table").filter(has_text="안전 도달률 95% 구간").screenshot(path=str(OUT/("full-study-results.png" if full else "study-results.png")))
    if full:
        page.get_by_role("button",name="환경 설정",exact=True).click()
        page.locator(".settings-grid").nth(2).locator("select").select_option("crowded")
        page.get_by_label("만남 조건",exact=True).select_option("crossing")
        page.get_by_label("추가 에이전트 수 (주행 AMR 제외)",exact=True).fill("4")
        page.get_by_role("button",name="알고리즘 비교",exact=True).click()
        page.get_by_role("button",name="저장 CSV 불러오기",exact=True).click()
        expect(page.locator(".unified-dashboard .table-scroll tbody tr")).to_have_count(3)
        naive=page.locator(".unified-dashboard .table-scroll tbody tr").filter(has_text="Naive")
        expect(naive.locator("td").nth(4)).to_have_text("timeout")
        expect(naive.locator("td").nth(8)).to_have_text("N/A")
    assert not errors,errors
    (OUT/("full-study-browser.json" if full else "study-browser.json")).write_text(json.dumps({"passed":True,"summary_rows":expected_rows,"graphs":expected_figures,
        "image_route_verified":True,"invalid_asset_rejected":True,"page_errors":errors},ensure_ascii=False,indent=2))
    print(f"통제 실험 표{expected_rows}행·그래프{expected_figures}개·이미지 응답·임의 파일 차단 검사 통과")
    browser.close()
