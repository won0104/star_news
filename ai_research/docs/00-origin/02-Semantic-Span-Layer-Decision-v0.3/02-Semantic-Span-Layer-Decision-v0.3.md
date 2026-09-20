# Semantic Span Layer Decision v0.3

## 결정

EVENT/STATEMENT semantic span의 static representation은 **KF-DeBERTa L8**로 고정한다.

| layer | dev exact micro-F1 | test exact micro-F1 | dev seed wins |
|---|---:|---:|---:|
| L8 | **0.4111** | **0.4204** | **3/3** |
| L10 | 0.3829 | 0.3863 | 0/3 |
| L12 | 0.3892 | 0.3947 | 0/3 |

Layer와 checkpoint는 dev exact character span + type micro-F1로만 선택했다. Test는 선택된 checkpoint의 안정성 확인에만 사용했다.

## 해석

L8은 L12보다 dev `+0.0219`, test `+0.0257` 높았다. 이는 Entity의 L12 선호와 달리 proposition boundary가 중간층 표현을 더 잘 활용한다는 근거다.

다만 L8도 test exact precision은 낮고 recall이 높다. 3-seed 평균은 EVENT `P=0.254/R=0.739/F1=0.378`, STATEMENT `P=0.316/R=0.812/F1=0.455`다. 따라서 L8 선택은 기존 start/end Head의 완성도를 뜻하지 않으며, 다음 label-conditioned span scorer가 해결해야 할 핵심은 false positive와 start/end 오결합이다.

상세 계약과 실제 문자열은 [DirectionTest 보고서](../../DirectionTest/Report-KF-Semantic-Span-Layer-Probe-v1.md)에 있다.

## 다음 gate의 static policy

```text
Entity        L12
Time          L10
Semantic Span L8
Trigger       L8
```

이 네 표현을 고정하고 기존 BIO/start-end와 learned-label-conditioned candidate span scorer를 같은 Gold/split/seed로 비교한다.
