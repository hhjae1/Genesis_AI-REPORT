
# 보상함수 원리

## 1️. 목표 값 정의 (hover_train.py)
```python
command_cfg = {
    "num_commands": 3,
    "pos_x_range": [-1.0, 1.0],
    "pos_y_range": [-1.0, 1.0],
    "pos_z_range": [1.0, 1.0],
}
```
- **"cfg"**: configuration(설정값)
- **num_commands**: 명령 벡터의 차원 수를 뜻함. 아래 총 3개의 위치벡터가 존재
- `x, y: [-1.0, 1.0] z: 1.0`으로 고정된 이 범위 내에서 무작위로 목표위치를 생성함 

> 드론은 일정시간마다 새롭게 무작위로 생성된 목표 좌표 `[x, y, z]`를 따라가야 함  
 

---

## 2️. 관측 및 행동 (hover_train.py)

### (1) 관측 (obs)
```python
obs_cfg = {
    "num_obs": 17,
    "obs_scales": {
        "rel_pos": 1/3.0,
        "lin_vel": 1/3.0,
        "ang_vel": 1/3.14159,
    }
}
```
- **num_obs = 17** : 총 17차원의 관측 벡터  *obs = observation (관측값)

-  **rel_pos (목표와의 상대 위치)** : 스케일링 계수 :  1/3.0 -> 3차원

- **lin_vel (선속도)** : 스케일링 계수 : 1/3.0 -> 3차원

- **ang_vel (각속도)** : 스케일링 계수  : 1/π -> 3차원

> 스케일링의 이유: 신경망(MLP)은 입력값의 범위에 굉장히 민감함.  
z = w₁x₁ + w₂x₂ + … + b  
신경망의 한 뉴런은 위의 식과 같이 계산되는데 만약, x1 = 100, x2 = 0.01이라면 w2가 학습되어도 x1 값이 너무 커서 값이 큰 입력 특징만 네트워크 출력에 강하게 반영됨. 따라서 모든 관측값을 **비슷한 크기**로 맞추어야 신경망이 균일하게 학습할 수 있음.  

위 코드 외 스케일링이 없는 구성요소(아래 코드에 근거)

- **base_quat (드론자세, 쿼터니언)** -> 4차원
- **last_actions (직전 액션, 프로펠러 4개)** -> 4차원  
   
   3 + 3 + 3 + 4 + 4 이렇게 총 17차원
```python
self.obs_buf = torch.cat(
    [
        torch.clip(self.rel_pos * self.obs_scales["rel_pos"], -1, 1),
        self.base_quat,
        torch.clip(self.base_lin_vel * self.obs_scales["lin_vel"], -1, 1),
        torch.clip(self.base_ang_vel * self.obs_scales["ang_vel"], -1, 1),
        self.last_actions,
    ],
    axis=-1,
)
```
이렇게 관측한 17차원의 벡터를 Actor 네트워크로 통과시킴

### (2) Actor 네트워크 (행동)



![alt text](images/MLP구조.gif)

**구조:**

sₜ(17) → Linear(17→128) → tanh → Linear(128→128) → tanh → Linear(128→4) = aₜ

Actor 네트워크는 위 그림과 같이 MLP(Multi-Layer Perception)구조로 설명 가능  
1. Input layer(입력층)  
- 드론 환경에서는 17차원의 관측값이 들어감. 즉, 입력층은 총 17개의 뉴런으로 구성.  
2. Hidden Layer 1,2 (은닉층)
- 드론 Actor 네트워크는 두 개의 은닉층을 가짐
- 각 뉴런은 다음과 같이 계산됨  
  z = Σᵢ (wᵢ·xᵢ) + bgit commit -m "Update reward function doc with Unicode equations"
  
여기서 가중치 w는 입력 특징의 영향력을 조절하고, 편향 b는 입력이 0일 때도 안정적으로 동작하기 위해 뉴런이 일정 출력(기본값)을 내도록 해줌.  
- 각 은닉층에는 128개의 뉴런이 있고, 활성화 함수로 `tanh` 사용 
>활성화 함수로 **tanh** 쓰는이유:  
드론의 관측값(obs)들도 스케일링 덕분에 범위가 [-1, 1]로 정규화 되어 있기 때문에 네트워크 내부 표현도 같은 범위로 맞춰지면 학습이 안정적
3. Output Layer (출력층)  
- 출력층은 4차원으로 프로펠러 제어 (M1~M4 RPM 변화량)를 함  

4. Actor 네트워크 전체 파라미터 수 (가중치 수 + 편향 수)

