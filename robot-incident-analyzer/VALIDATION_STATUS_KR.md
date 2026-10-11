# Robot Incident Analyzer v0.4.2 | 외부 실측 데이터 검증 준비 결과

**2026-10-11**

## 검증된 항목

- Linux / Python 3.13 환경에서 unittest 총 **46개 통과**
- 별도 위치에 패키지 설치 후 CLI 버전 확인 성공
- 합성 ROS2 DB3/MCAP 자료에서 field-validate 독립 보고서 생성
- 합성 MCAP 4개 토픽 / 35개 메시지 / 6개 사건 탐지
- 합성 DB3 3개 토픽 / 163개 메시지 / 4개 사건 탐지 (일부 메시지 타입 미지원, REVIEW_REQUIRED)
- 합성 데이터 라벨 2건에 대한 탐지 2건: **라벨 검출률 100% (합성 테스트에 한정)**
- 압축 청크 미지원, 분석량 제한, 지원되지 않는 메시지 타입 등 결과 누락 경고 검사

## 검증되지 않은 항목

- **외부에서 수집한 실제 로봇 MCAP/DB3 실행: 못함.** GitHub 바이너리 및 다운로드에 접근할 수 없는 실행 환경 제약.
- 실제 현장 장애 진단 정밀도, 오탐률, 탐지율: 측정하지 않음
- 해외 엔지니어가 실사용해 업무 시간을 줄였는지: 검증 참여자 0명
- ROS2 배포판별 설치 검증: 이번에는 단일 Linux/Python 버전만 실측. CI 설정은 추가했지만 원격 CI 수행 여부 확인 안 됨.

## 바로 실행하기

```bash
cd robot-incident-analyzer-v0.4.2-field-pilot
python3 -m robot_incident_analyzer field-validate /경로/기록.mcap \
   --origin unknown --output field_results
```

`field_results/FIELD_RESULTS.md`와 `field_results/field_results.json` 확인. `REVIEW_REQUIRED`가 나오면 커버리지/토픽 매핑부터 확인.

실제 공개 데이터 원본은 `docs/FIELD_PILOT_EN.md`에 연결했음. 상용성 여부를 판단하려면 **해외 엔지니어 3~5명의 독립 실행과 실제 장애 라벨 비교**가 반드시 필요함.
