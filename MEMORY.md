---
name: Resume Automation Tool Memory Index
description: Index of memory files for the resume automation tool project
type: project
---

# Memory Index for Resume_Custom

## Decision Log
- **Architecture**: Arch B by default (LLM extraction + deterministic patching), Arch C optional via `--premium` flag

## Key files
- `keywords.py` — master keyword list + synonym normalization map (source of truth)
- `arch_a.py` — regex/TF-IDF deterministic extractor
- `arch_b.py` — Claude API extractor (structured JSON, temp=0)
- `benchmark.py` — side-by-side comparison runner
- `fixtures/` — 5 test JD files
