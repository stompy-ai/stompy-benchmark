"""Preserve independent INVALID causes without replacing earlier evidence."""


def invalidate(row: dict, reason: str, *, primary: bool = False) -> None:
    reasons = row.setdefault("reasons", [])
    previous = row.get("reason")
    if previous == "; ".join(reasons):
        previous = None
    for value in (previous, reason):
        if value and value not in reasons:
            reasons.append(value)
    row.update(outcome="INVALID", score=None)
    row["reason"] = reason if primary else "; ".join(reasons)
