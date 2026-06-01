# MPPI + Optuna 기반 Golden Truth 탐색

## 1. MPPI 원리
 
**MPPI(Model Predictive Path Integral)** 은 sampling 기반 **stochastic MPC(Model Predictive Control)**

매 frame 실행:
1. **Sampling**: warm-start(이전에 구한 미래 10 frame S,T)를 기준으로 Gaussian noise 더해 N=2048 control sequence 생성 (각 horizon=10 steps) -> 첫 frame은 blender S,T로 start
2. **Rollout**: 각 sample을 Genesis에 imagination으로 forward 시뮬레이션
3. **Cost 계산**: 각 sample의 rollout 결과로 cost 평가
4. **Weighted average**:
   `weight_i = exp(-cost_i / λ)`
   `optimal = Σ weight_i × sample_i`
5. **Apply**: optimal의 첫 step만 real env에 적용, sliding window 한 칸 전진

```-> 즉, 다시 말해 설정한 env 만큼 S,T(horizon 10이니까 각 env별 10 frame)를 random sampling하여 각 env에 실행. random sampling은 이전 sequence 10 frame의 S,T를 warm-start로 잡고 random noise를 주는 방식. 그 후 각 env의 cost를 계산해 env별 가중평균으로 real env에 적용(한 frame씩).```

→ Black-box simulator에서 작동 (Genesis가 미분 불가능해도 OK). Gradient descent 방식 아님.

---

## 2. Cost 함수 설정 (7-term)

각 horizon step h마다:

```
cost_h = w_pos · |Δpos|                   # 위치 매칭
       + w_kappa · |Δkappa|               # 곡률 매칭
       + w_vel · |Δv|                     # 속도 매칭
       + w_heading · |Δheading|           # 방향 매칭
       + w_rate · |Δcontrol|              # smoothness
       + w_ff · |control - FF|            # FF anchor
       + w_accel · |Δa|                   # 가속 매칭
```

**7개 weight + λ (temperature) = 8개 hyperparameter**.

---

## 3. Optuna vs Grid Search



| | Grid Search | Optuna (TPE + Pruner) |
|---|---|---|
| 탐색 방식 | 격자 모든 조합 시도 | Bayesian (TPE), 좋은 영역 학습 |
| 효율 | 차원이 커지면 조합의 수 폭증 | 정해진 trial에 대해서만 파라미터 조합 수 설정 가능
| 조기 종료 | Pruner로 망한 trial 즉시 cut  | 동일 |
| 결과 품질 | 격자에 갇힘 | 연속값 최적화, 더 정밀 |

- **TPE = Tree-structured Parzen Estimator**

- **옛 grid search 시절 best**: W_KAPPA=50, W_HEADING=30, W_VEL=3 → mesh-contact era 0.52m  

- **Optuna로 찾은 best (dual-scene)**: w_pos=34572, w_kappa=25, w_heading=15, λ=0.013 → **main path 0.148m** (mesh-contact 의 3.5× 개선)

-> 기존의 **grid search** 방식은 직접 파라미터 조합에 대한 grid를 설정하여 grid의 파라미터 조합에 대한 결과들 중 best를 선정

-> 반면, Optuna 방식은 
1. 첫 10 trial(1 trial이 1개의 파라미터 조합)만 random sampling
2. 각 trial에 대한 cost를 계산하여 cost 순으로 정렬 
3. 그 후, 상위 γ%를 기준으로 good(l(x)), bad(g(x))를 나누어 각각의 파라미터 분포를 학습(해당 분포들은 trial 단위로 업데이트)
4. 다음 trial의 파라미터 조합은 l(x) / g(x)를 기준으로 추출(즉, good 분포 방향으로 파라미터 조합이 추출되게)

