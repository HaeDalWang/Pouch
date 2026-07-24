# 이 저장소에서 일하는 법

> pouch의 오너는 배승도다. 이 프로젝트의 첫 번째 규칙:
> **오너가 이해하지 못한 결정은 결정이 아니다.**
> 이 파일은 에이전트와 사람(동료 포함) 모두에게 적용된다.

## 작업 고리 — 모든 변경이 이 네 단계를 돈다

1. **해설** — 결정·변경을 중학교 3학년도 알아듣게 쉬운 말로 설명한다.
   은어나 개발 용어를 꼭 써야 하면 [docs/GLOSSARY.md](docs/GLOSSARY.md)에
   (쉬운 말 / 왜 생겼나 / 헷갈리기 쉬운 점 / 위치) 네 칸을 채워 등록하고 쓴다.
2. **락** — 오너가 **자기 말로 되풀어 말해야** 결정이 닫힌다. 되풀지 못하면
   그건 설명이 부족한 것이니 락을 보류하고 다시 푼다. 닫힐 때는 오너의
   되풀이 문장을 **그대로** 문서에 근거로 남긴다.
3. **개발** — 락된 결정만 기반으로 구현한다. 코드가 먼저 나갔더라도 결정이
   굳은 게 아니다 — 문서에 "구현됨 (오너 확인 전)"으로 표시하고 확인을 기다린다.
4. **기록** — 동작이 바뀌면 [docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md)에
   반영한다. 오너는 언제 돌아와도 그 문서 하나로 길을 찾을 수 있어야 한다.

### 기록은 약속이 아니라 관문이다 (2026-07-21)

④가 약속이라서 바쁘면 조용히 건너뛰어졌고, 건너뛴 사실이 아무 데도 안 남았다 —
사흘치 작업과 일주일 묵은 기능이 로드맵·백로그 어디에도 없는 게 뒤늦게 드러났다.
그래서 커밋 순간에 걸리게 했다(`.githooks/commit-msg`).

```sh
git config core.hooksPath .githooks   # 클론한 뒤 한 번
```

`feat:`·`fix:` 커밋이 `src/pouch/`를 건드리는데 HOW-IT-WORKS·ROADMAP·BACKLOG 중
아무것도 안 바뀌었으면 막는다. 빠져나갈 문은 둘 — 커밋 메시지에 `[no-docs]`
(영향 없음) 또는 `[docs-later]`(미룸). 미룬 건 부채로 남아 되찾을 수 있다:

```sh
git log --grep='\[docs-later\]' --oneline
```

## PR을 낼 때

- **한 PR에 새 설계 갈래는 하나만.** 문서 여러 개·결정 여러 개를 한꺼번에
  쏟지 않는다. 산출 속도가 오너의 이해 속도를 앞지르면 오너가 길을 잃는다
  (2026-07, 문서 7개 713줄이 한 PR로 들어와 실제로 일어난 사고).
- 결정을 "닫힘/결정됨"으로 적지 않는다. 오너 확인 전에는 전부
  **"제안 · 오너 확인 대기"**다.
- PR 설명도 쉬운 말로 쓴다 — ① 무엇을 바꾸나 ② 왜 바꾸나 ③ 오너가 확인할
  결정이 무엇인가, 세 가지를 평문으로.

## 길잡이 문서

- [docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md) — pouch가 어떻게 도는가 (오너용 본문서)
- [docs/GLOSSARY.md](docs/GLOSSARY.md) — 용어 사전. 오너가 실제로 걸린 단어에서 자란다
- [README.md](README.md) / [ROADMAP.md](ROADMAP.md) / [BACKLOG.md](BACKLOG.md)
  — 왜 만드나 / 어떤 순서로 / 무엇을 안 하기로 했나

## 코드 지도로 확인하기 (code-review-graph)

오너는 코드를 직접 읽지 않는다. 그러니 에이전트의 "확인했다"는 말은
**오너가 눈으로 볼 수 있는 증거**로 바뀌어야 한다. 그 증거를 싸게 뽑는 도구가
code-review-graph — 저장소를 미리 훑어 "누가 무엇을 부르는지"를 지도로 만들어 둔다.

