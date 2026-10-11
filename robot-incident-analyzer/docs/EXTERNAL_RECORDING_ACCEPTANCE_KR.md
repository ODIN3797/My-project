# 실제 외부 ROS2 기록 검증 절차 — v0.4.3

## 현재 검증 상태

- **실제 물리 로봇 MCAP/DB3를 여기서 분석한 적 없음**. 공개 링크는 확인했으나 실행 환경의 외부 바이너리 다운로드 제한으로 파일을 획득하지 못함.
- 51개 자동화 테스트 성공은 합성 및 의도적으로 손상된 MCAP/DB3로 검증한 **구조적 정확성**만 의미함.
- 사고 탐지 precision/recall, 실제 개발자 업무시간 감소, 고객 지불의사 모두 **미검증**.

## 공개 데이터 출처

1. JKK Research Dataset 02: https://jkk-research.github.io/dataset/jkk_dataset_02/ — 실제 주행 기록 MCAP. 데이터셋 페이지의 **Download a sample MCAP** 참조. 장애 정답 라벨은 확인되지 않았음. 해당 데이터는 로봇 장애 분석 평가보다는 포맷·메시지 호환성과 데이터 규모 테스트에 유용함.
2. RTAB-Map ROS2 multi-session bag example: https://github.com/introlab/rtabmap_ros/blob/ros2/rtabmap_demos/launch/multisession_mapping_demo.launch.py — `map1.db3`부터 ROS2 bag 다운로드 링크를 제공. 자율주행 장애 라벨 여부 미확인.
3. BAGEL tour.mcap: https://github.com/Hussain004/BAGEL/tree/main/public/sample-bags — 타 프로젝트에서 제작한 샘플 MCAP. **실측 데이터로 취급하면 안 됨**. 파서 상호운용성 테스트 전용.

원본을 사용하기 전 게시자의 재배포/라이선스, 개인정보 및 로그 민감정보를 확인. 파일 자체는 우리 ZIP에 넣지 않음.

## 재현 방법 (Ubuntu)

```bash
cd robot-incident-analyzer-v0.4.3-beta
python3 --version  # 3.10+
python3 -m unittest discover -s tests -v
bash scripts/validate_local_real_bag.sh /absolute/path/to/recording.mcap unknown output_external
cat output_external/FIELD_RESULTS.md
```

실제 물리 로봇 기록이라는 근거가 있을 때만 `unknown` 대신 `physical` 사용. 진단 실패 라벨이 있는 경우 `field-validate --labels labels.csv`를 사용.

출력된 `report.html`, `report.json`, `FIELD_RESULTS.md`는 로컬 장비에 남으며 외부 업로드하지 않음.

## 실제 사용성 평가 체크리스트

1. **파일 처리**: 1개의 공개 실측 MCAP·DB3에서 오류 없이 종료하는가? 누락 메시지, 미지원 타입, 압축 청크가 무엇인가?
2. **토픽 매핑**: 자동 선택한 Command/Odometry가 의미상 올바른가? 이 로봇의 최종 주행 지령인가? 안전 제한·중재 후 속도인가?
3. **사건 탐지**: 엔지니어가 별도로 만든 사건 라벨 대비 TP/FP/FN을 조사하는가? 라벨이 없으면 정밀도 지표를 보고하지 않음.
4. **진단 유효성**: 시간 근접성이 원인 인과로 오인되지 않았는가? TF의 정상적인 위치 보정도 오류로 단정하지 않았는가?
5. **성능**: 파일 크기, 처리 시간, 피크 RSS, 파일당 분석 메시지 수, 경고 수를 기록하는가?
6. **사용성**: 엔지니어 5명 대상 설치 시간과 수작업 대비 시간 절약을 직접 측정하는가? 현재 참여자는 0명.

## 출시 판단 기준 (제안 목표, 실측 완료 아님)

- **공개 알파**: 서로 다른 수집 환경의 외부 bag 3개 파싱 가능, 누락/미지원 항목이 모두 표시될 것.
- **비공개 현업 테스트**: 별도 이용 허가를 받은 실제 로봇 로그 3개 및 사람 라벨을 이용해 오탐/미탐 점검.
- **유료 출시 검토**: 현업 엔지니어 5명 중 3명 이상이 시간을 절감하고 반복 사용 의사를 명시하며 최소 1곳 유료 파일럿 계약.

## 주의 사항

전제 조건 없이 보고서가 생성됐다고 `PASS`라고 부르지 않음. 상태가 `REVIEW_REQUIRED`인 이유를 먼저 해결. 실측 로그가 없으면 `실측 검증 미완료` 상태 유지.
