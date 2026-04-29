"""
Arch A — Fully deterministic keyword extractor.
Regex-scans the JD for any term in (MASTER_KEYWORDS ∪ SYNONYM_MAP), normalizes via
synonym map, then returns canonical forms. Anything that normalizes to a term NOT in
MASTER_KEYWORDS still gets returned — it will land in "real_gap" during diff.
"""

import re
import time
from keywords import MASTER_KEYWORDS, SYNONYM_MAP, normalize


def _build_pattern() -> re.Pattern:
    all_terms = set(MASTER_KEYWORDS.keys()) | set(SYNONYM_MAP.keys())
    # Longest first prevents partial matches (e.g. "rest" before "rest api")
    sorted_terms = sorted(all_terms, key=len, reverse=True)
    escaped = [re.escape(t) for t in sorted_terms]
    return re.compile(r'\b(' + '|'.join(escaped) + r')\b', re.IGNORECASE)


_PATTERN = _build_pattern()


def extract(jd_text: str) -> tuple[list[str], float]:
    """
    Returns (list of canonical keywords found in JD, elapsed_seconds).
    Includes terms that normalize to genuine gaps — diff.py handles categorization.
    """
    start = time.perf_counter()
    raw_matches = _PATTERN.findall(jd_text)
    # Normalize and deduplicate; keep even if not in master (diff will flag as gap)
    canonical = {normalize(m) for m in raw_matches}
    elapsed = time.perf_counter() - start
    return sorted(canonical), elapsed