- **첫 번째 레이어 (17 → 128)**  
17 × 128 + 128 = 2176 + 128 = 2304  

- **두 번째 레이어 (128 → 128)**  
128 × 128 + 128 = 16384 + 128 = 16512  

- **세 번째 레이어 (128 → 4)**  
128 × 4 + 4 = 512 + 4 = 516  

> 2304 + 16512 + 516 = 19332  
총 19332개


위와 같은 구조로 관측값들이 Actor 네트워크를 통과하여 행동함.

---

## 3. 보상 함수 (hover_env.py)
드론의 현재 상태(state)와 행동(action)에 따라 보상(reward)을 계산.  
보상 함수들: `_reward_target`, `_reward_smooth`, `_reward_yaw`, `_reward_angular`, `_reward_crash`  
→ 결과는 `rew_buf`에 스텝별 보상 저장    * buf = buffer(임시 저장 공간)

```python
reward_cfg = {
        "yaw_lambda": -10.0,
        "reward_scales": {
            "target": 10.0,
            "smooth": -1e-4,
            "yaw": 0.01,
            "angular": -2e-4,  
            "crash": -10.0,
        }
```
보상 함수에서 계산된 함수값에 위 스케일들이 각 각 곱해져 최종 보상에 들어감

---

### (1) `_reward_target`
```python
def _reward_target(self):
    target_rew = torch.sum(torch.square(self.last_rel_pos), dim=1) \
               - torch.sum(torch.square(self.rel_pos), dim=1)
    return target_rew
```
target_rew = ∥last_rel_pos∥² − ∥rel_pos∥²

- `last_rel_pos`: 이전 드론 위치와 목표 위치의 차이 벡터  * rel = relative
- `rel_pos`: 현재 드론 위치와 목표 위치의 차이 벡터  


> 현재 드론이 목표에 가까워지면 rel_pos가 작아짐 ->  target_rew > 0 이므로 보상  
멀어지면 rel_pos가 커짐 -> target_rew < 0 이므로 페널티

---

### (2) `_reward_smooth`
```python
def _reward_smooth(self):
    smooth_rew = torch.sum(torch.square(self.actions - self.last_actions), dim=1)
    return smooth_rew
```

smooth_rew = ∥actions − last_actions∥²
- `actions`: 현재 제어 입력  
- `last_actions`: 이전 제어 입력  



> 스케일 값이 음수이므로  
smooth_rew 값이 커질수록(액션 변화가 클수록) 페널티  -> 급격한 제어 억제, 부드럽게 움직이게 함

---

### (3) `_reward_yaw`
```python
def _reward_yaw(self):
    yaw = self.base_euler[:, 2]
    yaw = torch.where(yaw > 180, yaw - 360, yaw) / 180 * 3.14159
    yaw_rew = torch.exp(self.reward_cfg["yaw_lambda"] * torch.abs(yaw))
    return yaw_rew
```
yaw_rew = exp(yaw_lambda · |yaw|)

- `base_euler[:, 2]`: 드론의 yaw(방향각)  * euler = euler angles -> 3차원 공간에서 물체의 회전을 나타내는 방법
- `yaw_lambda`: 보상 계수 (-10.0)  


> Yaw 오차가 커질수록 보상 감소  
-> “드론이 목표 바라본 상태 유지”

---

### (4) `_reward_angular`
```python
def _reward_angular(self):
    angular_rew = torch.norm(self.base_ang_vel / 3.14159, dim=1)
    return angular_rew
```
angular_rew = ∥base_ang_vel / π∥

- `base_ang_vel`: 드론 각속도 벡터 * ang_vel = angular velocity 


> 스케일 값이 음수이므로  
angular_rew값이 커질수록(드론이 많이 흔들릴수록) 더 높은 페널티  -> “안정적 호버링”  



---

### (5) `_reward_crash`
```python
def _reward_crash(self):
    crash_rew = torch.zeros((self.num_envs,), device=gs.device, dtype=gs.tc_float)
    crash_rew[self.crash_condition] = 1
    return crash_rew
```
crash_rew = 1 (추락 시), 0 (정상)
- `crash_condition`: 드론 추락/범위 이탈/지면 충돌 여부  


> 스케일 값이 음수이므로  
crash_rew 값이 1일 때(추락 시) 큰 패널티  

---

## 4. Critic 네트워크와 $V(s_t)$  

![alt text](images/MLP구조.gif)

- Actor 네트워크와 같은 MLP 구조(마지막 출력값만 1차원으로 다름)
- 입력: 드론 상태 관측값 (17차원)  
- 출력: 스칼라 값 1개 = V(sₜ)  

네트워크 구조: 

