# 🗺️ pouch 로드맵

> 살아있는 문서. README의 비전을 "실제로 만들 순서"로 옮긴 것이다.
> 닳고 붙고 떨어지는 걸 전제로 한다 — 이 로드맵도 마찬가지다.

## 확정된 방향 (2026-06-27)

| 결정 | 선택 | 이유 |
|------|------|------|
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

- [ ] 메모리 저장소 설계 — `~/.pouch/memory/` (글로벌) + 프로젝트 스코프
- [ ] 메모리 스키마 — frontmatter(`name`, `type`, `description`, `scope`, `weight`, `created`) + 본문
  - `type`: `user` / `feedback` / `project` / `reference` (Claude 네이티브 분류와 호환)
- [ ] `MEMORY.md` 인덱스 자동 생성/갱신 (한 줄 한 메모리)
- [ ] CLI
  - `pouch memory add` — 새 기억 저장
  - `pouch memory list` — 인덱스 보기
  - `pouch memory recall <query>` — 관련 기억 회상
  - `pouch memory forget <name>` — 틀린 기억 삭제
- [ ] **"무조건 참고" 메커니즘** — SessionStart hook이 pouch 메모리를 컨텍스트에 주입
- [ ] 중복 방지 — 같은 사실은 갱신, 새로 만들지 않음

**산출물:** "내 에이전트가 나를 기억한다"는 첫 경험. 🌊 진화의 토대.

---

## Phase 2 — init 마법사 (🪨 pouch)

> 목표: 환경·역할·취향을 묻고 나만의 한 벌을 담는다.

- [ ] 환경 감지 — OS, shell, 설치된 도구, git, 언어 스택
- [ ] 인터랙티브 질문 — 역할/취향/작업 패턴
- [ ] 추천 구성 산출 → `~/.claude` 또는 pouch 설정에 설치
- [ ] 멱등성(idempotent) + 롤백 — 다시 돌려도 안전
- [ ] 메모리 연동 — 마법사 답변을 `user` 타입 메모리로 저장

**산출물:** `pouch init` — README의 "설치 마법사".

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

## 진행 원칙

- **한 번에 한 Phase.** 끝나면 README 상태 섹션을 갱신한다.
- **메모리 먼저, 기능 나중.** 모든 Phase는 메모리에 흔적을 남긴다.
- **규칙은 코드로.** 문서 약속보다 잘못 쓰기 어려운 구조를 선호한다.
