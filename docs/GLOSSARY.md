# 📖 pouch 용어 사전

> **이 사전은 오너가 실제로 막힌 단어에서 자라난다.** Claude가 미리 다 채워넣지
> 않는다 — [HOW-IT-WORKS.md](HOW-IT-WORKS.md)를 읽다 걸린 단어가 항목이 된다.
> 그래야 "아는 척 넘어간 단어" 없이, 사전이 진짜 이해 격차의 지도가 된다.
>
> 각 항목은 네 칸이다: **쉬운 말 / 왜 이 개념이 생겼나 / 헷갈리기 쉬운 점 / 코드·문서 위치.**
> 정의만 있으면 반쪽이다 — pouch의 용어는 대개 결정 하나를 통째로 담고 있어서,
> "왜 생겼나"를 알아야 그 결정을 검토(=오너 노릇)할 수 있다.

---

## 표면 (surface)

**쉬운 말** — 에이전트가 실제로 도구를 꺼내 쓰는 자리. 공사현장으로 치면
"그날 연장통에 꺼내놓은 연장". 구체적으로는 `~/.claude/skills/` 폴더와
프로젝트의 `.mcp.json` 파일 — Claude Code가 세션을 시작할 때 스캔해서
"내가 쓸 수 있는 도구가 뭐지?"를 파악하는 바로 그 자리다.

**왜 이 개념이 생겼나** — "장부에 등록됨"과 "지금 쓸 수 있음"을 갈라야 했기
때문이다. 이 둘이 갈려 있어야 evolve가 "창고엔 두되 연장통에서만 뺀다"
(=떨어진다≠삭제된다)를 할 수 있다. 표면이 없으면 "내린다"가 곧 "지운다"가 되어
되돌릴 수 없어진다.

**헷갈리기 쉬운 점** — 표면은 "홈디렉토리 같은 넓은 작업 환경"이 아니다.
에이전트가 도구를 읽어가는 **특정한 몇 자리**를 콕 집어 가리키는 말이다.
"설치한다 = 표면에 올린다", "내린다 = 표면에서 뺀다"로 읽으면 된다.

**위치** — 경로 정의 [src/pouch/paths.py](../src/pouch/paths.py)
(`claude_skills_dir`, `project_mcp_config_path`) · 스키마의 `surface` 필드
[src/pouch/catalog/model.py](../src/pouch/catalog/model.py)

---

## 카탈로그 / 장부 (catalog)

**쉬운 말** — pouch가 **"네 도구"로 관리하는** 것들의 목록. 파일 하나 = 도구 하나.
`~/.pouch/catalog/`에 산다. 여기 있는 것만 pouch가 챙긴다(목록·상태·추천·오르내림
제안). 소스(아래)에서 실제로 쓰거나 install해 **진입한** 것이 여기 올라온다.

**왜 이 개념이 생겼나** — pouch가 관리할 도구와 아직 관심 밖인 후보를 갈라야
했기 때문이다. import한 것을 전부 여기 넣으면(옛 방식) 안 쓰는 도구 수백 개가
"내가 진짜 뭘 쓰는지"의 신호를 묻는다. 그래서 진입 문턱을 두어, **실사용이
증명한 것만** 장부에 올린다(관문 "다" 정책).

**헷갈리기 쉬운 점** — 이제 도구는 **세 자리**를 거친다:
① `catalog import`로 **소스**에 재워둠(pouch가 아직 못 본 척) → ② 실제로 쓰거나
`install`하면 **장부**로 진입(pouch가 관리 시작) → ③ `install`로 **표면**(연장통)에
올림(에이전트가 실사용). 옛 문서는 ①과 ②가 한 단계였다 — import가 곧 장부 등록.
지금은 그 사이에 소스라는 대기 자리가 생겼다. 그리고 **장부에 있다 ≠ 에이전트가
쓸 수 있다**는 여전히 맞다(그건 ③ 표면의 몫).

**위치** — 저장·조회 [src/pouch/catalog/store.py](../src/pouch/catalog/store.py) ·
들여오기 [src/pouch/catalog/importer.py](../src/pouch/catalog/importer.py) ·
소스→장부 진입 [src/pouch/evolution/reconcile.py](../src/pouch/evolution/reconcile.py) ·
표면에 올리기 [src/pouch/catalog/install.py](../src/pouch/catalog/install.py)

