# 1. Genesis에서의 Training 병렬 수행

## 1. 병렬 수행의 구조
- `num_envs = 8192` 처럼 설정하면  
  → 8192개의 환경(env)을 **병렬로 동시에 시뮬레이션**함. 
- 하지만 이 병렬화는 **CPU 스레드 기반이 아니라 GPU 병렬 연산 기반**  
  → 즉, GPU가 모든 환경을 **하나의 대규모 텐서(batch)** 로 묶어 **한 번의 CUDA 연산**으로 처리

---

## 2. “Training 병렬 수행(env 별)”의 의미
- 각 환경이 rollout 데이터를 독립적으로 생성하지만,  
  이 데이터는 GPU 상에서 **벡터 연산 형태로 동시에 학습에 사용**  
- 즉, 8192개의 환경이 각각 따로 학습하는 게 아니라,  
  **하나의 정책 네트워크가 공유**되어  
  수천 개 환경의 데이터를 **병렬 입력(batch)** 으로 받아 학습

---

## 3. 결론
> Genesis의 **training 병렬 수행(env 별)** 은  
> **CPU 스레드가 아닌 GPU 텐서 병렬화**로 이루어지므로  
> “thread 개수 설정”은 **불필요**  


# 2. Genesis / PPO — Training 메모리 구조 및 관리


## (1) 핵심 개념

| 항목 | 설명 |
| --- | --- |
| **네트워크 수** | 1개 (공유됨) |
| **파라미터 수** | 38,277개 ≈ 153 KB |
| **공유 구조** | 8192개 환경이 모두 이 한 네트워크를 참조 |
| **업데이트 방식** | PPO 학습 시, 이 하나의 네트워크 가중치가 계속 **덮어쓰기(overwrite)** 됨 |

즉,  

> 8192개의 환경이 각각 네트워크를 들고 있는 게 아니라,  
> **하나의 네트워크가 8192개 환경의 입력(batch)** 을 동시에 받아 행동을 내리고,  
> 학습 단계에서 그 **단일 네트워크의 가중치만 업데이트** 

---

## (2) 메모리 동작 순서

1️ . **Gathering 이후 (rollout 완료)**  
→ GPU 메모리에 `(obs, actions, rewards, dones)` 가 저장되어 있음

2 . **Training 시작**  
→ 이 데이터를 batch 단위로 꺼내서 PPO loss 계산  

3️ . **Backpropagation(역전파) 연산 (gradient 계산)**  
→ loss에 대한 gradient를 함  

4️ . **Optimizer step()**  
→ optimizer state(Adam의 m, v 값 등)를 이용해  
   `θ ← θ - α * m / sqrt(v + ε)` 형태로 업데이트  

- **m** = gradient들의 **이동 평균 (momentum)**  
- **v** = gradient들의 **제곱 이동 평균 (variance 추정)** — learning rate 조절  

> learning rate 조절 이유  
> - gradient가 너무 크면 → 한 번에
**너무 멀리 이동해서 overshoot (발산)**  
>- gradient가 너무 작으면
→ 이동이 너무 느려서 학습이 거의 안 됨


5️.  **새로운 정책 파라미터로 overwrite 완료**  
→ 즉, 기존 weight는 새로운 값으로 덮어써짐  
→ 이후 rollout은 업데이트된 정책으로 수행  

### Optimizer step은 왜 필요한가?
___

- Adam은 “단순한 기울기 하강법”을 **개선**한 방식입니다.  
문제는,  

- gradient가 noisy하거나 (보상이 불안정)  
- scale이 큰 파라미터와 작은 파라미터가 섞여 있으면  학습이 불안정해짐.  
>-> Adam은  **이전 gradient의 추세(momentum)** 와  **gradient의 크기(scale)** 를 추적하면서  **적응적(Adaptive)** 으로 보정

###  일반 gradient descent VS Adam Optimizer :



| 구분 | 일반 gradient descent | Adam |
| --- | --- | --- |
| **g_t** | 현재 gradient | 현재 gradient |
| **m_t** | 사용 안 함 | gradient의 이동평균 (방향) |
| **v_t** | 사용 안 함 | gradient 제곱의 이동평균 (크기 조절) |
| **효과** | 모든 파라미터에 동일한 learning rate | 파라미터별로 적응형 learning rate |
| **안정성** | 불안정함, 튀는 경우 많음 | 매우 안정적, noisy 데이터에 강함 |

---

## (3) 네트워크 관련 메모리 용량

| 항목 | 크기(대략) | 설명 |
| --- | --- | --- |
| **Policy/Value weights** | 153 KB | 실제 학습되는 가중치 |
| **Gradients** | 153 KB | backprop 시 일시적으로 생성 |
| **Adam moment buffers** | 2 × 153 KB ≈ 306 KB | m, v 상태 저장 |
| **합계** | 약 **612 KB** | 매우 작음 — 거의 고정 유지 |
