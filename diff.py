"""
Deterministic gap analysis — same logic regardless of which extractor produced the keyword list.
"""

from keywords import coverage


def analyze(jd_keywords: list[str]) -> dict:
    covered = []
    can_surface = []
    skills_only = []
    real_gap = []

    for kw in jd_keywords:
        level = coverage(kw)
        if level == "bullet":
            covered.append(kw)
        elif level == "implicit":
            can_surface.append(kw)
        elif level == "skills":
            skills_only.append(kw)
        else:
            # coverage() returned None — not in master list at all
            real_gap.append(kw)

    total = len(jd_keywords)
    matched = len(covered) + len(can_surface) + len(skills_only)
    ratio = total / matched if matched > 0 else float("inf")
    grade = _grade(ratio)
    coverage_pct = round(matched / total * 100) if total > 0 else 0

    return {
        "covered": covered,
        "can_surface": can_surface,
        "skills_only": skills_only,
        "real_gap": real_gap,
        "total_jd_keywords": total,
        "matched": matched,
        "coverage_pct": coverage_pct,
        "hh_ratio": f"1:{round(ratio, 1)}" if ratio != float("inf") else "∞",
        "grade": grade,
        "apply_recommended": ratio <= 1.75,
    }


def _grade(ratio: float) -> str:
    if ratio <= 1.1:   return "A+"
    if ratio <= 1.25:  return "A"
    if ratio <= 1.5:   return "B"
    if ratio <= 1.75:  return "C"
    if ratio <= 2.0:   return "D"
    return "F"
