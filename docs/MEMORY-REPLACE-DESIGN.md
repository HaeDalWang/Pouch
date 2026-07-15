# 🦦 A안 설계 — pouch가 Claude 네이티브 메모리를 대체한다

> **이 문서는 [MEMORY-POSITIONING.md](MEMORY-POSITIONING.md)의 열린 결정 #1(A vs B)을
> A(대체)로 닫고, "대체"가 구체적으로 무엇을 뜻하는지 설계한다.** 아직 코드가 아니라
> 같이 개발하는 사람과 합의하기 위한 설계 문서다.
>
> 읽는 법은 [HOW-IT-WORKS.md](HOW-IT-WORKS.md)와 같다 — 막히는 단어는 표시해뒀다가
> [GLOSSARY.md](GLOSSARY.md)로 넘긴다.

---

## 왜 A가 가능한가 (전제 사실)

Claude Code 네이티브 메모리는 **완전히 끌 수 있다**:

| 스위치 | 효과 |
|---|---|
| `autoMemoryEnabled: false` (settings.json, 모든 스코프) | 네이티브 메모리 **읽기·쓰기 전부 중단** |
| env `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` | 같은 효과 |
| `autoMemoryDirectory: <경로>` | 읽기·쓰기 위치만 이동(끄는 건 아님) |

- 자동로드는 켜져 있을 때 **MEMORY.md 첫 200줄(또는 25KB)** 을 세션 시작에 주입한다.
  개별 파일은 에이전트가 명시적으로 읽을 때만 로드된다.
- ⚠️ **read-only 모드는 없다.** 켜면 읽기+쓰기 둘 다, 끄면 둘 다. 반쪽(읽기만/쓰기만)은
  불가능하다 — 이 비대칭이 아래 §3(A의 대가)의 뿌리다.

> 이 키들은 claude-code-guide가 공식 문서(code.claude.com `memory.md`·`settings.md`)에서
> 확인했다. **배선 구현 시 정확한 키 이름을 한 번 더 확인**한다 — 키를 틀리면 조용한
> 무동작(silent no-op)이라 "껐다고 믿었는데 안 꺼짐"이 가장 위험한 실패다.

---

## "대체"가 뜻하는 네 갈래

네이티브가 하던 일을 하나씩 pouch로 옮기거나(이관), 없애며 청소한다.

| 네이티브가 하던 일 | A에서 누가 | 방법 | 상태 |
|---|---|---|---|
| 세션 시작 주입 | pouch SessionStart 훅 | `additionalContext` | **이미 있음** |
| 기억 저장 | pouch `~/.pouch/memory/` | 플랫 MD | **이미 있음** |
| 기존 기억 보존 | `pouch memory adopt` 이관 | §2 | 신규 |
| 에이전트의 기억 쓰기 | ??? | §3 | **A의 진짜 대가** |

핵심: 주입·저장은 pouch가 이미 한다. A의 새 작업은 **②네이티브 중립화 + ③기존 이관 +
④사라진 write 경로 메우기** 셋이다.

---

## §1. 네이티브 중립화 (한 번, 가역)

- pouch가 `~/.claude/settings.json`에 `autoMemoryEnabled: false`를 기록한다.
- 기존 `hook install`과 **같은 안전장치**: 쓰기 전 `.bak` 백업, 멱등, 기존 설정 보존.
- 되돌리기: 그 키를 지우면 네이티브 부활 → **완전 가역**.
- 네이티브 자동로드가 꺼지므로 pouch 훅 주입과 **중복 주입이 구조적으로 없다**
  (docs가 둘의 병존 시 dedup·순서를 보장하지 않아, 병존은 애초에 피한다).

---

## §2. 기존 기억 이관 — `pouch memory adopt`

`~/.claude/projects/*/memory/*.md`를 훑어 pouch로 들인다.

### 포맷 매핑 (거의 호환)

| 네이티브 | pouch | 처리 |
|---|---|---|
| `metadata.type` (user/feedback/project/reference) | `type` | 직접 |
| `name` · `description` | `name` · `description` | 직접 |
| 본문(`**Why:** / **How to apply:**`) | `body` | 그대로 |
| `metadata.originSessionId` | (provenance 필드?) | 보존 여부 미정 → 하위 결정 |
| `[[wikilink]]` 상호참조 | — | pouch에 링크 개념 없음. v0는 본문 텍스트로 보존 |
| 파일 mtime | `created` | 네이티브 frontmatter엔 날짜 없음 → mtime 사용 |
| (없음) | `scope` | ⭐ 타입으로 결정(아래) |

### 스코프 규칙 — 타입이 자리를 정한다

| 네이티브 타입 | pouch scope | 이유 |
|---|---|---|
| `user` · `feedback` | **global** | 너·일하는 법에 대한 것 → 어디서나 적용 |
| `project` · `reference` | **project** | 그 작업에 매인 것 → 해당 repo `.pouch/memory/` |

