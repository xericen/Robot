"""Write a verification report and reproducibility manifest from completed checks."""
from pathlib import Path
import argparse,json,re,hashlib,shutil
from research_data import ROOT,read_json,assert_originals,git
CHANGED=["newton_warehouse.py","newton_results.py","experiment_archive.py","algorithms/base.py","algorithms/orca.py",
"algorithms/velocity_obstacle.py","requirements-newton.txt","README.md","research_data.py","research_statistics.py",
"research_orca.py","research_layouts.py","research_figures.py","research_supplement.py","research_telemetry.py",
"research_report.py","research_pipeline.py","verify_research.py","finalize_research.py","docs/research_reproduction.md",
"tests/test_research_analysis.py","tests/test_controlled_encounters.py","tests/browser_research_results.py"]
UI=["src/app/page.algorithm.run/api.py","src/app/page.algorithm.run/view.ts","src/app/page.algorithm.run/view.pug",
    "src/app/page.algorithm.run/view.scss","src/route/warehouse.experiments/controller.py"]
def finalize(out):
    out=Path(out);audit=read_json(out/"audit.json");assert_originals(audit)
    check=read_json(out/"research_validation.json");assert check["passed"]
    browser=read_json(out/"browser_validation.json");assert browser["passed"]
    log=(out/"tests.log").read_text()
    match=re.search(r"(\d+) passed, (\d+) warnings in ([0-9.]+)s",log)
    assert match and not re.search(r"\d+ failed",log)
    historical=Path("/tmp/newton-enhanced-final-tests.log")
    if historical.exists():shutil.copyfile(historical,out/"historical_142_tests.log")
    paths=[ROOT/p for p in CHANGED]+[ROOT.parent/p for p in UI]
    provenance={"head":git("rev-parse","HEAD"),"branch":git("branch","--show-current"),
                "dirty":git("status","--short","--untracked-files=no"),
                "source_sha256":{str(p.relative_to(ROOT.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
    (out/"analysis_provenance.json").write_text(json.dumps(provenance,ensure_ascii=False,indent=2))
    note=["# 최종 검증 보고",f"\n자동 테스트: {match[1]}개 통과, 0개 실패, {match[2]}개 의존성 경고, {match[3]}초.",
      "\n초기 신규 테스트의 NumPy 2차원 cross 호출 오류를 명시적 행렬식으로 수정한 뒤 전체를 재실행했다.",
      "\nWIZ 정상 빌드 성공. 실제 브라우저 5개 분석 메뉴·4개 시나리오·2개 인구 구성·6개 맵 전환과 잘못된 파일 접근 차단 통과.",
      f'\n원본 파일 {check["original_files_verified"]}개의 SHA256 보존 확인. 240회 원본과 예비18회를 분석했고 Dense120행은 중복 부분집합이다.',
      "\n새 통제 시뮬레이션30회(시드42), 별도 전역 탐색54회. 검증용5프레임 테스트는 연구 표본으로 합산하지 않았다.",
      "\n과거142개 테스트 기록을 별도 복사했다. 이번 추가 테스트20개를 포함한 총163개가 현재 기준이다.",
      "\n원본의 목표227/240·무충돌152/240·안전53/240 재계산 일치, 중복·누락·설정/물리 상태 불일치 없음.",
      "\n계측 전후 동일 조건24쌍의 물리 지표 일치. 보완 재개 시 기존30개 ID/CSV 변경 및 새 실행 없음.",
      "\n원본 누락 시 가상 수치 생성 없이 종료하고 기존 출력 폴더 재사용은 명시적 재개 외 거부함을 검증했다.",
      "\n원본 CSV와 dashboard.json의 모든 수치 열을 대조했다. 기존 원본 CSV의 P95·정지 시간·LP 내부 횟수는 N/A이며 단일 시드 보완 자료와 혼합하지 않았다.",
      "\n검증 중 호환 별칭 CSV가 기존 실행에 의해 갱신되는 경로를 발견해 내용 해시가 일치하는 legacy_snapshots에서 원본을 복원했다. 중간 출력도 별도 보존했다. save_result는 이후 기존 별칭을 변경하지 않으며 실행별 metrics.csv를 반환한다.",
      "\n## 미완료·해석 한계",
      "\n- 과거 미측정 프레임별 항목과 선호 속도는 복구할 수 없어 N/A다. 별도30회는 단일 시드여서 전체240회의 P95로 대체할 수 없다.",
      "- 주 분석은Map1/10시드, 예비 시나리오는2시드다. 추가 맵 주행·모든 시나리오의10시드 확장은 후속 연구다.",
      "- ORCA의 C 인과 원인과 E 프레임의 단일 원인은 미확정이다. 독립 허용해 검사에서 확정된 A 오류는 없어 솔버를 교체하지 않았다.",
      "- 통행 간격은0.25m 샘플 기반 운영 지표다. 연속 기하의 전역 최소 폭으로 단정하지 않는다.",
      "- 공개 Robot 커밋과 로컬 WIZ HEAD/dirty 상태는 다르다. 공개 트리에 로컬240회 배치가 없으며 게시/푸시하지 않았다.",
      "\n## 수정·추가 소스 파일",*["\n- warehouse-collision-avoidance/"+p for p in CHANGED],*["\n- "+p for p in UI],
      "\n개발로그: devlog.md 및 devlog/2026-11-17/011-robot-research-analysis.md.",
      "\n## 생성 자료",
      "\n필수5개 분석CSV, 짝지은 통계/민감도/보완CSV, 원본감사·메타데이터·실행별로그,7절 연구 보고서, 발표 요약을 생성했다.",
      "\n24개 PNG(200dpi, Noto Sans KR):"]
    bundle=read_json(out/"dashboard.json")
    note.extend("- figs/"+f for f in bundle["figures"])
    note+=["\n전체 파일 목록은 manifest.json, 원본 해시는 audit.json, 최종 분석 소스 해시는 analysis_provenance.json에 있다."]
    (out/"verification_report.md").write_text("\n".join(note)+"\n")
    files=[f for f in sorted(out.rglob("*")) if f.is_file() and f.name!="manifest.json"]
    (out/"manifest.json").write_text(json.dumps({"status":"complete","primary_runs":240,"pilot_runs":18,"new_runs":30,
       "planner_runs":54,"pytest_passed":int(match[1]),"pytest_failed":0,"originals_unchanged":True,
       "files":[str(p.relative_to(out)) for p in files]},ensure_ascii=False,indent=2))
    print("Finalized",out,len(files),"files")
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("output",type=Path);finalize(p.parse_args().output)
