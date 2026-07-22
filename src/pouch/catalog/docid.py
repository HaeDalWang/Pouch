"""규칙(rule)의 정체(id) ↔ 원래 자리 — 접기와 펴기를 한 곳에 둔다.

규칙만 원래 자리가 한 겹 깊다(`rules/<묶음>/<이름>.md`). `coding-style.md`가
python/·common/·golang/… 여러 묶음에 겹치기 때문이다. 장부(store)는 평면
(`<id>.md`)이라 들일 때 `<묶음>__<이름>`으로 **접고**, 표면에 올릴 때 다시 폴더로
**편다**.

두 방향이 서로 다른 파일에 흩어져 있으면 한쪽만 바뀌어 왕복이 어긋난다 —
주워온 자리와 내려놓는 자리가 달라지는 순간 "되돌려놨다"가 거짓말이 된다.
그래서 접기·펴기를 이 한 파일에 둔다(배승도 락 2026-07-22).
"""

from __future__ import annotations

# 폴더 경계를 접은 자국. 파일명에 안전하고, 실제 규칙 이름에는 거의 안 쓰인다.
RULE_ID_SEPARATOR = "__"


def fold_rule_id(group: str, name: str) -> str:
    """`python`+`coding-style` → `python__coding-style`. 평면 장부에 앉힐 이름."""
    return f"{group}{RULE_ID_SEPARATOR}{name}"


def unfold_rule_id(entry_id: str) -> tuple[str, ...]:
    """접힌 이름을 표면 경로 조각으로 편다.

    `python__coding-style` → `("python", "coding-style")`.
    접은 자국이 없으면 폴더 없이 이름 하나로 본다 — 없는 묶음을 지어내지 않는다.
    자국이 여럿이면 **첫 번째만** 폴더 경계다: 이름 자체에 `__`가 있던 규칙
    (`common__a__b`)이 원래 이름 `a__b`를 잃지 않는다.
    """
    group, mark, name = entry_id.partition(RULE_ID_SEPARATOR)
    if not mark:
        return (entry_id,)
    return (group, name)