- **무언가 지우거나 크게 바꾸기 전에**, 파일을 잔뜩 읽지 말고 지도에 먼저 묻는다.
  `code-review-graph query callers_of <이름>` (누가 부르나) ·
  `code-review-graph impact --files <경로>` (바꾸면 어디가 깨지나) ·
  `code-review-graph query tests_for <이름>` (어떤 테스트가 지키나).
  이름이 여러 곳에 겹치면 도구가 "정확한 이름으로 다시"라고 안내한다 — 그대로 따른다.
  그 결과 목록을 오너에게 그대로 내민다 — "안전하다"가 아니라 "부르는 곳: (목록)".
- **지도는 "지도"지 "심판"이 아니다.** 연결 관계(callers·impact·tests_for·architecture)는
  믿어도 된다. 하지만 `dead-code`·큰 함수 "나쁨" 판정은 **오탐이 흔하다**
  (이 저장소는 Typer 데코레이터로 함수를 간접 등록해서, 안 쓰는 것처럼 잘못 잡힌다).
  이런 "판정"은 에이전트가 **한 번 직접 검증한 뒤** 오너에게 말한다.
- 지도는 커밋될 때 `.githooks/post-commit`이 조용히 자동 갱신한다. 세션 중
  방금 고친 걸 물을 땐 `code-review-graph update -q`를 먼저 돌려 지도를 맞춘다.
- 지도 db(`.code-review-graph/`)는 `.gitignore`로 빠져 있어 커밋에 안 섞인다.

## pouch 철학 네 줄 — 코드에 손대기 전에

- **제안만 한다.** 동의 없이 아무것도 안 움직인다. 자동으로 움직이는 건 기록뿐.
- **떨어진다 ≠ 삭제된다.** 내리는 건 표면(연장통)에서 빼는 것이지 지우는 게 아니다.
- **실사용이 증거다.** "이 역할이면 이거 쓰겠지" 같은 지어낸 큐레이션은 담지 않는다.
- **설정은 대신 바꾸되 투명하게.** 설명 → 동의 → 백업이 항상 따라온다.

<!-- code-review-graph MCP tools -->
## MCP Tools: code-review-graph

**IMPORTANT: This project has a knowledge graph. ALWAYS use the
code-review-graph MCP tools BEFORE using Grep/Glob/Read to explore
the codebase.** The graph is faster, cheaper (fewer tokens), and gives
you structural context (callers, dependents, test coverage) that file
scanning cannot.

### When to use graph tools FIRST

- **Exploring code**: `semantic_search_nodes_tool` or `query_graph_tool` instead of Grep
- **Understanding impact**: `get_impact_radius_tool` instead of manually tracing imports
- **Code review**: `detect_changes_tool` + `get_review_context_tool` instead of reading entire files
- **Finding relationships**: `query_graph_tool` with callers_of/callees_of/imports_of/tests_for
- **Architecture questions**: `get_architecture_overview_tool` + `list_communities_tool`

Fall back to Grep/Glob/Read **only** when the graph doesn't cover what you need.

### Key Tools

| Tool | Use when |
| ------ | ---------- |
| `detect_changes_tool` | Reviewing code changes — gives risk-scored analysis |
| `get_review_context_tool` | Need source snippets for review — token-efficient |
| `get_impact_radius_tool` | Understanding blast radius of a change |
| `get_affected_flows_tool` | Finding which execution paths are impacted |
| `query_graph_tool` | Tracing callers, callees, imports, tests, dependencies |
| `semantic_search_nodes_tool` | Finding functions/classes by name or keyword |
| `get_architecture_overview_tool` | Understanding high-level codebase structure |
| `refactor_tool` | Planning renames, finding dead code |

### Workflow

1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes_tool` for code review.
3. Use `get_affected_flows_tool` to understand impact.
4. Use `query_graph_tool` pattern="tests_for" to check coverage.