sₜ(17) → Linear(17→128) → tanh → Linear(128→128) → tanh → Linear(128→1) = V(sₜ)

> V(sₜ): 현재 상태가 앞으로 얼마나 좋은 보상을 가져올지를 추정하는 값 -> **Advantage** 계산에 사용 

 Critic 네트워크 전체 파라미터 수 (가중치 수 + 편향 수)

- **첫 번째 레이어 (17 → 128)**  
17 × 128 + 128 = 2176 + 128 = 2304  

- **두 번째 레이어 (128 → 128)**  
128 × 128 + 128 = 16384 + 128 = 16512  

- **세 번째 레이어 (128 → 1)**  
128 × 1 + 1 = 128 + 1 = 129  

> 2304 + 16512 + 129 = 18945  
총 18945개

---

## 5. Advantage 계산 (GAE(Generalized Advantage Estimation))
TD-error(Temporal Difference-error) 시간차 오차:  

δₜ = rₜ + γ·V(sₜ₊₁) − V(sₜ)

> 위 식은 현재 한 행동이 예상보다 얼마나 좋았는가/나빴는가를 판단  
-> 따라서 실제 결과가 예상 V(sₜ) 보다 좋으면 행동 확률을 증가시키고, 나쁘면 확률을 감소시킨다.

GAE:  
Aₜ = δₜ + (γλ)δₜ₊₁ + (γλ)²δₜ₊₂ + …

- rₜ = 보상 함수 결과  
- V(sₜ) = Critic 네트워크 예측  
- γ = 0.99 : 미래 보상 중요도  
- λ = 0.95 : 얼마나 길게 누적할지  

> Advantage도 δₜ와 같은 성격을 띔  
Aₜ > 0 → 행동 강화  
Aₜ < 0 → 행동 억제  

---

## 6. PPO Loss(Proximal Policy Optimization Loss)
### (1) Actor Loss 

L_actor = Eₜ[ min(rₜ(θ)·Aₜ , clip(rₜ(θ), 1−ε, 1+ε)·Aₜ) ]

- rₜ(θ) = π_θ(aₜ|sₜ) / π_old(aₜ|sₜ) 
  (새 정책과 이전 정책의 행동 확률 비율)  -> 새 정책이 예전 정책보다 행동 확률을 얼마나 바꿨는가

> min 을 쓰는 이유: **cliping** 효과를 제대로 반영해서 정책 업데이트를 보수적으로 제한하기 위함


- **clip**:  

 clip(rₜ(θ), 1−ε, 1+ε)

  rₜ(θ) 이 너무 커지거나 작아지면 정책이 급격히 변한다는 뜻 → 확률 변화량 제한 (안정성 확보)  

> Aₜ > 0 → 행동 확률 증가  
 Aₜ < 0 → 행동 확률 감소  
 Actor Loss를 줄이는 방향으로 Actor 네트워크 가중치, 편향을 업데이트  
 -> 앞으로 비슷한 상황에서 더 좋은 RPM 조합을 선택하도록 학습

---

### (2) Critic Loss

L_critic = (Rₜ − V(sₜ))²

- Rₜ = 실제 return (누적 보상)  
- V(sₜ) = Critic 예측 값  

>Critic Loss를 줄이는 방향으로 Critic 네트워크 가중치, 편향을 업데이트  
→ 다음에는 상태 가치를 더 정확히 예측하도록 학습

---

## 최종정리 

1. **목표 값**  
    - 드론이 따라가야 할 [x,y,z] 좌표 설정 

2. **관측 및 행동**  
    - 드론이 현재 어디 있는지, 속도는 어떤지, 목표와 얼마나 떨어져 있는지와 같은 것을 관측함.  
    ex) 드론의 선속도, 각속도, 목표와의 상대 위치 등의 17차원을 관측
    - 이 관측값(obs)을 **Actor 네트워크**로 통과시켜 드론이 행동하게 함. (처음에는 무작위 초기화된 네트워크에 통과시켜 의미없는 행동을 함.) 
    
3. **보상 함수**  
    - 목표 값과 드론 상태를 비교해서 보상 rₜ 계산  

3. **Critic 네트워크**  
    - 상태(관측값) sₜ를 입력받아 V(sₜ) 예측  

4. **Advantage (GAE)**  
    - rₜ와 V(sₜ), V(sₜ₊₁)를 이용해 Aₜ 계산  

5. **PPO Loss**  
   - 계산된 loss로 loss의 기울기를 구해(Backpropagation) 각 네트워크의 가중치와 편향을 업데이트  
   -> Gradient Descent(경사 하강법)
