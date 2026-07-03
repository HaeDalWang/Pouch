# 🗺️ pouch 로드맵

> 살아있는 문서. README의 비전을 "실제로 만들 순서"로 옮긴 것이다.
> 닳고 붙고 떨어지는 걸 전제로 한다 — 이 로드맵도 마찬가지다.

## 확정된 방향 (2026-06-27)

| 결정 | 선택 | 이유 |
| --- | --- | --- |
| 배포 형태 | **독립 CLI + 마법사** (`pouch …`) | "남이 만든 정답 세트"가 아닌 내 손에 맞는 독립 도구. README 비전에 가장 충실 |
| 구현 스택 | **Python** | 마법사 UX, 파일 조작, 메모리 파싱에 강함. macOS 기본 탑재 |
| 첫 MVP | **메모리 레이어** | "쓸수록 진화한다"는 핵심 차별점의 토대. 여기부터 깔아야 나머지가 진화함 |
| 메모리 소유 | **pouch 자체 메모리** (`~/.pouch/memory/`) | 통제력 확보. 단 Claude Code엔 SessionStart hook으로 주입해 "무조건 참고" 달성 |

### 핵심 통찰

- **ECC = 백과사전, pouch = 개인 사서.** ECC가 "다 깔고 골라 쓰는 풀세트"라면,
  pouch는 "물어보고 나한테 맞는 것만 담고, 쓸수록 다시 깎는" 큐레이션 레이어다.
- **자체 소유 + 네이티브 주입.** 메모리는 pouch가 소유하되(`~/.pouch/`),
  에이전트가 무조건 읽도록 Claude Code의 hook/컨텍스트 메커니즘으로 연결한다.

---

## Phase 0 — 기반 (scaffolding)

> 목표: `pouch --help` 가 동작하는 빈 골격.

- [x] `git init` + `.gitignore`
- [x] Python 프로젝트 구조 (`pyproject.toml`, `uv` 기반)
- [x] CLI 엔트리 (Typer) — `pouch`, `pouch --version`, `pouch --help`
- [x] 패키지 레이아웃 (`src/pouch/`)
- [x] 기본 테스트 하네스 (pytest, 3 passed)

**산출물:** 설치 가능한 빈 CLI. 이후 모든 기능이 여기 붙는다. ✅ **완료 (2026-06-27)**

---

## Phase 1 — 메모리 레이어 ★ 첫 MVP

> 목표: 에이전트가 무조건 참고하고, 쓸수록 쌓이는 "나만의 기억".

- [x] 메모리 저장소 설계 — `~/.pouch/memory/` (글로벌) + 프로젝트 `<repo>/.pouch/memory/`
- [x] 메모리 스키마 — frontmatter(`name`, `type`, `description`, `scope`, `weight`, `created`) + 본문
  - `type`: `user` / `feedback` / `project` / `reference` (Claude 네이티브 분류와 호환)
- [x] `MEMORY.md` 인덱스 자동 생성/갱신 (쓰기 후 자동 reindex)
- [x] CLI
  - `pouch memory add` — 새 기억 저장 (비대화형 플래그)
  - `pouch memory list` — 스코프별 목록
  - `pouch memory recall <query>` — 키워드 회상 (시맨틱은 Phase 4)
  - `pouch memory forget <name>` — 틀린 기억 삭제
- [x] 중복 방지 — 같은 이름은 덮어씀(멱등 저장)
- [x] **"무조건 참고" 메커니즘** — `pouch memory context` + `pouch hook install/uninstall/status`
  - SessionStart hook이 인덱스를 컨텍스트에 주입 (본문은 recall로)
  - 자동화 + 투명성: 설명·동의·백업·복구, `--yes` 완전 자동

**산출물:** "내 에이전트가 나를 기억한다"는 첫 경험. 🌊 진화의 토대. ✅ **완료 (2026-06-27, 47 tests)**
**확장:** `boundary` 타입 — 자율성/신뢰 경계 (2026-06-29). context 최상단 강조·본문 주입, allow 좁게·deny 넓게(scope 구조가 누수 차단). direction 필드는 deny 오독 발생 시 도입.

