# Stage 2: Behavioral Cloning 기반 궤적 추종 제어기 설계 및 단일 경로 검증

## 1. 목표 (Goal)
본 단계(Stage 2)의 목적은 **MPPI(Model Predictive Path Integral) 제어기를 통해 추출한 최적 제어 데이터(Golden Data)를 경량화된 인공신경망(MLP)에 학습(Behavioral Cloning)** 시키는 것.   
이를 통해 연산량이 매우 높은 MPPI의 한계를 극복하고, Genesis 시뮬레이터 환경에서 실시간(Real-time)으로 Blender 목표 궤적을 추종할 수 있는 베이스라인 제어기(Mapper)를 구축.

---

## 2. System State 및 네트워크 설계 (Architecture)
단순한 절대 좌표 매핑이 아닌, 제어기의 **자기 객관화(Closed-loop 피드백)** 와 **예측 제어(Lookahead)** 가 가능하도록 27차원의 상태 변수(System State)를 설계.

### 2.1. 입력 상태 변수 (Input State, X = 27 Dims)

| 카테고리 | 변수명 | 차원 | 설명 (설계 의도) |
| :--- | :--- | :--- | :--- |
| **Feedback (오차)** | `delta_v`, `delta_heading`, `cross_track_error` | 3 | 목표 궤적과의 현재 오차. 궤도 이탈 시 모델이 이를 인지하고 보정할 수 있도록 유도 (Covariate Shift 대응 최소한의 장치). |
| **Dynamics (현재 상태)** | `v_current`, `kappa_current`, `prev_throttle`, `prev_steer` | 4 | 현재 차량의 동역학적 관성 및 직전 제어값. 제어의 연속성(Smoothness) 보장. |
| **Lookahead (미래 예측)** | `kappa_target[t+1:t+10]`, `v_target[t+1:t+10]` | 20 | 전방 10프레임의 곡률 및 목표 속도. MPPI의 Horizon과 동일한 미래 시야를 제공하여 코너링 전 선제적 감속/조향 유도. |

### 2.1.1. 학습 시 (Training)

| 차원 | 항목 | 출처 |
| :--- | :--- | :--- |
| **1** | `delta_v` (목표속도 - 현재속도) | Golden CSV (`blender_v` - `mppi_v`) |
| **2** | `delta_heading` (목표heading - 현재heading) | Golden CSV (`blender_heading` - `mppi_heading`) |
| **3** | `cross_track_error` (횡방향 오차) | Golden CSV (Mppi x,y vs Blender x,y) |
| **4** | `v_current` (현재 속도) | Golden CSV (`mppi_v`) |
| **5** | `kappa_current` (현재 곡률) | Golden CSV (`mppi_heading` 변화율로 계산) |
| **6** | `prev_throttle` | 이전 스텝 label 값 |
| **7** | `prev_steer` | 이전 스텝 label 값 |
| **8~17** | `kappa_lookahead` × 10 | Blender CSV (kappa 미래 10프레임) |
| **18~27** | `v_lookahead` × 10 | Blender CSV (v_smooth 미래 10프레임) |

---

### 2.1.2 추론 시 (Inference / Rollout)

| 차원 | 항목 | 출처 |
| :--- | :--- | :--- |
| **1** | `delta_v` | Genesis 실시간 vs Blender CSV 목표 |
| **2** | `delta_heading` | Genesis 실시간 vs Blender CSV 목표 |
| **3** | `cross_track_error` | Genesis 실시간 위치 vs Blender CSV 목표 위치 |
| **4** | `v_current` | Genesis 실시간 |
| **5** | `kappa_current` | Genesis 실시간 heading 변화율 |
| **6~7** | `prev_throttle`, `prev_steer` | BC가 직전에 출력한 값 |
| **8~17** | `kappa_lookahead` × 10 | Blender CSV |
| **18~27** | `v_lookahead` × 10 | Blender CSV |