---

## 소스 / 소스 스테이징 (sources)

**쉬운 말** — import했지만 **아직 안 써서 장부엔 안 든** 것들이 재워지는 대기
자리. `~/.pouch/sources/`에 산다. 백과사전에 항목이 있다고 표시만 한 것 —
내 노트(장부)에 옮겨 적힌 건 아니다. `pouch catalog list --sources`로 본다.

**왜 이 개념이 생겼나** — `import`가 곧바로 장부에 넣던 옛 방식에선, 플러그인
하나를 들이면 그 안의 스킬 수백 개가 몽땅 장부로 직행했다. 그래서 import를
"가리키기"로 낮추고, 진짜 장부 진입은 실사용에 맡기려고 이 중간 자리를 만들었다
(관문 "다"). import는 후보를 넓게 가리키고, 무엇이 장부에 들어갈지는 사용이 정한다.

**헷갈리기 쉬운 점** — 소스에 있는 동안 pouch는 **일부러 못 본 척한다**: 목록에도
안 뜨고(`--sources`로만 보임), 상태·추천·evolve 제안 어디에도 안 잡힌다. "import했는데
왜 아무 일도 안 일어나지?"의 답이 이것이다 — 정상이다. 한 번 써보거나 `install`하면
그때 장부로 진입해 pouch의 레이더에 들어온다. 소스는 카탈로그와 **형제 디렉토리**라
같은 코드(`CatalogStore`)로 다루되, 위치가 곧 상태 구분이다.

**위치** — 경로 [src/pouch/paths.py](../src/pouch/paths.py) (`sources_dir`) ·
import가 소스로 담음 [src/pouch/catalog/commands.py](../src/pouch/catalog/commands.py)
(`import_source`) · 진입(promote)·강등(demote)
[src/pouch/catalog/promote.py](../src/pouch/catalog/promote.py) ·
[src/pouch/catalog/demote.py](../src/pouch/catalog/demote.py)

---

## 문 앞 대기 (pending) / 저마찰

**쉬운 말** — 기억을 가볍게 담되, 확인 전까지는 매 세션 에이전트에게
자동으로 들이밀지 않는 상태. 저장은 이미 됐고, "책상 위(indexed)"로 올릴지만
아직 안 정해진 것.

**왜 이 개념이 생겼나** — 긴장 하나를 풀기 위해서다. 기억을 쉽게 쌓게 만들수록
(저마찰) 쓸모없는 것도 쉽게 쌓인다. 해법: 쉽게 들어온 것은 일단 문 앞에
세워두고, 책상에 올리는 것(promote)만 확인을 거친다. 그러면 쓰레기가 쌓여도
문 앞에 쌓이지 책상(=에이전트가 매 세션 읽는 목차)에는 안 쌓인다.

**헷갈리기 쉬운 점** — pending은 "기록 안 함"이 **아니다**. 세 상태 모두 파일로
저장은 된다. 갈리는 건 오직 **주입 여부**(에이전트가 매 세션 자동으로 읽느냐):
책상(indexed)=주입됨 / 문 앞(pending)=저장됐지만 주입 안 됨 / 서랍(archived)=
목차에서 내려갔지만 recall로 부르면 나옴. 저마찰의 진짜 뜻은 "막 담아도 안전하다 —
확인 전엔 에이전트를 오염시키지 못하니까"다.

**위치** — 상태 정의 [src/pouch/memory/model.py](../src/pouch/memory/model.py)
(`MemoryState`) · 문 앞 대기열과 타입별 마찰
[src/pouch/memory/pending.py](../src/pouch/memory/pending.py)

---

## 경계의 방향 (direction) — allow / ask / deny

**쉬운 말** — 에이전트에게 거는 규칙(경계)이 어느 쪽인지. 세 가지다:
**허용(allow)** "dev는 자율로 해라" / **확인(ask)** "prod 바꾸기 전엔 물어봐라" /
**금지(deny)** "force push는 하지 마라".

