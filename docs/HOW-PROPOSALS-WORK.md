# 🦦 제안은 어떻게 만들어지나 — 무엇을 보고, 무엇을 쌓고, 무엇을 근거로

> **이 문서는 [HOW-IT-WORKS.md](HOW-IT-WORKS.md)의 ⑤ "제안받는다"를 확대한 part 문서다.**
> pouch가 "이거 내리자 / 저거 올리자 / 이거 써봐"를 **어떤 데이터를 보고, 어떤
> 로직으로** 만들어내는지 코드를 안 열어도 따라갈 수 있게 쓴다. 같이 개발할
> 사람과 이 부분을 같이 뜯어보려고 만든 문서다.
>
> 읽는 법은 HOW-IT-WORKS와 같다 — 막히는 단어는 표시해뒀다가
> [GLOSSARY.md](GLOSSARY.md)로 넘긴다.

---

## 먼저, 가장 큰 오해 하나를 정면으로

`pouch catalog list --sources`를 치면 지금 **198개**가 대기 중으로 뜬다. 여기서
자연스럽게 드는 생각:

> "이 198개 중에서 pouch가 나한테 맞는 걸 골라 제안해주는 거지?"

**아니다.** 이게 이 문서에서 가장 먼저, 가장 크게 짚어야 할 사실이다.

> **소스 스테이징에 있는 것은 제안 엔진이 아예 쳐다보지 않는다.**
> pouch의 모든 제안("내리자·올리자·이거 써봐")이 보는 재료는 딱 둘뿐이다 —
> **① 사용 기록(`usage.jsonl`)** 과 **② 카탈로그(진입한 도구)**. 소스는 둘 다 아니다.

소스는 "백과사전에 그 페이지가 있다"는 표시일 뿐, pouch는 그걸 **일부러 못 본
척한다**(HOW-IT-WORKS ①의 "진입하면 뭐가 달라지나" 표). 그래서 지금처럼
카탈로그 3개·소스 198개인 상태에서 `pouch evolve`를 돌리면, **제안할 재료가
거의 없다** — 198개는 제안 풀에 없고, 카탈로그 3개는 아직 사용 기록이 얕기 때문이다.

그럼 네 원래 직관("소스에 있는 걸 제안받는다")은 완전히 틀렸나? 아니다. **한
단계가 빠져 있을 뿐이다.** 정확한 문장은 이렇다:

> **소스에 있는 것을 "쓰면", pouch가 그걸 카탈로그로 올리고(진입), 그 다음부터
> 제안에 잡힌다.** 제안의 방아쇠는 "소스에 있음"이 아니라 "실제로 씀"이다.

이 한 단계(**실사용 → 진입 → 제안**)가 이 문서 전체의 뼈대다. 아래에서 데이터가
어떻게 흐르는지 처음부터 따라간다.

---

## 제안의 유일한 연료: "무엇을 썼는가"

pouch의 제안은 감이나 큐레이션이 아니다. **오직 하나의 사실**에서 나온다 —
*"내가 어떤 도구를, 언제, 몇 번 썼는가."* 이 사실이 `usage.jsonl`에 쌓이고,
집계되고, 임계값과 만나 제안이 된다.

```text
   ④ 기록된다              집계                 임계 판정              제안
 usage.jsonl 한 줄씩  →  entry_id별로 접기  →  "안 쓴 지 30일?"  →  "내리자"
 (무엇을·언제)          (횟수 + 최근성)       "최근 7일 썼나?"      "올리자"
                                              "3회+ 썼나?"          "이거 써봐"
```

이 파이프라인을 왼쪽부터 하나씩 본다.

---

## 1단계 — 무엇이 "한 번의 사용"으로 쌓이나

도구를 쓸 때마다 Claude Code가 `pouch evolve log`를 부르고(③에서 건 hook),
그게 `usage.jsonl`에 **한 줄**을 덧붙인다. 한 줄의 모양:

```json
{"entry_id": "exa", "ts": "2026-07-14T16:06:00"}
```

**중요 — 모든 도구 사용이 기록되는 게 아니다.** 무엇이 한 줄이 되는지는 딱 세
경우뿐이다([tracker.py](../src/pouch/evolution/tracker.py)의 `entry_id_from_payload`):

