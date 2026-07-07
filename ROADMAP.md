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
- [x] ④ 기억 위생 + 저마찰 축적 — 들어오는 문과 나가는 문(한 세트). 정책 락(2026-07-05) →
  구현 완료(같은 날). 핵심 프레임: 저마찰 유입이 나가는 작업량을 결정 → 스테이징 계층이 긴장을 푼다.

**①~③ 완료 (2026-07-02, 194 tests).**

**④ 정책 락 (2026-07-05) — 기억은 나이가 아니라 진실로 닳는다:**

- **긴장·해법** — 저마찰 IN + 위생 OUT은 같은 곡선의 양 끝. 저마찰 포착을 *pending 계층*에
  격리하면 마찰 없는 유입이 주입 인덱스를 안 더럽힌다. 마찰이 "담을 때"→"리뷰 때 일괄"로 이동.
- **3계층 (drop≠delete의 기억판)** — Indexed(MEMORY.md 주입) / Archived(파일 있고 인덱스에서 빠짐,
  recall로만 소환=도구 drop) / Deleted(별도 시끄러운 파괴). 위생은 1→2 강등만 제안. `weight` 높으면 면역.
- **나가는 문은 타입별 신호** (나이는 project에만 통함): project→만료 / reference→생존성(죽은 URL·경로,
  rehome의 기억판) / boundary→**제외**(안 걸린 deny는 제 일 중) / feedback·user→모순(v0 defer).
- **결정 1·2** — 유입 축=타입. project·reference 저마찰(pending 자동 포착), feedback·boundary·user
  확인 필수. **특히 feedback**: 오독한 일회성 지적이 매 세션 standing rule이 되는 위험(boundary deny 오독과 동형).
- **결정 3** — v0 = project 만료 + reference 생존성 + boundary 제외. 모순 감지 defer. ⚠️ **인지된 갭:
  feedback·user는 v0에서 나갈 문이 없다**(모순만이 신호인데 defer됨) — 명시적 삭제로만 제거. 모순 감지가 메움.
- **결정 4** — `last_recalled` **슬롯은 지금 박음**(구조, 나중 마이그레이션 비쌈). v0 로직: recall 시
  갱신 + reference 생존성 체크가 이 이벤트에 올라탐. defer: recall 빈도를 면역 신호로. 근거: 생존성이
  recall 이벤트를 요구 → 슬롯이 이미 필요. "슬롯은 지금(구조), 로직은 나중(최적화)" — weight와 같은 정신.
- **표면** — `pouch evolve`가 두 문을 한 화면에(🆕 pending 확인 IN + 🧹 강등 후보 OUT), 도구 drop+attach와 나란히.

**④ 구현 완료 (2026-07-05, 261 tests):** `MemoryState`(PENDING/INDEXED/ARCHIVED) + `last_recalled` 슬롯
→ `hygiene_candidates`(타입별 신호, 순수) → recall 배선(last_recalled 갱신 + reference 생존성 인라인 경고,
자동 강등 없음) → `pending.py`(타입별 마찰, CLI `add --pending`/`promote`) → `pouch evolve` 통합
(🆕 확인할 기억 / 🧹 정리할 기억, 둘 다 일괄 confirm 후 적용). `MemoryStore.promote/demote`가 상태 전이+
재인덱싱을 한 곳에서 보장. reference 생존성은 로컬 경로만 실제 확인(URL은 네트워크 없이 "판단 불가=생존" —
v0 스코프, 필요해지면 백로그로).

**후속(A안, 2026-07-03): alias + 표면 통제권.** end user 실측에서 같은 도구가 이름 둘을 가짐이 드러남 —
카탈로그는 `.mcp.json`의 원래 이름(exa), usage 추적은 런타임 네임스페이스(`plugin_<플러그인>_exa`).

- **alias 슬롯** — plugin import 시 런타임 별칭을 엔트리에 박고(이름은 `.claude-plugin/plugin.json`에서,
  디렉토리명 추측 금지), 집계는 alias를 정식 id로 접어(canonicalize) 비교한다.
- **surface 축** — ownership(몸의 소유)과 직교하는 "표면 통제권". 플러그인이 표면을 관리하는 엔트리는
  evolve의 재부착/드롭 대상에서 빠지고 **관측만**(`플러그인이 관리 중`), `catalog install`도 거부(중복 등록 방지).

**부채 상환 (동승):**

- [x] environment vs stack 소스 오브 트루스 — **stack(사용자 의도)이 추천의 소스, environment(감지 사실)는
  참고 컨텍스트.** 코드는 이미 이렇게 동작(recommend는 role·stacks만 읽음) — 규칙을 명문화해 고정 (2026-07-02).

**후속(2026-07-05, BACKLOG 필수 1 승격): upstream 증발 대비 — "body는 자동 이사, boundary는 flag만".**
vendored upstream이 버전 고정 경로(`<mkt>/<plugin>/<version>/…`)라 플러그인 업데이트 한 번에 194개가 동시에
죽는 시한폭탄이었다. 층을 갈라 해결:

- **body 자동 이사(rehome)** — 죽은 경로를 형제 버전 중 최신으로 재해석(rc < 정식), sync가 자동 re-link하고
  "1.0.0 → 1.1.0 이사"로 보고. sync의 계약 자체가 "upstream 따라 fresh 유지"라 자동이 맞다.
- **하이재킹 가드** — 재해석 결과가 같은 스킬인지 frontmatter name으로 검증. 스킬만 삭제된 경우 형제 스킬로
  body가 조용히 바뀌는 최악의 오염을 유실 보고로 대체.
- **boundary는 flag만** — 이사한 항목에 boundary가 있으면 "새 버전에서 유효성 확인 요망" 한 줄(막지 않음).
- **완전 증발** — 엔트리·overlay 보존 + 유실 보고 + 재연결 안내. sync_all은 항목별 격리(인질 패턴 해제,
  import 때와 같은 정신). 222 tests.

**후속(2026-07-07, BACKLOG 필수 1 완료): 백업/복원 v0 — 잃었을 때 되찾기.**
`~/.pouch`가 단일 장애점인데 백업 명령이 없던 구멍을 메웠다. 정책 락(같은 날):

- **글로벌만** — `~/.pouch`만 클라우드행. 프로젝트별 `.pouch/`는 민감정보라 제외(각 repo git 위임).
  데이터 유출을 v0에서 구조로 회피.
- **코어 + 어댑터** — "무엇을 싸서 어떻게 되푸나"(코어)를 로컬 파일로 먼저 완성. 두 목적지
  (S3=기술자 / 구글드라이브=비기술자, 실사용자 조사 근거)는 인증·API만 달라 같은 코어 위에 얹는다.
  S3·GDrive 어댑터는 다음.
- **restore 포함 + 복원의 되돌리기** — export만은 반쪽. 복원 전 현재 상태를 자동 스냅샷
  (settings.json `.bak`과 같은 정신). replace 시맨틱(백업 시점으로 되돌리기).
- **버그 잡음** — 백업/스냅샷이 같은 초에 실행되면 파일명이 충돌해 스냅샷이 원본 백업을
  덮어쓰는 오염을 발견, 접두사 분리(`pouch-backup-`/`pre-restore-`)로 구조 차단. 실물 왕복 검증.
- **raft 연결** — 백업 코어 = Phase 5 export/import와 같은 뿌리(백업=나에게 되돌리기,
  공유=남에게 주기). 275 tests.

**후속(2026-07-07, BACKLOG 필수 2 완료): usage.jsonl 위생 — 접기(compaction).**
append-only 무한 성장 + 매번 전체 읽기 문제를 잘라내기가 아니라 접기로 풀었다.
배승도 근거: "pouch는 나에게 맞게 진화 — 인간은 엄청 옛날 것도 흔적으로 남는다." 잘라내기는
과거 소실, 접기는 누적 count 보존(습관 신호).

- **무엇을** — 경계(180일) 밖 이벤트를 entry_id별 {count, last_used} 요약으로 접기. 개별 시각은
  흐려지되 누적은 영구 보존. 진화 최대 창(30일) 훨씬 밖이라 판단 무손실.
- **언제** — evolve 실행 시 자동(무손실이라 "제안만" 빡빡히 적용 안 함) + 접었으면 한 줄 알림.
- **멱등 안전** — 요약에 `compacted_through` 마커. 집계는 이 시각 이하(접힌 잔재)를 무시하고
  summary+최근상세를 합산 → jsonl 재작성이 실패해도 이중 계산 없음. plan_evolution이 접힌
  과거를 반영해 "썼던 도구"를 never-used로 오분류하지 않는다.
- **append-only 예외** — 정상 로깅(hook)은 계속 덧붙이기만, 접기만 예외적 재작성(원자적). 292 tests.

**오너십 문서(2026-07-06~07):** 압축 은어로 '대충 읽고 수락'하던 문제를 `docs/HOW-IT-WORKS.md`
(은어 없는 흐름) + `docs/GLOSSARY.md`(오너가 막힌 단어에서 자라는 사전)로 풀기 시작.

---

## Phase 5 — raft (개인 → 팀)

> 목표: 한 사람의 좋은 돌이 무리로 번진다.

- [ ] pouch 구성 export / import
- [ ] 팀 공유 레지스트리
- [ ] 개인 메모리와 공용 구성의 경계 정의
- [ ] 세트 공유 순환 — 완성된 세트 공유 → 스타(인정) → 인정받은 세트의 기본 온보딩 편입
  (2026-07-07 예약, BACKLOG 필수 4 "시작 세트"의 공유편. 세트 자체는 필수 4에서 먼저)

**산출물:** 🦦 a raft of otters.

---

## 백로그

> Phase에 묶이지 않은 후보 풀은 **[BACKLOG.md](BACKLOG.md)**로 분리했다 (2026-07-05).
> 채택 렌즈("pouch의 약속이 거짓말이 되는가"), 필수/있으면 좋겠다 구분,
> 결정 기록(D1 boundary 비강제, D2 Claude Code 우선), 예고된 문제(P1 boundary 출처)가 거기 있다.
> 채택되면 이 문서의 Phase로 승격된다.

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
