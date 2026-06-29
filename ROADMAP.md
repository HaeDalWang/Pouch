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

- [ ] skill/command/agent/rule/hook 메타데이터 스키마
- [ ] 카탈로그 레지스트리 — 도구별 "누구에게 맞는지" 태그
- [ ] 마법사가 카탈로그에서 선택하도록 연결
- [ ] (선택) ECC 등 외부 소스 import 어댑터

**산출물:** 마법사가 고를 수 있는 도구 풀.

---

## Phase 4 — 진화 엔진 (🌊 raft 직전)

> 목표: 닳고 붙고 떨어진다.

- [ ] 사용 패턴 추적 — hook으로 도구 사용 로깅
- [ ] 강화/제거 로직 — 자주 쓰는 건 강화, 안 쓰는 건 정리 제안
- [ ] 메모리 `weight` 기반 우선순위
- [ ] 정기 회고 — `pouch evolve` 가 구성 변화를 제안

**산출물:** 시간이 지날수록 더 정확히 맞아가는 주머니.

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

- [ ] `pouch doctor` / 상태 대시보드 — 무엇이 연결됐고 어떤 효과인지 사람 말로 풍부하게 설명하는 화면. 비기술직군 친화 UX의 핵심이지만 우선순위는 낮음.

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
