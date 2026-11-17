# 통제 실험 실측 요약

실행 18회. 도달시간은 성공 실행만, 다른 지표는 실패를 포함해 집계한다.

|맵/만남/집단|n|방식|실행 수|도달률%|무충돌 도달률%|안전 도달률%|도달시간 평균±표준편차(s)|회피시간 평균±표준편차(ms)|
|---|---|---|---|---|---|---|---|---|
|map1/crossing/workers|4|Naive|2|50.0|0.0|0.0|32.8670 ± N/A|0.0265 ± 0.0052|
|map1/crossing/workers|4|ORCA|2|100.0|100.0|0.0|31.2500 ± 0.2588|0.0804 ± 0.0037|
|map1/crossing/workers|4|VO|2|100.0|100.0|50.0|31.0665 ± 0.0474|1.5625 ± 0.0623|
|map1/head_on/workers|4|Naive|2|50.0|50.0|0.0|32.6000 ± N/A|0.0296 ± 0.0004|
|map1/head_on/workers|4|ORCA|2|100.0|100.0|0.0|31.3000 ± 0.1414|0.0888 ± 0.0001|
|map1/head_on/workers|4|VO|2|100.0|100.0|100.0|31.1165 ± 0.0233|2.0174 ± 0.0022|
|map1/narrow_passing/workers|4|Naive|2|100.0|0.0|0.0|41.8335 ± 0.3302|0.0258 ± 0.0042|
|map1/narrow_passing/workers|4|ORCA|2|100.0|50.0|0.0|32.5835 ± 0.8252|0.0702 ± 0.0014|
|map1/narrow_passing/workers|4|VO|2|100.0|50.0|0.0|32.4830 ± 0.4950|1.4920 ± 0.0119|

각 도달률의95% Wilson 구간, 실패 제외 도달시간 표본 수, 개별 안전 지표와 카운터는 safety_summary.csv에 보존한다.

## 입력 크기와 계산량
- map1/crossing/workers/Naive: n=4→4, 평균 회피시간 1.00배, 끝점 기준 경험적 지수 N/A. 이 값은 Big-O의 증명이 아니다.
- map1/crossing/workers/ORCA: n=4→4, 평균 회피시간 1.00배, 끝점 기준 경험적 지수 N/A. 이 값은 Big-O의 증명이 아니다.
- map1/crossing/workers/VO: n=4→4, 평균 회피시간 1.00배, 끝점 기준 경험적 지수 N/A. 이 값은 Big-O의 증명이 아니다.
- map1/head_on/workers/Naive: n=4→4, 평균 회피시간 1.00배, 끝점 기준 경험적 지수 N/A. 이 값은 Big-O의 증명이 아니다.
- map1/head_on/workers/ORCA: n=4→4, 평균 회피시간 1.00배, 끝점 기준 경험적 지수 N/A. 이 값은 Big-O의 증명이 아니다.
- map1/head_on/workers/VO: n=4→4, 평균 회피시간 1.00배, 끝점 기준 경험적 지수 N/A. 이 값은 Big-O의 증명이 아니다.
- map1/narrow_passing/workers/Naive: n=4→4, 평균 회피시간 1.00배, 끝점 기준 경험적 지수 N/A. 이 값은 Big-O의 증명이 아니다.
- map1/narrow_passing/workers/ORCA: n=4→4, 평균 회피시간 1.00배, 끝점 기준 경험적 지수 N/A. 이 값은 Big-O의 증명이 아니다.
- map1/narrow_passing/workers/VO: n=4→4, 평균 회피시간 1.00배, 끝점 기준 경험적 지수 N/A. 이 값은 Big-O의 증명이 아니다.

## ORCA 감사

```json
{
  "hypothesis_frame_counts": {
    "physical_tracking_error": 149,
    "prediction_or_noncooperative_motion": 203,
    "infeasible_constraints": 45
  },
  "target_constraint_violation_frames": 45,
  "static_risk_only_frames": 33,
  "tracking_error_mean_mps": 0.12578297486169737,
  "tracking_error_max_mps": 1.2763932238629088,
  "interpretation": "가설 분류이며 원인 증명이 아님. static_risk_only는 동적 위반/접촉 없이 정적 안전거리만 위반한 프레임."
}
```

목표는 제약을 만족하지만 실제 속도가 벗어난 프레임은 추종 오차의 근거다. 정적 장애물은 ORCA 반평면에 포함되지 않으므로 정적 접근을 비협조적 작업자의 영향으로 단정하지 않는다. 비협조적 순찰과 제약 불가능, 물리 제어 지연을 함께 해석해야 한다.

실행별 결과/설정/초기 상태/코드 해시·의존성은 results/newton/runs/<run_id>/에 있다. 현 비교의 전역 탐색은A*이고 온라인 재탐색은 사용하지 않는다.