> 네이티브는 프로젝트 디렉토리 슬러그(`-Users-joung-develop-investment-dashboard`)로
> 자리를 갈랐다. 이걸 실제 경로(`/Users/joung/develop/investment-dashboard`)로 역매핑해
> 그 repo에 project 기억을 쓴다. repo가 없어졌으면? → 하위 결정.

### 라이프사이클 트리아지 — A의 청소 가치가 여기서 나온다

네이티브는 생명주기가 없어 **"안정 핵심만 항상 주입"이라는 원칙을 어기고** 세션로그
53개를 전부 상시 주입하고 있었다. adopt는 그걸 **복원**한다:

| 들어오는 것 | pouch 계층 | 결과 |
|---|---|---|
| user·feedback·reference | **INDEXED** | 주입됨(안정 핵심만) |
| project — **날짜(YYMMDD) 박힌 세션로그** | **ARCHIVED** | 주입 안 됨 · recall만 · 리뷰 잔소리 없음 |
| project — 날짜 없는 것 | **PENDING** | 주입 안 됨 · recall 가능 · 리뷰 대기 |

→ 53파일 사례라면 **주입되는 건 ~10개 안팎으로 줄고** 나머지는 recall 대기. "담을 때"가
아니라 "리뷰 때" 마찰을 무는 pouch pending 철학과 같은 정신이다.

멱등: 다시 돌려도 중복 안 만든다(같은 name = 갱신/skip).

---

## §3. ⚠️ A의 대가 — 네이티브 write 경로가 사라진다

네이티브 메모리의 **숨은 가치는 자동로드가 아니라, 에이전트가 작업 중 스스로 기억을
쓰는 것**(저마찰 축적)이다. `autoMemoryEnabled: false`는 read-only 분리가 불가능하므로
이 write까지 죽인다.

**따라서 A는 "세션→기억 자동 축적"([MEMORY-POSITIONING.md](MEMORY-POSITIONING.md) 열린
결정 #4, 로드맵 미완)을 선택이 아니라 필수로 앞당긴다.** 대체하는 순간 새 기억이 흘러들
경로가 없으면 주머니가 마른다.

| 시점 | write 경로 | 비고 |
|---|---|---|
| 단기 | 주입에 "기억하려면 `pouch memory add …` 실행" 지침 한 줄 | **✅ 구현됨**(`render_how_to_remember`, `memory/context.py`). 고정 구역(경계·체크포인트 아래) 영어 지침이라 Codex·Kiro도 동일하게 동작 |
| 장기 | PostToolUse/Stop 훅으로 기억 후보 포착 → PENDING | 별도 설계(deferred). 진짜 저마찰 |

이 대가는 순비용이자, 동시에 **pouch를 저장소 경쟁에서 진짜 차별(주입·경계·수명)로 미는
지점**이다 — 셋 다 못 푼 축적 문제를 A가 정면으로 떠안게 만든다.

---

## 명령 형태 스케치

```
pouch memory adopt [--dry-run] [--no-disable-native]
```

- `--dry-run` : 무엇이 어디로(scope)·어떤 계층으로(INDEXED/ARCHIVED) 갈지 **미리보기만**.
  아무것도 안 바꾼다 — `plan_*`/`apply_*` 분리 정신.
- 기본 동작은 **네이티브도 끈다**(대체니까). 이관만 하고 싶으면 `--no-disable-native`.
- `pouch init`/`hook install` 흐름에 자연스럽게 얹을 수 있다("네이티브 메모리 쓰던데,
  pouch로 넘길까요?").

---

## 안전·가역성

- `settings.json`은 `.bak` 백업(hook 패턴 재사용).
- 이관은 **복사**다 — 원본 네이티브 파일을 지우지 않는다. 되돌아갈 자리를 남긴다.
- adopt 되돌리기 = `autoMemoryEnabled` 복구 + pouch 쪽 이관본 정리.

---

## 남은 하위 결정

1. **provenance 보존** — `originSessionId`를 새 필드로 남길까, 버릴까.
2. ~~**세션로그 자동 판별**~~ — **닫힘.** 이름에 유효한 YYMMDD가 박힌 project는 ARCHIVED,
   없으면 PENDING(`_looks_dated`). 오분류돼도 recall로 복구 가능. 실측 리뷰 큐 45→30.
3. **repo 역매핑 실패 처리** — project 기억의 원래 repo가 사라졌으면? (global 강등 +
   메모 vs skip vs 별도 보관)
4. ~~**write 지침 문구·위치**~~ — **닫힘.** 고정 구역(경계·체크포인트 아래)에 영어
   지침으로 심었다(`render_how_to_remember`). 채우는 값은 사용자 언어로 쓰라고 명시.
5. **write 경로 장기안 착수 시점** — 단기 지침으로 버티다 언제 PostToolUse 훅 설계로 갈지.

> 이 문서도 [MEMORY-POSITIONING.md](MEMORY-POSITIONING.md)처럼 결정을 *열어두는* 문서다.
> 위 다섯을 닫을 때마다 근거와 함께 여기 남긴다.