``` -> 즉, Grid search는 brute-forth 방식으로 차원이 커지면 파라미터 조합이 기하급수적으로 늘어 최적의 파라미터 조합을 찾기 어렵지만, Optuna 방식은 분포 학습 기반으로 좋은 영역에 집중 sampling 하여 효율적으로 최적의 조합을 찾기 수월함. (trial이 늘수록 분포가 정밀해져 최적에 수렴할 가능성 올라감) ```


---

## 4. 가설 검증 실험

### 4.1 가설

> 한 경로에서 찾은 best 파라미터 조합이 다른 경로들에도 잘 작동할 것이며, 다른 경로들의 best 파라미터도 그 근처로 수렴할 것이다.

근거: mesh-contact 시절 grid search로 찾은 best params (W_KAPPA=50, W_HEADING=30 등)가 5개 경로에서 비슷하게 수렴한 경험.

### 4.2 실험 설정

- **Main path**에서 Optuna 400 trial → **trial 264** best (0.148m mean drift)
- 그 params를 **8개 다른 경로** (hairpin, right, s_curve, sharp_right, slalom, ss_curve, straight_curve, wide_left)에 적용 → generalization 확인
- 추가로 각 경로마다 **trial 264 ±50% narrow Optuna 50 trial** → 근처 수렴 여부 확인

### 4.3 결과(mean drift) 

| Trajectory | FF baseline | Trial 264 generalization | Narrow Optuna (±50%) | 개선율 |
|---|---|---|---|---|
| ss_curve | 4.60 m | 0.69 m | 0.65 m | -5.8% |
| right | 11.80 m | 3.69 m | 3.39 m | -8.1% |
| sharp_right | 10.30 m | 3.84 m | 3.54 m | -7.9% |
| s_curve | 17.05 m | 7.76 m | 6.95 m | -10.5% |
| hairpin | 18.36 m | 10.99 m | 10.46 m | -4.8% |
| slalom | 19.00 m | 13.05 m | (pruning 실패) | - |
| wide_left | 20.31 m | 13.77 m | 13.14 m | -4.6% |
| straight_curve | 20.22 m | 15.91 m | 15.13 m | -5.0% |

### 4.4 가정의 부분적 기각

**모든 경로가 FF(Blender S,T)는 능가** (trial 264로 25-86% 개선) → 가정의 절반은 성립.

**하지만 drift가 trajectory마다 0.65m ~ 15.13m로 큰 편차를 보임**.

**Narrow ±50% search가 모든 경로에서 4~10%만 개선**. 즉:
- Trial 264 region은 *그 경로의 local optimum*까지는 도달
- 하지만 *진짜 global optimum*은 trial 264 region과 다른 영역에 있을 가능성 큼
- Sim2sim gap의 본질적 난이도는 trajectory의 특성(곡률 빈도, 속도 변화, 길이 등)에 좌우됨

→ **"비슷한 파라미터로 수렴" 가정은 ss_curve, right 같은 일부 경로에서만 성립. straight_curve, slalom 같은 어려운 경로는 다른 region에 global best 가능성.**

---

## 5. 결론 및 다음 단계

**경로마다 최적 파라미터를 따로 찾아야 한다.** -> 현재 각 경로에 대한 최적화 진행 중(400 trial로). 400 trial 기준 경로 당 5~6시간 소요(경로 평균 frame: 400)

**진행 중인 작업**:
- **Worst 3 trajectory (straight_curve, wide_left, slalom)** 에 대해 wide Optuna 400 trial 재실행 (각 경로의 진짜 global best 탐색)
- ETA ~18시간

**Pipeline 정리**:
```
Blender CSV → MPPI + Optuna (per trajectory)
              ↓
              Best params (per trajectory)
              ↓
              MPPI run with best params → Golden Truth (throttle, steer)
              ↓
              BC 학습 dataset
```

## 6. 질문

- perturbation(외란)을 주었을 때 RL로 해결하는 것을 ST Mapper가 어느정도의 일반화 성능이 되었을 때 진행해야(몇 개 정도의 경로를 최적화 시킨 뒤 진행해야)
