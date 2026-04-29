"""
Arch B — LLM-based keyword extractor (Claude, temp=0, structured JSON output).
Used for extraction only. Everything after this is deterministic.
"""

import json
import os
import time
import anthropic
from keywords import normalize, coverage

_CLIENT = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

SYSTEM_PROMPT = """You are a technical resume keyword extractor.

Given a job description, extract all technical keywords that a software engineer would put on a resume.

Rules:
- Output ONLY a JSON object: {"keywords": ["keyword1", "keyword2", ...]}
- Normalize to canonical forms: use "Node.js" not "NodeJS", "REST API" not "RESTful APIs", "PostgreSQL" not "Postgres", "TypeScript" not "TS", "CI/CD" not "Continuous Integration"
- Include: programming languages, frameworks, libraries, databases, tools, infrastructure, architecture patterns, methodologies
- Exclude: soft skills, company names, generic business terms ("team player", "communication")
- No duplicates, all lowercase except proper nouns
- Do not include anything that isn't a concrete technical skill or tool"""


def extract(jd_text: str) -> tuple[list[str], float, float]:
    """
    Returns (list of canonical keywords found in JD, elapsed_seconds, cost_usd).
    Normalizes LLM output through the same synonym map used by Arch A.
    """
    start = time.perf_counter()

    response = _CLIENT.messages.create(
        model="claude-haiku-4-5-20251001",  # cheapest, fast, sufficient for structured extraction
        max_tokens=512,
        temperature=0,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Job description:\n\n{jd_text}"}],
    )

    elapsed = time.perf_counter() - start

    # Cost estimate: Haiku input ~$0.80/MTok, output ~$4/MTok
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    cost_usd = (input_tokens * 0.80 + output_tokens * 4.0) / 1_000_000

    raw_text = response.content[0].text.strip()

    # Parse JSON — if malformed, fall back to empty list with error note
    try:
        data = json.loads(raw_text)
        raw_keywords = data.get("keywords", [])
    except json.JSONDecodeError:
        # Try to extract JSON block if wrapped in markdown
        import re
        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if match:
            data = json.loads(match.group())
            raw_keywords = data.get("keywords", [])
        else:
            raw_keywords = []

    # Normalize through synonym map, filter to only known master keywords
    canonical = {normalize(k) for k in raw_keywords}
    found = [k for k in canonical if coverage(k) is not None]

    return sorted(found), elapsed, cost_usd