---

## Phase 2 — init 마법사 (🪨 pouch)

> 목표: 환경·역할·취향을 묻고 나만의 한 벌을 담는다.
> **범위(v0):** 감지 + 질문 + `user` 메모리 저장 + hook 연결. **도구 추천 설치는 Phase 3**에서 이 마법사에 얹는다(닭-달걀 회피).

- [x] 환경 감지 — OS, shell, git email, 언어 런타임, Claude 설치 여부 (`init/detect.py`)
- [x] 인터랙티브 질문 — 역할 / 주력 스택(감지 기반) / 작업 스타일 (호칭 제외). 대화형 questionary + 비대화형 플래그 둘 다
- [x] 메모리 연동 — 답변+감지결과를 `user` 메모리로 저장 (`build_memories` 순수 함수)
- [x] 멱등성(idempotent) — 다시 돌려도 안전(기존 메모리 덮어씀)
- [x] hook 연결 제안 — 마지막에 `hook install` 호출 (Phase 1 재사용)
- [ ] (Phase 3) 추천 구성 산출 → 카탈로그에서 도구 설치

**산출물:** `pouch init` — README의 "설치 마법사". ✅ **v0 완료 (2026-06-29, 64 tests)** — 도구 설치는 Phase 3에서 얹음.

---

## Phase 3 — 도구 카탈로그

> 목표: 무엇을 담을 수 있는지의 레지스트리.
> **ownership 3값** — 판별 기준 "추적할 upstream이 있느냐":
> `owned`(upstream 없음, body 소유·mutate) / `vendored`(upstream 추적, body 불변 sync, 개인화는 overlay) / `linked`(외부 실행, recipe+region).

- [x] ① 카탈로그 스키마 + 레지스트리 — `ToolEntry`(ownership 3값) + list/search by tag (`catalog/`)
- [x] ② 임포터 — vendored·owned·plugin 분해·sync 전부 완료. vendored(frontmatter만, body 불변, overlay 분리, 재import 멱등), owned(body 통째 소유, upstream 끊음, force 없인 덮기 거부), plugin(번들→원자: .mcp.json→linked, skills→vendored, region 파싱, plugin 엔트리 안 남김), sync(vendored만 upstream 재방문, overlay 보존, owned·linked 제외). 실제 aws-core(14조각) 검증
- [x] ③ 설치 — ownership이 메커니즘을 가름. owned(catalog body 쓰기) / vendored(upstream 재읽기) / linked(.mcp.json mcpServers 등록, 백업 동반). 순수 함수+IO 분리, 실제 aws-core 검증
- [x] ④ init 연결 — 역할·스택 → 관심 토큰 추출 → 카탈로그 토큰 교집합 매칭(substring 아님, 노이즈 직군어 제외) → ownership별 설치. 실제 aws-core 검증

**AWS toolkit 분해:** Skills 40+ → vendored, rules → vendored, MCP Server → linked, Plugin(aws-core)은 번들이라 importer가 원자 단위로 쪼갬.
**산출물:** `pouch init`이 역할로 도구를 골라 담는 한 벌. boundary는 owned/vendored/linked 셋 다 적용. ✅ **완료 (2026-06-30, 111 tests)**
**Phase 4로 넘긴 것:** 추천 정밀도. v0는 "관심사로 그물을 던진다"까지 — `aws` 토큰이 `aws-sdk-swift-usage`까지 끌어온다. 안 쓰는 변종을 떨구는 건 진화 엔진의 일감("안 쓰는 건 떨어진다"). 지금 좁히면 speculative(YAGNI).

---

## Phase 4 — 진화 엔진 (🌊 raft 직전)