| Claude Code가 부른 것 | 기록되는 entry_id | 설명 |
| --- | --- | --- |
| `Skill` 호출 | `tool_input.skill` 값 | 스킬 이름이 곧 카탈로그 id |
| `mcp__<서버>__<도구>` 호출 | `<서버>` | MCP 연결(linked)의 서버 이름 |
| `Bash`·`Edit`·`Read` 등 | **기록 안 함(None)** | 카탈로그 도구가 아니므로 추적 대상 아님 |

여기서 **구조적인 사각지대**가 하나 생긴다. 훅·규칙·에이전트는 실행돼도
`usage.jsonl`에 흔적을 안 남긴다(Skill/MCP 호출이 아니니까). 그래서 pouch는
이들에 대해 "안 쓴다"를 **판별할 수 없다** — 이 사실이 뒤(drop 판정)에서 중요한
예외로 되돌아온다.

기록은 **best-effort**다. 무슨 일이 있어도 hook은 exit 0으로 조용히 성공한다 —
사용 추적이 네 작업을 막는 일은 절대 없다([commands.py](../src/pouch/evolution/commands.py)의 `log`).

- 무엇이 1회 사용인가: [src/pouch/evolution/tracker.py](../src/pouch/evolution/tracker.py)
- 한 줄 append: [src/pouch/evolution/usage_log.py](../src/pouch/evolution/usage_log.py)

---

## 2단계 — 흩어진 줄을 도구별 통계로 접는다

`usage.jsonl`은 그냥 사건의 나열이다. 제안을 하려면 이걸 **도구별로** 접어야
한다. 접으면 도구마다 두 숫자가 나온다([aggregate.py](../src/pouch/evolution/aggregate.py)):

- **count** — 총 몇 번 썼나 (보조 신호)
- **last_used** — 마지막으로 쓴 시각 (주축 신호 — "최근성"이 핵심이다)

접는 과정에 두 가지 보정이 들어간다. 둘 다 "같은 도구인데 다르게 세는" 사고를 막는다.

### 보정 ①: 별명 접기 (canonicalize)

Claude Code는 플러그인에서 온 도구를 `plugin_아무개_exa` 같은 **런타임 별명**으로
부른다. 카탈로그엔 `exa`로 적혀 있는데 기록엔 `plugin_아무개_exa`로 쌓이면 둘이
같은 도구인 줄 모른다. 그래서 집계 시 **별명을 정식 이름으로 접어서** 센다
(`canonicalize_stats` + 카탈로그의 `alias` 칸).

> 이 보정이 왜 중요한가 — 안 접으면 "exa를 5번 썼다"가 카탈로그 `exa`에 안 닿아,
> 잘 쓰는 도구를 "한 번도 안 썼네, 내리자"로 **오분류**한다.

### 보정 ②: 오래된 기록 접기 (compaction)

180일보다 오래된 개별 기록은 요약(`usage-summary.json`)으로 접힌다. 개별 시각은
흐려지되 "총 몇 번"은 영구 보존된다. 제안 판정은 **접힌 요약 + 최근 상세를 합친
전체 통계**(`full_stats`) 위에서 돈다 — 200일 전 열심히 쓴 도구를 "never-used"로
잘못 보지 않기 위해서다([compaction.py](../src/pouch/evolution/compaction.py)).

---

## 3단계 — 통계가 임계값과 만나 다섯 종류의 제안이 된다

이제 도구별 통계(`count`, `last_used`)가 준비됐다. 여기에 임계값을 대면 제안이
나온다. 제안은 다섯 종류이고, **각각 보는 재료와 임계가 다르다.** 이 표가 이
문서의 심장이다:

| 제안 | 무엇을 근거로 | 임계 | 무엇을 보나 | 코드 |
| --- | --- | --- | --- | --- |
| 🌊 **내리자 (drop)** | 활성 표면 도구가 안 쓰임 | never-used(설치 후 14일 유예 지남) / stale(30일 안 씀) | **카탈로그∩표면** | [candidates.py](../src/pouch/evolution/candidates.py) |
| 🧲 **다시 올리자 (reattach)** | 카탈로그에 있는데 표면엔 없고, 최근 씀 | 최근 **7일** 내 1회+ | **카탈로그** | [attach.py](../src/pouch/evolution/attach.py) |
| ＋ **편입 안내 (adopt)** | 카탈로그 **밖**인데 자주 씀 | 최근 7일 내 **3회+** | **usage(카탈로그 밖)** | [attach.py](../src/pouch/evolution/attach.py) |
| 🔌 **플러그인 조언 (advice)** | 플러그인이 관리하는 도구 사용 | stale 넘으면 suggest_off, 아니면 reinforce | **카탈로그(surface=plugin)** | [advice.py](../src/pouch/evolution/advice.py) |
| 💡 **이거 써봐 (try-this)** | 반복해 쓰는 도구와 "비슷한" 것 | 설명 토큰 **2개+** 겹침 | **카탈로그** | [similar.py](../src/pouch/evolution/similar.py) |

표에서 "무엇을 보나" 칸을 다시 읽어보라. **다섯 개 중 소스 스테이징을 보는 건
하나도 없다.** 넷은 카탈로그를, 하나(adopt)는 카탈로그 밖 usage를 본다. 소스는
어디에도 없다 — 서두의 오해가 여기서 구조로 확인된다.

각 제안을 조금 더 풀어 쓴다.

### 🌊 내리자 (drop) — 두 단계 후보

활성 표면(연장통)에 올라와 있는데 사용 신호가 없는 도구를 고른다. 두 단계로 나뉜다:

- **never-used** (강한 후보) — 설치하고 14일(유예)이 지나도록 **한 번도 안 씀**.
  "추천이 헛맞았나."
- **stale** (약한 후보) — 썼지만 마지막 사용이 30일을 넘음. "졸업했나."

여기 아까 예고한 사각지대가 되돌아온다. **훅·규칙·에이전트는 drop 후보에서
빠진다** — 사용 신호가 원래 안 찍히는 종류라 "기록 없음 = 안 쓰임"이 성립하지
않기 때문이다(`has_usage_signal`). 이걸 내리려면 `pouch catalog uninstall <id>`로
손수 내린다.

### 🧲 다시 올리자 (reattach) vs ＋ 편입 (adopt)

둘 다 "최근에 쓴 걸 주머니로 당기자"지만 대상이 다르다:

- **reattach** — 이미 카탈로그에 아는 도구인데 표면에서 내려가 있음. 1회만 써도
  신호다("내가 아는 걸 다시 찾았다"). 동의하면 자동으로 표면에 올린다.
- **adopt** — 카탈로그 **밖**의 낯선 도구. 우연일 수 있어 **3회 이상** 써야
  신호다. pouch가 자동으로 담지 않고 `pouch catalog import`로 편입하라고 **안내만** 한다.

reattach의 7일 창이 drop의 30일보다 **짧다**는 게 의도된 설계다 — 같은 도구가
내려갔다 올라갔다 **진동하는 게 구조적으로 불가능**해진다(30일째 내려간 도구의
옛 기록이 7일 창에 안 걸림).

### 🔌 플러그인 조언 (advice)

표면을 플러그인 시스템이 관리하는 도구는 pouch가 올리고 내릴 권한이 없다. 그래서
**행위 대신 조언만** 한다 — 최근 잘 쓰면 "reinforce(그대로 두세요)", 오래 안 쓰면
"suggest_off(ECC에서 꺼볼까요, pouch가 직접은 안 내려요)". **한 번도 관측 못 한
플러그인 도구는 침묵한다** — "본 적 없으니 꺼"는 추측이라 안 한다.

### 💡 이거 써봐 (try-this)

네가 반복해 쓰는 도구(reattach·adopt 앵커)를 잡고, 그와 **비슷한** 카탈로그 도구를
곁들여 제안한다. "비슷하다"를 지어내지 않는 게 핵심이다 — 도구가 달고 온
**설명·태그·id의 토큰이 2개 이상 겹칠 때만** 비슷하다고 보고, 왜 비슷한지(겹친
토큰)를 함께 보여준다([pool.py](../src/pouch/evolution/pool.py) + [similar.py](../src/pouch/evolution/similar.py)).

