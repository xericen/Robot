"""Verify persisted comparison and parameter UI against actual WIZ APIs."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE = os.getenv("WAREHOUSE_BASE_URL", "http://localhost:3000")
OUT = Path(__file__).resolve().parents[1] / "results/newton/validation"
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True, executable_path=os.getenv("WAREHOUSE_CHROMIUM") or playwright.chromium.executable_path, args=["--no-sandbox"])
    context = browser.new_context(viewport={"width": 1500, "height": 1200})
    context.add_cookies([{"name":"season-wiz-devmode","value":"true","domain":"localhost","path":"/"}])
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    requests = []
    page.on("request", lambda request: requests.append(request.post_data or "") if "run_newton" in request.url else None)
    page.goto(BASE + "/algorithm?section=implementation&public=1")
    page.get_by_role("button", name="알고리즘 비교", exact=True).click()
    expect(page.locator(".unified-dashboard .table-scroll tbody tr")).to_have_count(18, timeout=30000)
    expect(page.locator(".unified-dashboard .chart-grid figure")).to_have_count(6)
    expect(page.locator(".unified-dashboard .chart-grid figure").first).to_contain_text("Naive")
    expect(page.locator(".unified-dashboard .chart-grid figure").first).to_contain_text("ORCA")
    expect(page.get_by_text("현재 파라미터", exact=True)).to_be_visible()
    page.locator(".unified-dashboard .chart-grid").screenshot(path=str(OUT / "persisted-comparison.png"))
    page.locator(".unified-dashboard .table-scroll").screenshot(path=str(OUT / "persisted-table.png"))
    page.reload()
    page.get_by_role("button", name="알고리즘 비교", exact=True).click()
    expect(page.locator(".unified-dashboard .table-scroll tbody tr")).to_have_count(18, timeout=30000)
    # Summaries must not offer frame playback; no simulation command should be sent.
    assert page.locator(".unified-dashboard .table-scroll tbody button:enabled").count() == 0
    assert requests and all("saved" in body and "compare" not in body for body in requests), requests
    page.get_by_role("button", name="환경 설정", exact=True).click()
    expect(page.locator(".settings-grid").first.locator("input")).to_have_count(8)
    page.locator(".settings-grid").first.screenshot(path=str(OUT / "parameters.png"))
    # A real short comparison verifies parameter forwarding and timeout presentation.
    page.get_by_label("VO 후보 속도 K", exact=True).fill("11")
    page.get_by_label("랜덤 시드", exact=True).fill("9001")
    page.get_by_label("실험 최대 실행 프레임 (기본 30fps)", exact=True).fill("30")
    page.get_by_role("button", name="알고리즘 비교", exact=True).click()
    page.get_by_label("비교 범위", exact=True).select_option("selected")
    page.get_by_role("button", name="선택 맵 · 세 알고리즘 실행", exact=True).click()
    expect(page.locator(".unified-dashboard .table-scroll tbody tr")).to_have_count(3, timeout=120000)
    for row in page.locator(".unified-dashboard .table-scroll tbody tr").all():
        expect(row.locator("td").nth(3)).to_have_text("timeout")
        expect(row.locator("td").nth(4)).to_have_text("N/A")
    import csv
    for algorithm in ("naive", "vo", "orca"):
        path = OUT.parents[0] / f"map1_{algorithm}_medium_9001.csv"
        saved = next(csv.DictReader(path.open()))
        assert saved["vo_candidates"] == "11" and saved["frame_limit"] == "30"
        assert saved["timeout"] == "1" and saved["arrival_time_s"] == ""
    page.locator(".unified-dashboard .table-scroll").screenshot(path=str(OUT / "real-timeout-table.png"))
    assert not errors, errors
    result = {"passed":True,"persisted_rows":18,"map_charts":6,"parameter_inputs":8,
              "reload_preserves_csv_results":True,"real_short_comparison_and_parameters":True,"page_errors":errors}
    (OUT / "browser.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False))
    browser.close()