> 목표: 닳고 붙고 떨어진다.
> **핵심 프레임 — 떨어진다 ≠ 삭제된다.** 모든 "제거"는 활성 표면(skills_dir/`.mcp.json`)에서
> 내리는 것이지 카탈로그에서 지우는 게 아니다. 엔트리+overlay는 남는다(vendored가 body 대신
> overlay만 두는 것과 같은 정신). 재부착=`install_entry` 재실행. overlay는 죽을 자리에 애초에 없다.

**정책 5결정 (2026-07-01 락):**

- **① 신호** — 최근성 주축 + 횟수 보조. PostToolUse hook이 `{entry_id, ts}` 적재. boundary 통과는 신호에서 제외(위험≠유용, 가드레일로 직교).
- **② 제거 임계** — 제안만, 자동 제거 안 함. 2단계 후보(never-used+유예 / 썼지만 stale). 임계는 기본값 있는 config.
- **③ 강화 v0** — immunity + 추천 랭크 가점, 런타임 재정렬 없음. 태그 승격(사용 기반 프로필 학습)은 Phase 4.5 defer — usage.jsonl 위 derivation이라 retrofit 빚 없음.
- **④ 가역성** — 프레임으로 해결. drop=표면만, 카탈로그 보존. prod-gate 경계는 도구가 떨어져도 안 죽는다.
- **상태 저장** — 사이드카 분리. `~/.pouch/usage.jsonl`(append-only) + 별도 상태 파일. 카탈로그는 깨끗한 레지스트리로.

**구현 항목:**

- [x] 사용 로깅 hook — PostToolUse(`Skill|mcp__.*` 매처) → `usage.jsonl`. **선결 확정: `tool_input.skill`이 Skill 이름(라이브 검증)**
- [x] usage 집계 — entry_id별 last_used·count 파생 (사이드카 읽기)
- [x] drop 후보 산출 — 2단계 분류(never-used / stale), 순수 함수. immunity는 stale 임계에서 자동으로 나옴
- [x] `pouch evolve` — 후보 제안 + 동의 → 표면에서 uninstall(카탈로그 보존), 재부착 지원

**산출물:** 시간이 지날수록 더 정확히 맞아가는 주머니. ✅ **v0 완료 (2026-07-01, 163 tests → java 감지 수정 후 165)** — 6조각(사이드카 로그·추적 매핑·집계·후보·uninstall·evolve CLI) + 배선 2(설치→state 기록, hook에 사용 로깅 연결). 실물 CLI로 install→log→evolve 전 경로 검증.
**Phase 4.5로 넘긴 것:** 태그 승격(자주 쓴 도구 태그를 추천 키로 승격 = 실제 사용에서 진짜 프로필 학습). "쓸수록 손에 맞게 닳아간다"의 가장 깊은 형태지만, 같은 usage.jsonl 위 derivation이라 로그가 깊어진 뒤 안전하게 얹는다.

---

## Phase 4.6 — 체감 루프 (주머니에 생명 넣기)

> 목표: 루프는 완성됐는데 체감이 없다. 라이브 실측(2026-07-02, `~/.pouch/` 검시)으로 끊긴 고리를 짚었다:
> **① 공급 단절** — 카탈로그를 채울 CLI 입구가 없어 주머니가 빈 채 전 루프가 공회전
> (importer는 Phase 3에 있는데 배선이 없음).
> **② 가시성 부재** — usage가 쌓여도 보여주는 표면이 없다.
> **③ 진화가 반쪽** — "닳고 붙고 떨어진다"에서 떨어진다(drop)만 있고 붙는다(attach)가 없다.
> 그런데 라이브 로그가 이미 attach 신호를 갖고 있다(자주 쓰는데 카탈로그 밖인 도구).
> **④ 축적 단절** — 기억이 init 이후 수동으로만 쌓여 매 세션 같은 3줄 주입.

**구현 항목 (순서 = 의존 순서):**

- [x] ① `pouch catalog` CLI — import(plugin/skill/.mcp.json 자동 판별)·list·install·sync 배선.
  install은 drop 후 **재부착의 공식 입구**이기도 하다(Phase 4 가역성의 마지막 배선)
