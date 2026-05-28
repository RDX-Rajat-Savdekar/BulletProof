# Session 1 — Resume Automation Tool (BulletProof / ResumeKit)

## What this project is
A local web tool to apply to 10–15 jobs/day. Paste a JD → extract keywords → see gap analysis → toggle bullets → export a tailored PDF. Everything runs locally via FastAPI + a vanilla JS SPA.

**Stack:** Python (FastAPI, Anthropic SDK, BeautifulSoup), LaTeX (TinyTeX), vanilla JS single-file frontend, no build step.

**Run:** `source .venv/bin/activate && python3 server.py` → `http://127.0.0.1:8000`

---

## File map

| File | Role |
|---|---|
| `server.py` | FastAPI backend — all API endpoints |
| `source_truth.json` | Master data: personal, education, work_experience, projects, skills |
| `Rajat_Ref_Resume.tex` | LaTeX resume template with patch markers |
| `latex_gen.py` | Reads template + source_truth → patches markers → returns LaTeX string |
| `keywords.py` | Derives MASTER_KEYWORDS from source_truth; SYNONYM_MAP (100+ entries); `coverage(kw)` |
| `diff.py` | `analyze(jd_keywords)` → covered / can_surface / skills_only / real_gap + HH grade |
| `arch_a.py` | Regex keyword extractor (free, context-blind) |
| `arch_b.py` | Claude Haiku keyword extractor (~$0.002/call, temp=0) |
| `static/index.html` | Full SPA — 4 tabs: Source Truth, Analyze JD, Build Resume, Ideas |
| `project_ideas.json` | Persisted LLM-suggested project ideas (never wiped on restart) |
| `resume_history.json` | Log of every PDF/tex export with version ID (never wiped on restart) |
| `.env` | `ANTHROPIC_API_KEY=sk-ant-...` |
| `.gitignore` | Blocks .env, __pycache__, .venv, *.pdf, resume_history.json, project_ideas.json |

---

## Architecture decisions (locked in)

**Arch B by default:** Claude Haiku (temp=0) for keyword extraction — structured JSON output, handles unknown keywords (Oracle, FIX protocol, etc.) that regex can't find. Arch A (regex) available as free fallback via the "Regex" button.

**No LLM bullet rewriting** for daily use — hallucination risk + verification overhead. LLM only used for: (1) keyword extraction, (2) project suggestion.

**Suggested project is ephemeral** — not saved to source_truth unless user explicitly clicks "Save to Ideas". Passed separately to `latex_gen.generate()` as `suggested_project` param.

---

## source_truth.json schema

```json
{
  "personal": { "name", "location", "phone", "email", "linkedin", "github", "note" },
  "education": [{ "id", "school", "degree", "gpa", "period", "location" }],
  "work_experience": [{ "id", "title", "company", "period", "location", "bullets": [...] }],
  "projects": [{ "id", "name", "links": {"live","demo","github"}, "bullets": [...] }],
  "skills": { "languages", "frameworks", "databases", "infrastructure", "other" }
}
```

Each bullet: `{ "id", "text" (plain), "latex" (with \textbf{}), "keywords": ["kw", "~implicit-kw"] }`

`~` prefix on keyword = implicit coverage (implied but not stated directly).

---

## LaTeX template markers

| Marker | What gets patched |
|---|---|
| `%%PERSONAL_HEADER%%` | Full `\begin{center}...\end{center}` header from personal data |
| `%%EDUCATION_BLOCK%%` | All `\eduentry` calls from education array |
| `%%BULLETS:ta%%` / `%%END:ta%%` | Work experience bullet list (marker-based, one per role ID) |
| `%%BULLETS:jalgaon%%` / `%%END:jalgaon%%` | Same for jalgaon role |
| `%%PROJECTS_BLOCK%%` | All project entries generated dynamically (ranked order) |

Skills section patched via regex: `\noindent\textbf{Languages:}...` etc.

**Font:** `tgschola` (TeX Gyre Schola) — `newcent` not available in TinyTeX repo.

