# 1.드론 학습 시간 단위

## 시간 단위 (dt)
```python
self.dt = 0.01  # run in 100hz
```

- 시뮬레이터의 기본 timestep = **0.01초**
- 즉, **1 step = 0.01초 (10ms)**
- 시뮬레이션은 100Hz로 동작 → 실제 드론 제어 주파수와 유사

---

## Episode 길이
```python
self.max_episode_length = math.ceil(env_cfg["episode_length_s"] / self.dt)
```

- `episode_length_s = 15.0` (env_cfg에서 지정됨)
- 15초 / 0.01초 = **1500 steps**
- 즉, 한 **에피소드 = 최대 1500 step (15초)**

---

## Training loop에서 1 step 의미
훈련 코드(`hover_train.py`)에서는  
`runner.learn() → env.step(actions)` 으로 진행됨.

- **시뮬레이터 안**: 0.01초가 흐름
- **에이전트 학습 입장**: 1개의 `(상태, 행동, 보상, 다음 상태)` transition 수집

> 학습 코드에서의 **1 step = 1 제어 주기(0.01초)**  
 Real world로 환산 시 → 드론이 0.01초 동안 동작한 것

---
## 학습 효율 계산 
- `num_steps_per_env = 100`
- `num_envs = 8192`
- `dt = 0.01`

-> 한 iteration(rollout)에서 모으는 simulated time:
```
100 × 8192 × 0.01 = 8192초 ≈ 2.27시간 * 약 2시간 15분
```

즉, 실제 드론 8192대를 0.01초 간격으로 100 step 굴린 효과 = **2.27시간치 데이터**  
→ 병렬 환경 덕분에 실제 시간은 몇 초 안 걸려도 수 시간~수 일치 데이터를 학습 가능

## num_envs 와 num_steps_per_env
```python
num_envs = 8192
num_steps_per_env = 100
```

- **num_envs = 8192**
  - 동시에 돌리는 병렬 환경 개수
  - 즉, 드론 시뮬레이터를 **8192대 동시에 복사해서 학습**

- **num_steps_per_env = 100**
  - 각 환경에서 한 번 `rollout`할 때 모으는 step 수
  - 즉, 드론 하나가 100 step = 1초 분량의 데이터를 수집

---

##  Episode vs Rollout

- **Episode**
  - reset ~ terminate 까지 한 번의 비행 시퀀스
  - 최대 1500 step (15초), 하지만 crash로 더 짧아질 수 있음

- **Rollout**
  - 학습을 위해 episode 안을 일정 step 단위(여기선 100 step)로 잘라서 모은 것
  - episode가 1500 step이면 rollout은 총 15개
  - episode가 800 step이면 rollout은 총 8개

> 즉, **episode는 비행 전체, rollout은 학습 단위**

---

##  왜 rollout을 쓰는가?

- **빠른 업데이트**
  - episode 전체(15초)를 다 기다리면 학습이 느려짐
  - rollout 단위(1초)마다 잘라 학습 → 훨씬 빠른 policy 개선

- **On-policy 알고리즘 특성**
  - PPO 같은 알고리즘은 최신 policy로 얻은 데이터만 써야 함
  - rollout 단위가 짧을수록 이전 policy와 데이터의 차이가 작음 → 안정적 학습


---

##  정리
- **dt = 0.01s → 1 step = 10ms**
- **Episode = 최대 1500 step (15초)**
- **Rollout = 100 step 단위로 episode를 잘라서 학습에 사용**
- **num_envs = 8192 → 드론을 8192대 병렬로 시뮬레이션**
- 따라서 매 iteration마다 **2.27시간치 데이터를 모아 학습**  


# 2. Real World vs World Model Space

- Genesis는 real world와 같은 시간 단위(초) 를 사용 -> 시뮬레이터 내부의 “물리적 시간”은 현실 세계와 1:1 매핑됨.

- 다만 GPU 병렬 연산으로 계산 속도를 극적으로 끌어올려,  
예를 들어 RTX 4090에서 Franka 로봇 팔은 실시간보다 430,000배 빠르게 시뮬레이션 가능.

- 하지만 이건 “시간 단위가 바뀐 것”이 아니라,  
  - 시뮬레이션 안에서 1초 = 현실의 1초  
    -> 단지 그 1초를 계산하는 데 걸리는 벽시계 시간이 훨씬 짧다는 의미.

## 요약

- Genesis는 모든 물리량에서 초(sec)를 시간 단위로 사용.

- real world와 world model space의 시간 단위는 동일.

- 다른 점은 계산 속도: 현실의 1초를 시뮬레이터에서는 몇 μs ~ ms 만에 계산할 수 있음.