- [x] ② `pouch` 상태 화면 승격 — 민낯 `pouch` 한 화면: 주머니에 뭐가 있고 / 최근 뭘 썼고 /
  뭐가 오르내릴 후보인지. 백로그 doctor의 축소 승격(가장 싸고 즉시 체감)
- [x] ③ attach 제안 — evolve에 "당겨올 것" 섹션. 카탈로그에 있는데 표면에 없고+최근 쓴 것 → 재부착 제안 /
  카탈로그 밖인데 최근 자주 쓰는 것 → 편입 안내(제안만, 자동 없음 — drop과 같은 원칙).
  **신호는 최근 창(7일)만** — 창 < stale 임계(30일)라 drop↔attach 진동이 구조적으로 불가능
- [ ] ④ 기억 저마찰 축적 — 세션에서 배운 게 memory로 흘러드는 경로.
  **"뭘 자동으로 기억하나"는 boundary급 결정이라 정책 설계 먼저** — ①~③과 달리 코드부터 가지 않는다

**①~③ 완료 (2026-07-02, 194 tests).** ④는 정책 설계 세션이 선행돼야 열린다.

**후속(A안, 2026-07-03): alias + 표면 통제권.** end user 실측에서 같은 도구가 이름 둘을 가짐이 드러남 —
카탈로그는 `.mcp.json`의 원래 이름(exa), usage 추적은 런타임 네임스페이스(`plugin_<플러그인>_exa`).

- **alias 슬롯** — plugin import 시 런타임 별칭을 엔트리에 박고(이름은 `.claude-plugin/plugin.json`에서,
  디렉토리명 추측 금지), 집계는 alias를 정식 id로 접어(canonicalize) 비교한다.
- **surface 축** — ownership(몸의 소유)과 직교하는 "표면 통제권". 플러그인이 표면을 관리하는 엔트리는
  evolve의 재부착/드롭 대상에서 빠지고 **관측만**(`플러그인이 관리 중`), `catalog install`도 거부(중복 등록 방지).

**부채 상환 (동승):**

- [x] environment vs stack 소스 오브 트루스 — **stack(사용자 의도)이 추천의 소스, environment(감지 사실)는
  참고 컨텍스트.** 코드는 이미 이렇게 동작(recommend는 role·stacks만 읽음) — 규칙을 명문화해 고정 (2026-07-02).

---

## Phase 5 — raft (개인 → 팀)

> 목표: 한 사람의 좋은 돌이 무리로 번진다.

- [ ] pouch 구성 export / import
- [ ] 팀 공유 레지스트리
- [ ] 개인 메모리와 공용 구성의 경계 정의

**산출물:** 🦦 a raft of otters.

---

## 백로그 (후순위)

> Phase에 묶이지 않은, 나중에 할 가치가 있는 것들.

- [ ] `pouch doctor` / 상태 대시보드 — 무엇이 연결됐고 어떤 효과인지 사람 말로 풍부하게 설명하는 화면. 비기술직군 친화 UX의 핵심. **축소판은 Phase 4.6 ②로 승격됨** — 여기 남는 건 "풍부한 설명" 완전판.

---

## 설계 원칙 (전 Phase 공통)

- **자동화 + 투명성.** 설정 변경(`~/.claude/settings.json` 등)은 pouch가 대신 해준다.
  단 사람 말 설명 + 동의 + 백업 + `uninstall` 복구를 동반한다. `--yes`로 완전 자동도 지원.
  비기술직군도 json을 열지 않고 쓸 수 있어야 한다.

---

## 진행 원칙

- **한 번에 한 Phase.** 끝나면 README 상태 섹션을 갱신한다.
- **메모리 먼저, 기능 나중.** 모든 Phase는 메모리에 흔적을 남긴다.
- **규칙은 코드로.** 문서 약속보다 잘못 쓰기 어려운 구조를 선호한다.
