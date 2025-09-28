# 드론 PPO 학습 메모리 구조 및 관리

## 1. 필요한 정보 

- **num_envs = 8192**  
  → 병렬 환경 개수  

- **num_steps_per_env = 100**  
  → rollout 길이  

- **num_obs = 17** (`obs_cfg["num_obs"]`)  
  → 상태 벡터 크기  

- **num_actions = 4** (`env_cfg["num_actions"]`)  
  → 행동 벡터 크기  

- **dtype = torch.float32 (gs.tc_float)**  
  → 1 값 = 4 byte (32bit float)  

- **추가로 저장하는 버퍼**  
  - reward (`float32`, shape = [num_envs, num_steps])  
  - done/reset flag (`int`, shape = [num_envs, num_steps])   

---

## 2. 메모리 구조 (1 rollout = 100 step)

### (1) Observations
```
num_envs × num_steps × num_obs × 4 byte
= 8192 × 100 × 17 × 4
≈ 55.7 MB
```


- **정의**: 에이전트가 환경에서 관측하는 상태(state) 정보  
- **dtype**: float32 (4 byte)    
- **드론 예시**:  
  - 목표와의 상대 위치 (x,y,z)  
  - 드론 자세 (quaternion)  
  - 선속도, 각속도  
  - 직전 action  

-> 한 step마다 “드론이 지금 어떤 상태에 있는지”를 기록  
### (2) Actions
```
num_envs × num_steps × num_actions × 4
= 8192 × 100 × 4 × 4
≈ 12.5 MB
```

- **정의**: 에이전트가 환경에 내린 행동 값  
- **dtype**: float32 (4 byte)   
- **드론 예시**:  
  ```
  actions = [0.1, -0.3, 0.05, 0.2]  # 네 개 프로펠러의 rpm 조정 값
  ```  
-> 에이전트가 “드론을 이렇게 움직여라”라고 지시한 값  


### (3) Rewards
```
num_envs × num_steps × 1 × 4
= 8192 × 100 × 4
≈ 3.3 MB
```

- **정의**: 해당 step에서 받은 보상 값  
- **dtype**: float32 (4 byte)  
- **드론 예시**:  
  - 목표 위치와 가까워지면 +10  
  - 추락/crash 시 -10  
  - 진동이 심하면 -0.001  

-> 행동의 “잘했는지/잘못했는지”를 수치로 기록 

### (4) Done flags (int32)
```
num_envs × num_steps × 1 × 4
= 8192 × 100 × 4
≈ 3.3 MB
```

- **정의**: episode가 종료되었는지 여부 표시  
- **dtype**: int32 (4 byte)  
- **드론 예시**:  
  - 드론이 땅에 부딪힘 → done=1  
  - 에피소드 길이(15초) 초과 → done=1  
  - 아직 비행 중이면 → done=0  

-> “이 step에서 episode가 끝났는가?”를 나타내는 플래그
> Done flag 필요한 이유   
> 1. Episode 구분
> 2. Discounted return 계산 -> PPO는 보상 합계를 **discount factor (γ)** 로 누적해서 계산 ,`done=1`인 지점에서 **return/advantage를 0으로 초기화**해 줌.
> 3. Reset 타이밍 제어 -> `done=1`이면 해당 환경을 **reset**해서 드론을 다시 초기 위치로 돌림.
---

## 3.  총합
- Obs ≈ 55.7 MB  
- Act ≈ 12.5 MB  
- Rew ≈ 3.3 MB  
- Done ≈ 3.3 MB  

> **총합 ≈ 75 MB (1 rollout 기준)**  

---

## 4. 확장 계산
- Iteration 하나에서 rollout = 100 step  
- 만약 `max_iterations=301` →  
  ```
  301 × 75 MB ≈ 22.6 GB
  ```

> 메모리 전체를 다 저장한다면 이 정도 필요,  
> 하지만 PPO 구현에서는 rollout 끝나면 학습 후 discard → 항상 **“1 rollout 메모리”만 유지**

---

## 5.  정리
- 100 step(rollout) 경험 데이터 = 약 **75 MB**  
- GPU 메모리에는 이 정도만 상주 (학습 시 계속 overwrite)  
- Iteration이 쌓인다고 메모리가 선형 증가하지는 않음 (보통 1 rollout만 유지하고 매번 덮어씀)  

---



# PPO(Proximal Policy Optimization)에서 rollout discard 이유

## 1. On-policy 알고리즘의 특성
- PPO는 **On-policy (온폴리시)** 알고리즘  
- 의미: “현재 정책(policy)으로 얻은 데이터만 학습에 사용해야 한다”  
- 오래된 rollout 데이터는 이미 **이전 정책**에서 나온 것이므로 지금 정책과 분포가 달라짐 → 사용 불가  
>따라서 학습이 끝난 rollout 데이터는 더 이상 필요 없음 → discard  

---

## 2. 메모리 효율
- rollout 한 번 = 약 75 MB  
- 301 iteration을 모두 저장하면 ≈ 22.6 GB  
- 장기 학습에서는 TB 단위까지 커질 수 있음 → 비현실적  
- 따라서 메모리에 항상 “최근 rollout”만 유지하는 방식으로 효율 관리  

---

## 3. 학습 파이프라인
PPO 학습 루프는 보통 이렇게 진행:

1. **Rollout 수집**  
   - env.step() 반복해서 (obs, action, reward, done) 저장  
   - 길이 = num_envs × num_steps_per_env  

2. **Policy 업데이트**  
   - 수집된 rollout을 가지고 여러 epoch 동안 학습 (예: 5번 gradient descent)  

3. **버퍼 discard**  
   - rollout 사용 완료 → 메모리에서 버림  
   - 다시 env.step() 해서 새로운 rollout 수집  

> 즉, rollout은 **“임시 학습 데이터”**일 뿐, 장기 보존 대상이 아님  