**왜 이 개념이 생겼나** — 원래 경계는 자연어 문장 하나였다("테스트 통과 시 커밋
자율, force는 금지"). 사람은 읽으면 알지만, 기계가 이 문장에서 방향을 뽑으려다
**금지를 허용으로 잘못 읽는 사고**가 가장 위험했다. 그래서 방향을 문장 속에
묻어두지 않고 대괄호 라벨로 꺼내 박았다 — 기계는 이제 산문을 해석할 필요 없이
`[DENY]`를 그냥 읽는다. 도구를 내릴 때 "무엇을 함께 내리고 무엇을 남길지"도
이 방향이 가른다(허용은 도구와 함께, 금지·확인은 남김).

**헷갈리기 쉬운 점** — 방향이 붙어도 pouch는 **막지 않는다**. 방향은 에이전트가
"알고 존중하게" 하는 것이지 강제(차단)가 아니다(진짜 강제는 IAM·SCP의 일 —
[BACKLOG.md](../BACKLOG.md) D1). 또 방향은 경계(boundary)에만 있다 — 일반 기억엔
방향 개념이 없다. 방향이 비어 있는 옛 경계는 "잘 모름"으로 취급해 **안전 쪽
(남김)** 으로 처리한다.

**위치** — 정의 [src/pouch/memory/model.py](../src/pouch/memory/model.py)
(`Direction`) · 주입 라벨 [src/pouch/memory/context.py](../src/pouch/memory/context.py)
· 내릴 때 가르기 [src/pouch/catalog/boundary.py](../src/pouch/catalog/boundary.py)
(`plan_boundary_drop`)

---

## 경계의 출처 (source) — 누가 이 규칙을 걸었나

**쉬운 말** — 이 경계를 **사람이 직접** 걸었는지(`user`), 아니면 **도구가 딸고
왔는지**(`vendored:<도구이름>`)의 꼬리표. 예: aws-cdk 도구를 담을 때 "prod는
승인" 경계가 함께 따라왔다면 그 경계의 출처는 `vendored:aws-cdk`다.

**왜 이 개념이 생겼나** — 도구를 내릴 때 경계를 어떻게 할지 정하려면 출처를
알아야 했다. 사람이 손수 건 규칙은 도구를 내려도 **남아야** 한다(내 규칙이니까).
도구가 딸고 온 규칙은 도구와 운명을 같이해야 한다(그 도구 쓰려고 생긴 거니까).
출처 꼬리표가 없으면 "이 경계 왜 있지?"도 헷갈리고, 내릴 때 무엇을 남길지도
정할 수 없다. body와 개인화(overlay)를 갈라둔 것과 같은 정신 — 출신이 다르면
운명도 달라야 한다.

**헷갈리기 쉬운 점** — 출처는 CLI로 **주장할 수 없다**. `pouch memory add`로
직접 담는 경계는 정의상 언제나 `user`다 — 플래그로 `vendored:foo`인 척하게
허용하면 "누가 만들었나"의 의미가 무너진다. `vendored:` 출처는 도구를 설치하는
경로(승격 통로)만 프로그램으로 새길 수 있다.

**위치** — 정의 [src/pouch/memory/model.py](../src/pouch/memory/model.py)
(`SOURCE_USER`, `VENDORED_SOURCE_PREFIX`) · 도구 설치 시 새기기(승격)
[src/pouch/catalog/boundary.py](../src/pouch/catalog/boundary.py)
(`recommended_boundary_memories`)

---

## 풀 (pool) — "이거 써봐"의 후보 창고

**쉬운 말** — pouch가 "이거 써봐" 하고 추천할 때, **후보를 어디서 꺼내오나**의
목록이다. 지금(v0)은 **네 카탈로그(이미 담은 것들)** 그 자체다. 카탈로그 항목이
저마다 {이름·설명·태그}를 이미 달고 있어서, 그걸 추천에 알맞은 모양으로 훑어낸 게
풀이다. 나중엔 바깥 마켓까지 넓힐 자리.

**왜 이 개념이 생겼나** — "네가 자꾸 terraform을 쓰네, 비슷한 이거 안 써봤어?"를
하려면 **"비슷한 이거"의 후보가 어딘가 있어야** 한다. 그 후보 창고가 없으면 추천은
공회전한다. 그런데 이 창고를 **우리가 지어내면 안 된다** — 예전에 "DevOps면 이거
쓰겠지" 하고 채운 세트가 실사용과 달라 지웠다. 그래서 풀은 **네 카탈로그(=진짜
네 것)** 에서만 나오고, 각 항목 설명·태그도 도구 자기 파일(SKILL.md)에서만 온다.
"비슷하다"의 판정도 **태그 겹침**으로만 한다 — 태그는 우리 판단이 아니라 도구가
달고 온 사실이라, 매칭에 추측이 안 섞인다.

