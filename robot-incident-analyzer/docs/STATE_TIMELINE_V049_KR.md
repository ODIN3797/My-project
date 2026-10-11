# v0.4.9 로봇 상태 변화 타임라인

ROS2 `/rosout`와 CSV에 명시적으로 기록된 `mode=`, `docking_state=`, `charging_state=` 등을 분석해 상태 변화와 원본 로그 ID를 연결합니다. 장애 조사 화면에는 해당 장애 발생 전/당시 30초 동안의 상태 기록만 요약합니다. 다른 로봇 및 다른 입력 파일의 상태는 섞지 않습니다.

```bash
python3 -m robot_incident_analyzer demo-states --output state_demo
python3 -m robot_incident_analyzer analyze state_demo/fictional_state_transitions.mcap --output result --pdf
xdg-open result/report.html
```

PDF는 선택 패키지 `reportlab` 설치가 필요합니다. `report.json`의 `state_transitions`에도 근거가 저장됩니다. 사용자 정의 상태 키는 `examples/state_config.json`의 `state_keys`로 설정합니다.

**한계**: 로그에 상태가 기록되었다는 뜻이지 실제 로봇이 해당 상태로 전환되었다는 증명이 아닙니다. 메시지 간 상태 유지는 추정하지 않습니다. 장애와 상태의 시간적 근접성은 인과관계 증거가 아닙니다. 현재 테스트는 합성 데이터이며 실측 로그의 정확도는 미검증입니다.
