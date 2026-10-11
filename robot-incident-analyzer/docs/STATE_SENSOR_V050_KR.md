# v0.5.0 상태 전환 전후 센서값 비교

로봇이 기록한 `mode=PAUSED`, `docking_state=CONTACT` 등의 **명시적인 로그 상태 전환**을 기준으로 센서값을 비교합니다. 실제 컨트롤러의 상태를 독립적으로 검증하지는 않습니다.

- 전환 전 2초와 후 2초: 겹치지 않는 별도의 시간 구간
- 양쪽에 유효하고 서로 다른 타임스탬프 샘플이 2개 이상일 때만 중앙값·차이 계산
- 전환 근처의 샘플이 1초 이상 떨어져 있으면 수치 비교를 생략
- 로봇 네임스페이스와 로그 파일 출처를 구분
- HTML 장애 조사 카드에서 전환 시점(청록색)과 장애 시점(주황색)을 별도 점선으로 표시
- JSON에는 근거 ID·표본 수·시간 간격·변화량을 저장하고 PDF에는 핵심 비교만 표시

실행:

```bash
python3 -m robot_incident_analyzer demo-states --output demo_states
python3 -m robot_incident_analyzer analyze demo_states/fictional_state_transitions.mcap --output example_output
xdg-open example_output/report.html
```

**주의:** 관측된 전후 수치 차이는 통계적 유의성이나 장애 원인에 대한 증명이 아닙니다. 현재 결과는 가상 MCAP 및 공개 포맷 호환성 테스트에 기반하며, 실제 장애 정답 데이터 검증은 진행되지 않았습니다.
