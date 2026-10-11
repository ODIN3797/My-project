# Robot Incident Analyzer v0.5.3 — 사람 검토 기반 검증

## 왜 이 기능이 필요한가

로봇 bag을 읽고 경고를 출력할 수 있는 것과 **경고가 실제로 정확한지**는 다릅니다. Zenodo E1-1/E1-2 데이터는 정상/모의공격 실험 구분을 제공하지만 **검증된 공격 시작 시각과 모든 정상 구간의 정답 라벨**을 제공한다고 볼 수 없습니다. 따라서 v0.5.2의 단일-bag 급증 구간 1개, 기존 정상 기록의 0개라는 결과만으로 탐지율이나 오탐률을 산출해서는 안 됩니다.

이번 버전은 특정 ROS2 토픽의 **메시지 기록 빈도 급증**에 한정해서, 리뷰어가 주석을 직접 달아 정확도를 평가합니다. 모든 장애 유형에 대한 일반 정확도 평가 도구는 아닙니다.

## 명령어

```bash
python3 -m robot_incident_analyzer inspect-rates candidate.db3 \
  --reference normal.db3 --topic /mobile_base_controller/cmd_vel \
  --output rate_report

python3 -m robot_incident_analyzer init-rate-labels \
  rate_report/rate_timeline.json \
  --topic /mobile_base_controller/cmd_vel \
  --output rate_annotations.json

xdg-open rate_annotations.html
# 오프라인 UI에서 시간 범위를 직접 검토하고 JSON 내보내기

python3 -m robot_incident_analyzer score-rate-labels \
  rate_report/rate_timeline.json rate_annotations.json \
  --output evaluated

xdg-open evaluated/evaluation.html
```

라벨링 HTML에서 **분석기의 예측 구간은 기본 숨김**이며 직접 선택하면 표시됩니다. 결과에 영향을 줄 수 있는 예측 노출을 최소화하기 위해 먼저 독립적으로 로그를 확인하세요. UI에서 정상으로 표기하지 않은 나머지 부분은 미검토 구간으로 남습니다. 원본 bag은 사용자 PC에만 두세요.

## 수치 정의와 신뢰 한계

- **Positive recall**: 명시적으로 확인된 positive 구간 중 탐지 구간과 한 번 이상 겹치는 건수/전체 positive 건수. 여러 구간의 중복 매칭을 금지합니다. 미표기 장애는 분모에 포함하지 않습니다.
- **False alarms per reviewed hour**: *완전히* 검토 완료된 정상(negative) 구간 안에 포함된 예측 건수/정상 검토 시간(h). 정상으로 확인하지 않은 구간과 일부만 겹치는 예측은 계산에서 제외합니다.
- **Detection delay**: 정답 구간의 시작과 겹친 최초 매칭 탐지 구간 시작의 차이. 이전부터 이미 경고가 지속 중인 경우 0초로 클리핑하며 별도 onset 차이도 기록합니다. 1초 히스토그램 시간 해상도에 제한됩니다.
- **Not measured**: 해당 범위 정답이 없거나, 주석이나 데이터가 부족한 상태. 계산 불가능한 수치를 0으로 처리하지 않습니다.
- **Recording SHA-256 확인**: 다른 bag에 작성한 라벨을 잘못 적용하면 거부합니다. 토픽과 메시지 타입도 정확히 일치해야 합니다.
- **Coverage 제한**: 불완전한 히스토그램 및 시작·끝 부분의 비완전한 1초 구간은 평가를 거부합니다.

**주의**: 라벨의 `reviewed` 상태와 리뷰어 ID는 사용자가 직접 선언하는 것이며, 프로그램이 실제 검토 여부를 독립적으로 증명하지 않습니다. 공격·하드웨어 고장·근본 원인은 주파수 증가만으로 확정할 수 없습니다.

## 제공된 데모와 공개 데이터의 구분

| 데이터 | 라벨 상태 | 탐지율/오경보 지표 |
|---|---|---|
| `demo_evaluation`에 포함된 가상 bag/정답 | 합성 테스트에서 의도적으로 생성 | 테스트 목적으로 계산 가능, 실측 정확도로 인용 금지 |
| Zenodo 17649537 E1-2 실험 | 출처 표기 및 미검토 템플릿 | **측정하지 않음** (공격의 개시 정답 시각 및 정상 구간 검토 없음) |
| Vigo 주행 9개, BAGEL MCAP | 자체 정답 시간 구간 없음 | **측정하지 않음** |

## 다음 실제 검증 작업

1. Zenodo 실험 제작자가 정확한 attack onset 및 완전 정상 구간을 공개했는지 추가 확인하고, 가능하면 원 제작자에게 정답 시점을 문의합니다.
2. 실물 AMR의 정상 운용/도킹/충전 실패 로그를 적법하게 수집하고, 서로 독립적인 리뷰어 2명이 구간을 주석 처리합니다.
3. 라벨의 일치도를 확인하고 데이터셋별 recall, false alarms/reviewed hour, detection delay를 **동일 토픽·동일 판단 규칙**에서 비교합니다.
4. 실제 업무 조사 소요 시간 A/B 측정 전까지는 유료 제품의 시간 절감 효과를 주장하지 않습니다.