---

## 핵심 요약

* **현재 상태 (7차원)** $\rightarrow$ **학습:** Golden CSV / **추론:** Genesis 실시간
* **미래 목표 (20차원)** $\rightarrow$ **학습/추론 모두:** Blender CSV (동일)

### 2.2. 출력 변수 및 손실 함수 (Output & Loss)
* **Output (Y):** `throttle`, `steer` (2 Dims, Tanh 활성화 함수를 통해 [-1, 1] 스케일링)
* **Loss Function (MSE):** 최적 제어값과의 평균 제곱 오차 최소화

$$Loss = \frac{1}{N} \sum \left( (u_{\text{throttle}}^{\text{BC}} - u_{\text{throttle}}^{\text{MPPI}})^2 + (u_{\text{steer}}^{\text{BC}} - u_{\text{steer}}^{\text{MPPI}})^2 \right)$$

### 2.3. 네트워크 용량 (Network Capacity) 최적화
* **구조:** 3-Layer MLP `[27 -> 64 -> 64 -> 2]` (총 파라미터 수: 6,082개)
* **설계 근거:** 초기 `[256, 256, 128]` 구조는 파라미터가 과도하게 많아 MPPI가 가진 미세한 계산 노이즈(Jitter)까지 암기하는 과적합(Overfitting to noise) 문제가 우려. 이에 은닉층을 `[64, 64]`로 대폭 축소하여, 물리적 제어에 필수적인 **부드러운 보간(Smooth Interpolation)** 특성을 확보.

---

## 3. 단일 경로 검증 결과 (Sanity Check)

https://github.com/user-attachments/assets/cbd52cd4-4c4c-4305-bfe7-db0dc7e70303


  - Blue(파란색)  = Blender 원본 경로
  - Green(초록색) = MPPI 최적화 결과 경로 (golden_inputs_optimized.csv)
  - Red(빨간색)   = BC 모델 주행 경로

### 3.1 정량적 성능 지표 (MPPI vs BC)

| 평가지표 | MPPI (Teacher) | BC (Student) | 분석 |
| :--- | :--- | :--- | :--- |
| **Mean Drift (m)** | 0.465 | 0.478 | 6,000개의 파라미터만으로 MPPI와 사실상 동일한 평균 오차 달성 |
| **Max Drift (m)** | 2.521 | 2.492 | 누적 오차의 최대치 역시 유사한 수준으로 방어 성공 |
| **Mean Heading Err (°)**| 0.22 | 0.46 | BC가 약간 높으나 제어에 무리가 없는 수준 |
| **Mean Velocity Err** | 0.16 m/s | 0.142 m/s | 속도 추종은 BC가 오히려 안정적 |



---


## 4. 향후 계획 (Stage 3: Next Action Plan)
현재의 BC 모델(Mapper)은 '단일 경로'에 특화되어 있으므로 일반화 능력이 부족하며, Closed-loop 환경에서의 누적 오차를 극복하지 못함. 따라서 다음 단계를 수행 예정.

1. **다중 경로 학습 (Generalization):** Blender에서 형태가 다른 다양한 궤적(직선, S자, U턴 등)을 추가 생성하고, MPPI로 통합 Golden Data를 추출하여 범용적인 BC 베이스라인 제어기를 재학습.
2. **새로운 궤적 테스트:** 학습된 통합 BC 모델을 전혀 새로운 경로(Test set)에 적용하여, 제어기가 주행의 형태는 유지하되 어느 정도의 궤도 이탈(Drift)을 발생시키는지 한계를 명확히 측정.
3. **Stage 3 - Residual RL 도입:** 위에서 발생한 궤도 이탈 오차(Residual)만을 실시간으로 0m로 보정하는 **잔차 강화학습(Residual RL)** 에이전트를 BC 모델 위에 결합하여 완벽한 자율주행 파이프라인을 완성.

