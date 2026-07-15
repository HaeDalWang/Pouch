# 🦦 프로젝트별 주머니 — 카탈로그에 프로젝트 스코프

> **이 문서는 BACKLOG "프로젝트별 주머니"를 연다.** 레인 2a가 놓은 프로젝트 신호
> (로컬 사용 로그) 위에서, 카탈로그를 **전역 전용 → global/project 2계층**으로 확장한다.

---

## 왜

멀티 클라이언트 작업에서 도구가 섞이면 안 된다 — 클라이언트 A의 보안 도구 vs 내부 툴
개발. **memory는 이미 global/project 2계층인데 catalog는 전역뿐이다.** 이 비대칭을 메운다.

## 모델은 이미 준비돼 있다

`CatalogStore`가 `catalog_dir`로 매개변수화돼 있어(소스 스테이징이 이미 그 방식) —
프로젝트 스토어 = `CatalogStore(catalog_dir=<repo>/.pouch/catalog/)`. **retrofit이 아니라 확장.**

## 스코프 의미 (memory와 같은 정신)

- **전역 도구** — 어디서나 통한다(`~/.pouch/catalog/`).
- **프로젝트 도구** — 그 repo에서만, 전역에 *더해서*(`<repo>/.pouch/catalog/`).
- `.pouch/`라 로컬 전용·백업 제외(레인 2a와 같은 자리).

## 최소 첫 슬라이스 — 레지스트리 (이번 조각)

| 조각 | 내용 |
|---|---|
| `paths.project_catalog_dir` | `<repo>/.pouch/catalog/`(프로젝트 밖이면 None) |
| `catalog import --project` | 그 repo의 카탈로그에 **바로** 담는다 — 명시 의도라 소스 게이트를 건너뛴다(install·세트와 같은 정신). 프로젝트 밖이면 에러 |
| `catalog list` | 전역 목록 아래 "📁 이 프로젝트 주머니" 구역 |

## 밖에 두는 것 (다음)

- **표면/install 스코핑** — MCP는 프로젝트 `.mcp.json`이 자연스럽지만, **스킬은 Claude가
  전역(`~/.claude/skills`)이라 프로젝트 표면 자리가 없다.** 이 비대칭은 별도 설계. 이번
  슬라이스는 레지스트리(무엇이 이 프로젝트 것인가)까지 — memory가 저장·목록 먼저였듯.
- **evolve 제안** — "프로젝트 P에서 자주 쓰는 X를 P 주머니로?"(레인 2a 신호 활용). 다음.

> 이 문서도 열어두는 문서다. 다음 조각을 정하면 근거와 함께 남긴다.
