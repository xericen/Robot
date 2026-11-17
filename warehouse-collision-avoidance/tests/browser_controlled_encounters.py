"""Actual dashboard comparison: schedule controls, archive history, metrics and unchanged scene hash."""
import csv
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"results/newton/validation/controlled"
OUT.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path=os.getenv("WAREHOUSE_CHROMIUM") or p.chromium.executable_path,args=["--no-sandbox"])
    context=browser.new_context(viewport={"width":1600,"height":1100})
    context.add_cookies([{"name":"season-wiz-devmode","value":"true","domain":"localhost","path":"/"}])
    page=context.new_page();errors=[]
    page.on("pageerror",lambda e:errors.append(str(e)))
    page.goto("http://localhost:3000/algorithm?section=implementation&public=1")
    page.get_by_role("button",name="환경 설정",exact=True).click()
    page.get_by_label("만남 조건",exact=True).select_option("crossing")
    expect(page.get_by_label("인구 구성",exact=True)).to_have_value("workers")
    page.get_by_label("추가 에이전트 수 (주행 AMR 제외)",exact=True).fill("4")
    # Unique seed avoids mixing this test with prior measured experiments.
    import time
    seed=int(time.time())%900000+50000
    page.get_by_label("랜덤 시드",exact=True).fill(str(seed))
    page.get_by_label("실험 최대 실행 프레임 (기본 30fps)",exact=True).fill("60")
    page.get_by_role("button",name="알고리즘 비교",exact=True).click()
    page.get_by_label("비교 범위",exact=True).select_option("selected")
    for attempt in range(2):
        page.get_by_role("button",name="선택 맵 · 세 알고리즘 실행",exact=True).click()
        expect(page.locator(".unified-dashboard > .status")).to_contain_text("3건.",timeout=120000)
        expect(page.locator(".unified-dashboard .table-scroll tbody tr")).to_have_count(3)
    page.get_by_role("button",name="저장 CSV 불러오기",exact=True).click()
    expect(page.locator(".unified-dashboard .table-scroll tbody tr")).to_have_count(3)
    page.get_by_label("실행 이력 포함",exact=True).check()
    expect(page.locator(".unified-dashboard .table-scroll tbody tr")).to_have_count(6)
    page.locator(".unified-dashboard .table-scroll").screenshot(path=str(OUT/"history.png"))
    rows=[]
    for path in (ROOT/"results/newton/runs").glob("*/metrics.csv"):
        r=next(csv.DictReader(path.open()))
        if r["seed"]==str(seed):
            rows.append(r)
    assert len(rows)==6 and len({r["run_id"] for r in rows})==6
    assert len({r["scene_hash"] for r in rows})==1
    assert all(r["worker_count"]=="4" and r["other_robot_count"]=="0" and r["timeout"]=="1" for r in rows)
    page.get_by_role("button",name="환경 설정",exact=True).click()
    page.get_by_label("만남 조건",exact=True).select_option("narrow_passing")
    page.locator(".unified-dashboard").screenshot(path=str(OUT/"controls.png"))
    page.get_by_role("button",name="시뮬레이션",exact=True).click()
    page.get_by_role("button",name="Map 2: Horizontal",exact=True).click()
    expect(page.locator(".unified-dashboard > .status")).to_contain_text("Map1 전용")
    page.get_by_role("button",name="환경 설정",exact=True).click()
    page.get_by_label("만남 조건",exact=True).select_option("baseline")
    expect(page.get_by_label("인구 구성",exact=True)).to_have_value("legacy")
    expect(page.get_by_label("추가 에이전트 수 (주행 AMR 제외)",exact=True)).to_be_disabled()
    page.get_by_role("button",name="알고리즘 비교",exact=True).click()
    page.get_by_role("button",name="저장 CSV 불러오기",exact=True).click()
    expect(page.locator(".unified-dashboard .table-scroll tbody tr")).to_have_count(0)
    assert not errors,errors
    result={"passed":True,"archived_runs":6,"identical_scene_hash":True,"history_survives_reexecution":True,
            "population_forwarded":True,"timeout_metrics":True,"page_errors":errors,"seed":seed}
    (OUT/"browser.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False))
    browser.close()