**헷갈리기 쉬운 점** — 풀은 카탈로그와 **다른 물건이 아니다**. v0에선 카탈로그를
추천용으로 바라본 *뷰*일 뿐이다(별도 저장소 없음). 또 풀은 "많이 쓰는 것"이 아니라
"**있는 것**"의 목록이다 — "남들이 많이 쓴다"는 인기 데이터는 raft(공유)가 진짜
데이터를 만들 때까지 없다. 그리고 네가 반복한 도구가 태그가 없는 날것이면 "비슷한
것"을 못 준다(근거가 없어서) — 그 도구 자체만 제안된다.

**위치** — 풀 만들기 [src/pouch/evolution/pool.py](../src/pouch/evolution/pool.py)
(`build_pool`, `PoolEntry`) · 비슷한 것 찾기·조립
[src/pouch/evolution/similar.py](../src/pouch/evolution/similar.py)
(`find_similar`, `plan_try_this`)

---

## 핵심 도구 (core tool)

**쉬운 말** — 오래 걸쳐 꾸준히·많이 써서 "손에 맞은" 도구. pouch가 사용 기록에서
스스로 알아본다(count≥10 + 처음~마지막 사용 간격≥21일). `pouch`·`pouch report`가 🪨로 표시.

**왜 이 개념이 생겼나** — "쓸수록 나에게 맞춰진다"를 손이 아니라 실사용이 채우게
하려고(개인화 학습의 첫 걸음). 핵심 도구는 잠깐 안 써도 evolve의 "내리자" 제안에서
보호된다 — 오래 걸쳐 손이 간 도구가 한 주 공백으로 흔들리면 안 되니까(기억에서
weight 높은 것이 위생 제안에서 빠지는 것과 같은 정신).

**헷갈리기 쉬운 점** — 핵심은 **최근성이 아니라 지속**이다. 이번 주 몰아 쓴 것(burst)은
핵심이 아니고(span이 짧다), 오래 걸쳐 써온 것이 핵심이다. 그래서 조용한 주에도 보인다.
"많이/최근 씀"은 status의 "최근 7일" 줄이 따로 보여준다.

**위치** — 판정 [src/pouch/evolution/core_tools.py](../src/pouch/evolution/core_tools.py)
(`core_entry_ids`) · drop 보호 [src/pouch/evolution/commands.py](../src/pouch/evolution/commands.py) ·
표시 [src/pouch/status.py](../src/pouch/status.py) · [src/pouch/report.py](../src/pouch/report.py)

---

## 이관 (adopt)

**쉬운 말** — Claude Code의 자체 메모리(`~/.claude/projects/.../memory/`)를 pouch로
넘겨받는 것. `pouch memory adopt`. 타입이 자리·계층을 정하고, 원본은 복사라 안 지운다.

**왜 이 개념이 생겼나** — 네이티브 메모리는 생명주기가 없어 지난 세션로그까지 전부
매 세션 주입한다. 이관은 그걸 pouch의 "안정 핵심만 주입"으로 복원하며 청소한다 —
호스트를 가로지르는 하나의 기억 레이어로 모으는 첫 조각.

**헷갈리기 쉬운 점** — 기본은 **옮기기만** 한다(네이티브는 안전망으로 남음). 네이티브를
아예 끄는 완전 대체는 `--disable-native`로 명시 선택이다 — 끄면 에이전트의 자동 쓰기
길도 막히므로, 주입에 심은 "`pouch memory add`로 남겨라" 지침이 그 자리를 잇는다.

**위치** — [src/pouch/memory/adopt.py](../src/pouch/memory/adopt.py) ·
설계 [MEMORY-REPLACE-DESIGN.md](MEMORY-REPLACE-DESIGN.md)

---

*(다음 항목은 다음에 막히는 단어에서.)*