**TinyTeX bin path (Mac):** `~/Library/TinyTeX/bin/universal-darwin` — add to PATH if pdflatex not found.

---

## Keyword coverage levels

`bullet` > `implicit` > `skills` > `None` (real gap)

- **bullet:** keyword explicitly in a resume bullet
- **implicit:** `~` prefixed keyword (implied by bullet content)
- **skills:** only in skills section, no bullet
- **real_gap:** not present anywhere

---

## HH grading

| Grade | Ratio |
|---|---|
| A+ | ≤ 1:1.1 |
| A | ≤ 1:1.25 |
| B | ≤ 1:1.5 |
| C | ≤ 1:1.75 |
| D | ≤ 1:2.0 |
| F | beyond 1:2 |

Apply recommended when ratio ≤ 1.75 (C or better).

---

## Version ID format

`R{YYYYMMDD}-{HHMM}-{4hex}` e.g. `R20260429-1420-a3f2`

Every compile logs to `resume_history.json` with: id, timestamp, date_local, time_local, company, role_title, grade, coverage_pct, format (pdf/latex), jd_snippet, active_projects, project_order, selected_bullet_ids, suggested_project.

---

## Key API endpoints

```
GET  /api/source-truth
PUT  /api/personal          { personal: {...} }
PUT  /api/education         { education: [...] }
PUT  /api/skills            { skills: {...} }
POST /api/bullet/add        { section, section_id, text, latex, keywords }
PUT  /api/bullet/update     { bullet_id, text, latex, keywords }
DEL  /api/bullet/{id}
POST /api/project/add       { id, name, links, bullets }
DEL  /api/project/{id}
POST /api/work/add          { id, title, company, period, location, bullets }
DEL  /api/work/{id}

POST /api/analyze           { jd, use_llm, suggest_project }
POST /api/compile           { selected_bullet_ids, format, project_order,
                              suggested_project, jd_snippet, grade,
                              coverage_pct, active_projects, company, role_title }
                            → headers: X-Version-Id, X-Fallback

GET  /api/resume/history
GET  /api/resume/version/{id}

GET  /api/project-ideas
POST /api/project-ideas/save     { idea, jd_snippet }
PUT  /api/project-ideas/status   { idea_id, status: "idea"|"building"|"built" }
DEL  /api/project-ideas/{name}
```

---

## UI tabs

**Source Truth** — edit personal info, education, skills (save buttons per section), bullet library with inline edit/delete/add per role and project.

**Analyze JD** — paste JD or URL, AI or Regex button, "Suggest project for gaps" checkbox (AI only). Shows grade badge, gap buckets (real/surface/skills/covered), suggested project card with include toggle + Save to Ideas.

**Build Resume** — ranked project cards (top N auto-selected, configurable), bullet toggles with gap tags, score panel showing live keyword coverage %. Company + Role inputs before export. Version ID badge after export with copy button. Recreate-by-ID input. View History button.

**Ideas** — directory of saved suggested projects with status (idea → building → built), timestamps, delete.

---

## Bugs fixed this session

- `result["real_gap"]` is a plain string list — server.py was doing `i["keyword"]` on it → `TypeError` → 500 on every suggest-project call. Fixed to `result["real_gap"] + result["can_surface"]` directly.
- `newcent` font not in TinyTeX → blank 9KB PDF. Fixed by switching to `tgschola`.
- pdflatex PATH: TinyTeX installs to `~/Library/TinyTeX` not `~/.TinyTeX` on Mac.

---

## Things NOT done yet (possible next sessions)

- Save suggested project directly into source_truth as a real project (currently ephemeral only)
- URL fetching for JDs sometimes blocked by anti-scraping (LinkedIn, Greenhouse) — fallback to paste
- No authentication — purely local tool
- Mobile layout not tested
- skills section in PDF not dynamically driven from source_truth fully (skills regex patch exists but display format is comma-separated flat, not grouped)
- No bulk export / batch apply tracking
