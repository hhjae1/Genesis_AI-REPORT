# Sim2Sim Pipeline Implementation
> Based on "Trajectory-based Inverse Vehicle Dynamics" Methodology

 Blender의 제어 입력 $(T, S)$를 단순히 복사하는 것이 아니라, **결과적 움직임(Motion)인 가속도와 곡률 $(a, \kappa)$를 일치시키는 것**을 목표로 합니다.

---

## Step 1: Ground Truth Generation
**Data Extraction & Trajectory Definition**

이 단계는 Blender 시뮬레이션에서 기준이 되는 **목표 궤적(Target Trajectory)**을 정의하는 과정입니다.

* **Process**: Blender 시뮬레이션 로그(`blender_vehicle_log.csv`)에서 차량의 상태 $s_t$ (위치, 속도, 헤딩)를 추출합니다.
* **Computation**: 추출된 데이터를 바탕으로 Blender 차량이 실제로 구현한 물리량을 수치 미분으로 계산합니다.
  * 가속도: $a^B = \frac{\Delta v}{\Delta t}$
  * 곡률: $\kappa^B = \frac{\omega}{v}$
* **Output**: `blender_data_processed.csv`
  * 450 프레임 (약 18.75초) 분량의 Target Motion $(a^B, \kappa^B)$ 데이터셋 확보.

---

## Step 2: Golden Input Mining
**Offline Black-Box Optimization via MPPI**

[cite_start]Genesis 물리 엔진 내에서 Blender의 궤적을 완벽하게 재현할 수 있는 **"최적의 입력(Golden Input)"**을 역으로 찾아내는 과정입니다[cite: 118, 126]. 단순 탐색 대신 **MPPI (Model Predictive Path Integral)** 알고리즘을 사용하여 최적의 해를 효율적으로 탐색했습니다.

* [cite_start]**Problem**: Genesis의 물리 특성(마찰, 질량 등)이 다르기 때문에, 분석적인 역함수 $f^{-1}$를 구할 수 없습니다[cite: 81].
* **Method: MPPI Sampling-based Optimization**
  매 프레임 **State Reset**을 적용하여 독립적인 최적화를 수행했습니다.
  
  1. **Warm-start (Prior)**: Pure Feedforward 값을 평균($\mu$)으로 설정.
     * $T_{init} = a^B / 3.0$
     * $S_{init} = \kappa^B \cdot 2.8$
  2. **Sampling**: 초기 추정치 주변에서 Gaussian Noise를 추가하여 **200개의 병렬 샘플** 생성.
     * $T_{sample} \sim \mathcal{N}(T_{init}, 0.15^2)$
     * $S_{sample} \sim \mathcal{N}(S_{init}, 0.08^2)$
  3. **Evaluation**: Genesis 병렬 환경에서 시뮬레이션 후 Cost 계산.
     * $Cost = 1.0 \cdot |a^G - a^B| + 10.0 \cdot |\kappa^G - \kappa^B|$
  4. **Aggregation**: Cost에 기반한 Softmax 가중 평균으로 최적 입력 도출.
     * $w = \exp(-Cost / \lambda), \quad \lambda=0.1$
     * $(T^{\ast}, S^{\ast}) = \sum (w \cdot u_{samples}) / \sum w$

* **Output**: `golden_inputs.csv`
  * Genesis 환경에서 Blender와 동일한 움직임을 만들어내는 정답 제어 입력 데이터셋 생성.

---

## Step 3: Training the Input Mapper
**Supervised Learning**

Step 2에서 확보한 데이터를 바탕으로, 실시간으로 궤적을 제어 입력으로 변환해주는 **신경망(Input Mapper)** 을 학습시킵니다.

* **Architecture**: 3-Layer MLP (128-128-64), ReLU Activation, Dropout(0.1)
* **Dataset**:
  * **Input ($X$)**: 현재 속도($v$), 목표 속도($v_{target}$), 헤딩 오차($\psi_{error}$), 목표 가속도($a^B$), 목표 곡률($\kappa^B$)
  * **Label ($Y$)**: 최적화된 드라이브 $(T^{\ast})$ 및 스티어링 $(S^{\ast})$
* **Data Augmentation**: 헤딩 오차에 $\pm 30^\circ$ 범위의 섭동(Perturbation)을 추가하여 모델의 복원력(Robustness)을 강화했습니다.
* **Output**: `control_mlp_heading.pth`
  * 궤적 공간(Trajectory Space)의 요구사항을 Genesis 액추에이터 공간(Actuator Space)으로 번역하는 함수 근사.
  
  $$h_{\phi}(s_t, a, \kappa) \approx (T^{\ast}, S^{\ast})$$

---

## Step 4: Runtime Execution
**Hybrid Controller Implementation**

학습된 Mapper를 통해 실시간으로 Blender의 제어 의도를 Genesis용 입력으로 번역합니다.

* **Problem**: Step 2(State Reset)와 달리, 실제 Runtime에서는 오차가 누적되며 물리적 관성과 시스템 지연으로 인해 제어 타이밍이 어긋나는 문제가 발생합니다.
* **Solution (Hybrid Controller)**: MLP 추론 값에 아래의 보정 기법들을 결합했습니다.
  1. **Adaptive Feedback**: 헤딩 오차가 MLP 학습 분포($\pm 17^\circ$)를 초과할 경우 P-Control 피드백을 활성화하여 보정.
  2. **Look-ahead Steering**: 현재 시점($t$)이 아닌 미래 시점($t+N$)의 헤딩을 참조하여 물리적 지연을 선제적으로 보상. (속도와 미래 곡률에 따라 거리 동적 조절)
  3. **Predictive Braking**: 미래 곡률을 감지하여 급커브 진입 전 속도를 제한($4.5m/s$)하여 물리적 주행 안정성 확보.


https://github.com/user-attachments/assets/96a393fa-25f0-4722-9bb4-e70cb9bbc9a9


### Current Performance
| Metric | Value |
| :--- | :--- |
| **Velocity Ratio** | 95.5% |
| **Path Progress** | 95.2% |
| **Mean Drift** | 2.72 m |
| **Max Drift** | 6.21 m |

---

## Remaining Issues & Future Work

* **Issue**: 두 번째 좌회전 진입 타이밍이 빠름.
  * Look-ahead 기법이 직선 구간에서 다음 커브를 너무 일찍 감지하여, 의도보다 빠르게 조향을 시작하는 현상 발생.
  * 원인: 헤딩 기반 제어만으로는 차량이 현재 정확한 "경로 위"에 있는지 판단하기 어려움.
* **Proposed Solution**: 
  * **Cross-track Error** (횡방향 이탈 거리) 기반 제어 추가 도입.
  * 또는 위치 정보를 직접 활용하는 **Pure Pursuit** 알고리즘으로의 전환 검토 중.