> **여기 명시적 한계가 박혀 있다:** `pool.py` 주석에 "풀 v0 = 카탈로그. 바깥 마켓
> 소스는 나중"이라고 못박혀 있다. 즉 try-this가 "비슷한 것"을 찾는 창고는
> **카탈로그뿐**이고, 소스 198개는 후보에 없다. 이게 서두 오해의 코드 레벨 근거다.

---

## 4단계 — 소스가 제안 레이더에 잡히려면: reconcile

그럼 소스 198개는 영영 제안 못 받나? 아니다. **문 하나가 있다 —
`reconcile`(실사용 → 진입).** 이게 네 원래 직관과 코드를 잇는 유일한 다리다.

`pouch evolve`는 제안 목록을 띄우기 **전에**, 동의 없이 두 가지를 조용히 한다:

1. **compaction** — 오래된 기록 접기(위 2단계).
2. **reconcile** — **소스에 재워둔 것 중 이번에 실제로 쓴 게 있으면 카탈로그로
   진입시킨다.** 화면에 `📥 실제로 쓴 도구 N개가 카탈로그에 진입했어요`로 뜬다.

진입 조건은 순수 함수 하나로 요약된다([reconcile.py](../src/pouch/evolution/reconcile.py)의 `promote_candidates`):

> **소스에 있고(source) + 카탈로그엔 아직 없고(not catalog) + 사용 기록에 나타남(usage)**

문턱은 **딱 한 번**이다(adopt의 3회 방어가 여기선 불필요 — 그 번들을 일부러
import한 사실이 이미 우연을 걷어냈으니까). 그리고 진입은 **단조**다 — 한번
들어오면 소스를 다시 안 건드려서, drop이 도구를 내려도 소스↔카탈로그가 진동하지 않는다.

**그래서 전체 흐름은 이렇게 이어진다:**

```text
 소스에 재워둠        한 번 씀            evolve 실행           이제 제안에 잡힘
 (import)      →   usage.jsonl에    →   reconcile가 소스에서  →  drop·reattach·
 [제안 안 잡힘]      한 줄 쌓임           찾아 카탈로그로 진입     try-this 후보가 됨
```

소스를 카탈로그로 올리는 문은 reconcile 말고 둘 더 있다(둘 다 "일부러 고른 것"이라
소스를 건너뛴다): **`pouch catalog install <id>`**(손수 올림)와 **`pouch set
apply`**(세트 적용). 셋 다 결국 [promote.py](../src/pouch/catalog/promote.py)의
단일 진입 연산을 거친다.

---

## 그래서 지금(카탈로그 3·소스 198) 제안이 비어 보이는 이유

이제 서두의 관찰이 완전히 설명된다:

- **소스 198개** — 제안 풀에 없다. 한 번도 안 썼으니 reconcile도 안 걸렸다.
  pouch 입장에선 "존재는 아는데 관심 없는 것".
- **카탈로그 3개**(aws-mcp·context7·exa, 전부 linked) — 제안 풀엔 있지만, 사용
  기록이 얕으면 임계(30일 stale·7일 재사용·3회 편입)에 안 걸려 조용하다.

**이건 버그가 아니라 관문 "다" 정책의 의도된 결과다.** 옛날엔 import가 200개를
몽땅 카탈로그로 직행시켜 "내가 진짜 뭘 쓰는지" 신호가 묻혔다. 지금은 뒤집어서 —
**쓰는 것만 카탈로그에 올라오고, 카탈로그에 올라온 것만 제안받는다.** 제안이
조용한 건 "아직 실사용 데이터가 안 쌓였다"는 정직한 신호다.

---

## 알려진 구멍 (동료와 같이 볼 지점)

문서를 정직하게 유지하려고, 지금 **배선이 덜 됐거나 의도적으로 좁혀둔 곳**을 모아둔다:

1. **init의 낱개 추천이 배선 전이다.** "역할·스택 토큰 → 카탈로그 도구 매칭"
   계산은 [recommend.py](../src/pouch/catalog/recommend.py)에 `recommend()`로
   짜여 있지만 `init`이 이걸 부르지 않는다. 게다가 콜드 스타트엔 카탈로그가 비어
   후보 자체가 없다 — 그래서 콜드 스타트의 답은 낱개 추천이 아니라 **세트**다.
2. **try-this 풀 = 카탈로그 v0.** 바깥 마켓·소스 스테이징에서 "비슷한 것"을 찾는
   건 아직 안 한다(`pool.py` 주석에 명시). 소스 198개는 try-this 후보에 안 든다.
3. **매칭 신호가 태그 → 설명 토큰으로 옮겨졌다.** 실측상 태그가 거의 죽어 있어
   (0/201), 설명 토큰 겹침으로 매칭한다. 설명은 태그보다 시끄러워 **최소 2개
   겹침**으로 노이즈를 막는다([similar.py](../src/pouch/evolution/similar.py)).
4. **feedback·user 기억은 낡음 자동 감지가 없다** — 이건 제안이 아니라 기억
   생애주기 쪽 구멍이다(HOW-IT-WORKS 참조).

---

## 소스 파일 지도 — 제안 파이프라인만

| 단계 | 파일 | 역할 |
| --- | --- | --- |
| 기록 | [evolution/tracker.py](../src/pouch/evolution/tracker.py) | PostToolUse 페이로드 → entry_id (무엇이 1회 사용인가) |
| 기록 | [evolution/usage_log.py](../src/pouch/evolution/usage_log.py) | `usage.jsonl` append-only 읽기·쓰기 |
| 집계 | [evolution/aggregate.py](../src/pouch/evolution/aggregate.py) | 도구별 count+last_used, 별명 접기(canonicalize) |
| 집계 | [evolution/compaction.py](../src/pouch/evolution/compaction.py) | 180일 밖 기록 요약으로 접기(무손실) |
| 제안 | [evolution/candidates.py](../src/pouch/evolution/candidates.py) | drop 후보(never-used·stale) + 신호 없는 종류 제외 |
| 제안 | [evolution/attach.py](../src/pouch/evolution/attach.py) | reattach·adopt·observe 후보 |
| 제안 | [evolution/advice.py](../src/pouch/evolution/advice.py) | 플러그인 도구 조언(reinforce·suggest_off) |
| 제안 | [evolution/pool.py](../src/pouch/evolution/pool.py) · [similar.py](../src/pouch/evolution/similar.py) | try-this — 카탈로그에서 비슷한 것 찾기 |
| 진입 | [evolution/reconcile.py](../src/pouch/evolution/reconcile.py) | 실사용 → 소스에서 카탈로그로 진입 결정 |
| 진입 | [catalog/promote.py](../src/pouch/catalog/promote.py) | 소스 → 카탈로그 단일 진입 연산 |
| 엮기 | [evolution/orchestrate.py](../src/pouch/evolution/orchestrate.py) | 위 순수 함수들을 읽기(IO)와 이어 붙이는 planner |
| 입구 | [evolution/commands.py](../src/pouch/evolution/commands.py) | `pouch evolve` — reconcile→제안→동의→실행 |
| 먼저 내밀기 | [evolution/session_nudge.py](../src/pouch/evolution/session_nudge.py) · [nudge.py](../src/pouch/evolution/nudge.py) | 세션 시작 때 "정리할 게 쌓였어요" 쪽지(개수만, 물러남 있음) |

---

## 한 줄 결론

> **pouch의 제안은 "소스에 뭐가 있나"가 아니라 "내가 뭘 썼나"에서 나온다.**
> 소스는 못 본 척 대기하고, 사용 기록이 유일한 연료이며, 카탈로그가 유일한 후보
> 풀이다. 소스가 제안 레이더에 오르는 길은 딱 하나 — **한 번 써서 카탈로그로
> 진입하는 것.**

---

## 다음 읽을 것

- 전체 다섯 동사의 흐름 → [HOW-IT-WORKS.md](HOW-IT-WORKS.md)
- 왜 만드는가 → [README.md](../README.md)
- 용어 사전 → [GLOSSARY.md](GLOSSARY.md)
