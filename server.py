"""FastAPI backend for the Resume Keyword Tool."""

import json
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

import anthropic
import requests as http_requests
from bs4 import BeautifulSoup

import keywords as kw_module
from diff import analyze
from latex_gen import compile_pdf, generate

app = FastAPI()

_DATA_PATH    = Path(__file__).parent / "source_truth.json"
_STATIC_PATH  = Path(__file__).parent / "static"
_IDEAS_PATH   = Path(__file__).parent / "project_ideas.json"
_HISTORY_PATH = Path(__file__).parent / "resume_history.json"

_CLIENT = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# ── Ensure storage files exist ────────────────────────────────────────────────
for _p, _default in [(_IDEAS_PATH, "[]"), (_HISTORY_PATH, "[]")]:
    if not _p.exists():
        _p.write_text(_default)

# ── System prompts ─────────────────────────────────────────────────────────────
_EXTRACT_SYSTEM = """You are a technical resume keyword extractor.
Given a job description, extract all technical keywords a software engineer would put on a resume.
Output ONLY: {"keywords": ["keyword1", ...]}
Rules: canonical lowercase forms, no soft skills, no duplicates, no company names."""

_SUGGEST_SYSTEM = """You are a resume project advisor for a software engineer.

Given keyword gaps from a job description, suggest ONE specific buildable project.

Rules:
- Use as many gap keywords as possible
- Buildable in 1-2 weeks with AI coding tools
- Must be specific (not vague like "build a full-stack app")
- 3 bullets following HH format: What + How + Result with concrete metrics
- In the latex field, wrap key technologies with \\textbf{}

Return ONLY valid JSON (no markdown fences):
{
  "name": "Project Name",
  "tagline": "One sentence what it does",
  "tech_stack": ["tech1", "tech2"],
  "build_time": "1 week",
  "why_this_jd": "One sentence why this targets the gaps",
  "bullets": [
    {"text": "plain text bullet", "latex": "latex with \\\\textbf{Tech} highlighted"},
    {"text": "...", "latex": "..."},
    {"text": "...", "latex": "..."}
  ],
  "keywords_covered": ["kw1", "kw2"]
}"""


# ── Pydantic models ────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    jd: str
    use_llm: bool = True
    suggest_project: bool = False

class SaveSourceTruthRequest(BaseModel):
    data: dict

class UpdatePersonalRequest(BaseModel):
    personal: dict

class UpdateEducationRequest(BaseModel):
    education: list

class UpdateSkillsRequest(BaseModel):
    skills: dict

class AddBulletRequest(BaseModel):
    section: str
    section_id: str
    text: str
    latex: str = ""
    keywords: list[str] = []

class UpdateBulletRequest(BaseModel):
    bullet_id: str
    text: str
    latex: str = ""
    keywords: list[str]

class AddProjectRequest(BaseModel):
    id: str
    name: str
    links: dict = {}
    bullets: list[dict] = []

class AddWorkExpRequest(BaseModel):
    id: str
    title: str
    company: str
    period: str
    location: str
    bullets: list[dict] = []

class CompileRequest(BaseModel):
    selected_bullet_ids: list[str]
    format: str = "latex"
    project_order: list[str] = []
    suggested_project: dict | None = None
    # For version logging
    jd_snippet: str = ""
    grade: str = ""
    coverage_pct: int = 0
    active_projects: list[str] = []
    company: str = ""
    role_title: str = ""

class SaveIdeaRequest(BaseModel):
    idea: dict
    jd_snippet: str = ""

class UpdateIdeaStatusRequest(BaseModel):
    idea_id: str
    status: str  # idea | building | built


# ── Helpers ───────────────────────────────────────────────────────────────────

def _read_data() -> dict:
    return json.loads(_DATA_PATH.read_text())

def _write_data(data: dict):
    _DATA_PATH.write_text(json.dumps(data, indent=2))
    kw_module.reload()

def _fetch_jd_text(url_or_text: str) -> str:
    text = url_or_text.strip()
    if text.startswith("http://") or text.startswith("https://"):
        try:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; ResumeBot/1.0)"}
            resp = http_requests.get(text, headers=headers, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            return soup.get_text(separator="\n", strip=True)
        except Exception as e:
            raise HTTPException(400, f"Could not fetch URL: {e}. Paste JD text directly.")
    return text

def _extract_keywords_llm(jd_text: str) -> tuple[list[str], float]:
    resp = _CLIENT.messages.create(
        model="claude-haiku-4-5-20251001", max_tokens=512, temperature=0,
        system=_EXTRACT_SYSTEM,
        messages=[{"role": "user", "content": f"Job description:\n\n{jd_text[:6000]}"}],
    )
    cost = (resp.usage.input_tokens * 0.80 + resp.usage.output_tokens * 4.0) / 1_000_000
    raw = resp.content[0].text.strip()
    try:
        raw_kws = json.loads(raw).get("keywords", [])
    except json.JSONDecodeError:
        import re
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        raw_kws = json.loads(m.group()).get("keywords", []) if m else []
    canonical = {kw_module.normalize(k) for k in raw_kws}
    return sorted(canonical), cost

def _suggest_project_llm(gap_keywords: list[str]) -> tuple[dict, float]:
    if not gap_keywords:
        return {}, 0.0
    prompt = f"Keyword gaps from this job description:\n{json.dumps(gap_keywords)}\n\nSuggest the best project."
    resp = _CLIENT.messages.create(
        model="claude-haiku-4-5-20251001", max_tokens=1024, temperature=0.3,
        system=_SUGGEST_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    cost = (resp.usage.input_tokens * 0.80 + resp.usage.output_tokens * 4.0) / 1_000_000
    raw = resp.content[0].text.strip()
    # strip possible markdown fences
    raw = raw.strip("`").lstrip("json").strip()
    try:
        proj = json.loads(raw)
    except json.JSONDecodeError:
        import re
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        proj = json.loads(m.group()) if m else {}
    # Assign stable IDs to bullets so the UI can track them
    for i, b in enumerate(proj.get("bullets", [])):
        b["id"] = f"_sug_b{i+1}"
    proj["id"] = "_suggested"
    return proj, cost

def _rank_projects(jd_keywords: list[str], data: dict) -> list[dict]:
    jd_set = set(jd_keywords)
    ranked = []
    for proj in data.get("projects", []):
        proj_kws = set()
        for b in proj.get("bullets", []):
            for kw in b.get("keywords", []):
                proj_kws.add(kw[1:] if kw.startswith("~") else kw)
        matched = proj_kws & jd_set
        score = len(matched) / len(jd_set) if jd_set else 0
        ranked.append({
            "id": proj["id"], "name": proj["name"],
            "score": round(score, 3),
            "matched_keywords": sorted(matched),
            "matched_count": len(matched),
            "total_bullets": len(proj.get("bullets", [])),
        })
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked

def _build_kw_bullet_map(data: dict) -> dict:
    kw_map = {}
    def _add(kw_raw, bullet, section_name, section_id):
        is_impl = kw_raw.startswith("~")
        canonical = kw_raw[1:] if is_impl else kw_raw
        kw_map.setdefault(canonical, []).append({
            "bullet_id": bullet["id"], "text": bullet["text"],
            "section": section_name, "section_id": section_id, "implicit": is_impl,
        })
    for role in data.get("work_experience", []):
        for b in role.get("bullets", []):
            for kw in b.get("keywords", []):
                _add(kw, b, role["title"] + " @ " + role["company"], role["id"])
    for proj in data.get("projects", []):
        for b in proj.get("bullets", []):
            for kw in b.get("keywords", []):
                _add(kw, b, proj["name"], proj["id"])
    return kw_map

def _make_version_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    suffix = secrets.token_hex(2)
    return f"R{stamp}-{suffix}"

def _log_version(version_id: str, req: CompileRequest):
    now = datetime.now(timezone.utc)
    history = json.loads(_HISTORY_PATH.read_text())
    history.append({
        "id": version_id,
        "timestamp": now.isoformat(),
        "date_local": now.strftime("%Y-%m-%d"),
        "time_local": now.strftime("%H:%M UTC"),
        "company": req.company,
        "role_title": req.role_title,
        "grade": req.grade,
        "coverage_pct": req.coverage_pct,
        "format": req.format,
        "jd_snippet": req.jd_snippet[:200],
        "active_projects": req.active_projects,
        "project_order": req.project_order,
        "selected_bullet_ids": req.selected_bullet_ids,
        "suggested_project": req.suggested_project,
    })
    _HISTORY_PATH.write_text(json.dumps(history, indent=2))


# ── Routes — source truth ─────────────────────────────────────────────────────

@app.get("/api/source-truth")
def get_source_truth():
    return _read_data()

@app.put("/api/personal")
def update_personal(req: UpdatePersonalRequest):
    data = _read_data()
    data["personal"] = req.personal
    _write_data(data)
    return {"status": "saved"}

@app.put("/api/education")
def update_education(req: UpdateEducationRequest):
    data = _read_data()
    data["education"] = req.education
    _write_data(data)
    return {"status": "saved"}

@app.put("/api/skills")
def update_skills(req: UpdateSkillsRequest):
    data = _read_data()
    data["skills"] = req.skills
    _write_data(data)
    return {"status": "saved"}

@app.post("/api/bullet/add")
def add_bullet(req: AddBulletRequest):
    data = _read_data()
    section_list = data.get(req.section, [])
    target = next((s for s in section_list if s["id"] == req.section_id), None)
    if not target:
        raise HTTPException(404, "Section not found")
    existing = {b["id"] for b in target["bullets"]}
    n = len(target["bullets"]) + 1
    new_id = f"{req.section_id}_b{n}"
    while new_id in existing:
        n += 1; new_id = f"{req.section_id}_b{n}"
    target["bullets"].append({"id": new_id, "text": req.text, "latex": req.latex or req.text, "keywords": req.keywords})
    _write_data(data)
    return {"id": new_id}

@app.put("/api/bullet/update")
def update_bullet(req: UpdateBulletRequest):
    data = _read_data()
    for sections in [data.get("work_experience", []), data.get("projects", [])]:
        for s in sections:
            for b in s.get("bullets", []):
                if b["id"] == req.bullet_id:
                    b["text"] = req.text
                    b["latex"] = req.latex or req.text
                    b["keywords"] = req.keywords
                    _write_data(data)
                    return {"status": "updated"}
    raise HTTPException(404, "Bullet not found")

@app.delete("/api/bullet/{bullet_id}")
def delete_bullet(bullet_id: str):
    data = _read_data()
    for sections in [data.get("work_experience", []), data.get("projects", [])]:
        for s in sections:
            before = len(s["bullets"])
            s["bullets"] = [b for b in s["bullets"] if b["id"] != bullet_id]
            if len(s["bullets"]) < before:
                _write_data(data)
                return {"status": "deleted"}
    raise HTTPException(404, "Bullet not found")

@app.post("/api/project/add")
def add_project(req: AddProjectRequest):
    data = _read_data()
    if any(p["id"] == req.id for p in data["projects"]):
        raise HTTPException(400, f"Project id '{req.id}' already exists")
    data["projects"].append({"id": req.id, "name": req.name, "links": req.links, "bullets": req.bullets})
    _write_data(data)
    return {"status": "added"}

@app.delete("/api/project/{project_id}")
def delete_project(project_id: str):
    data = _read_data()
    before = len(data["projects"])
    data["projects"] = [p for p in data["projects"] if p["id"] != project_id]
    if len(data["projects"]) == before:
        raise HTTPException(404, "Project not found")
    _write_data(data)
    return {"status": "deleted"}

@app.post("/api/work/add")
def add_work(req: AddWorkExpRequest):
    data = _read_data()
    if any(w["id"] == req.id for w in data["work_experience"]):
        raise HTTPException(400, f"Work id '{req.id}' already exists")
    data["work_experience"].append({"id": req.id, "title": req.title, "company": req.company, "period": req.period, "location": req.location, "bullets": req.bullets})
    _write_data(data)
    return {"status": "added"}

@app.delete("/api/work/{work_id}")
def delete_work(work_id: str):
    data = _read_data()
    before = len(data["work_experience"])
    data["work_experience"] = [w for w in data["work_experience"] if w["id"] != work_id]
    if len(data["work_experience"]) == before:
        raise HTTPException(404, "Work experience not found")
    _write_data(data)
    return {"status": "deleted"}


# ── Routes — analysis ─────────────────────────────────────────────────────────

@app.post("/api/analyze")
def analyze_jd(req: AnalyzeRequest):
    jd_text = _fetch_jd_text(req.jd)
    if len(jd_text.strip()) < 100:
        raise HTTPException(400, "JD text too short — try pasting directly")

    cost = 0.0
    if req.use_llm:
        extracted, cost = _extract_keywords_llm(jd_text)
    else:
        import arch_a
        extracted, _ = arch_a.extract(jd_text)

    result = analyze(extracted)
    data = _read_data()
    kw_map = _build_kw_bullet_map(data)
    ranked = _rank_projects(extracted, data)

    def _annotate(kw_list):
        return [{"keyword": kw, "bullets": kw_map.get(kw, [])} for kw in kw_list]

    suggested = None
    if req.suggest_project:
        gap_kws = result["real_gap"] + result["can_surface"]
        if gap_kws:
            suggested, sug_cost = _suggest_project_llm(gap_kws[:20])
            cost += sug_cost

    return {
        "keywords": extracted,
        "grade": result["grade"],
        "hh_ratio": result["hh_ratio"],
        "coverage_pct": result["coverage_pct"],
        "apply_recommended": result["apply_recommended"],
        "covered": _annotate(result["covered"]),
        "can_surface": _annotate(result["can_surface"]),
        "skills_only": _annotate(result["skills_only"]),
        "real_gap": _annotate(result["real_gap"]),
        "total_jd_keywords": result["total_jd_keywords"],
        "matched": result["matched"],
        "cost_usd": round(cost, 5),
        "arch": "llm" if req.use_llm else "regex",
        "ranked_projects": ranked,
        "suggested_project": suggested,
    }


# ── Routes — compile + versioning ────────────────────────────────────────────

@app.post("/api/compile")
def compile_resume(req: CompileRequest):
    version_id = _make_version_id()
    _log_version(version_id, req)

    latex_source = generate(
        req.selected_bullet_ids,
        suggested_project=req.suggested_project,
        project_order=req.project_order or None,
    )

    if req.format == "pdf":
        pdf_bytes = compile_pdf(latex_source)
        if pdf_bytes:
            return Response(
                content=pdf_bytes, media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="resume-{version_id}.pdf"',
                    "X-Version-Id": version_id,
                },
            )
        return Response(
            content=latex_source, media_type="text/plain",
            headers={
                "Content-Disposition": f'attachment; filename="resume-{version_id}.tex"',
                "X-Fallback": "pdflatex-not-found",
                "X-Version-Id": version_id,
            },
        )

    return Response(
        content=latex_source, media_type="text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="resume-{version_id}.tex"',
            "X-Version-Id": version_id,
        },
    )


@app.get("/api/resume/history")
def get_history():
    return json.loads(_HISTORY_PATH.read_text())


@app.get("/api/resume/version/{version_id}")
def get_version(version_id: str):
    history = json.loads(_HISTORY_PATH.read_text())
    entry = next((h for h in history if h["id"] == version_id), None)
    if not entry:
        raise HTTPException(404, f"Version '{version_id}' not found")
    return entry


# ── Routes — project ideas ────────────────────────────────────────────────────

@app.get("/api/project-ideas")
def get_ideas():
    return json.loads(_IDEAS_PATH.read_text())

@app.post("/api/project-ideas/save")
def save_idea(req: SaveIdeaRequest):
    ideas = json.loads(_IDEAS_PATH.read_text())
    idea = req.idea.copy()
    idea["saved_at"] = datetime.now(timezone.utc).isoformat()
    idea["jd_snippet"] = req.jd_snippet[:200]
    idea["status"] = idea.get("status", "idea")
    # Deduplicate by name
    ideas = [i for i in ideas if i.get("name") != idea.get("name")]
    ideas.append(idea)
    _IDEAS_PATH.write_text(json.dumps(ideas, indent=2))
    return {"status": "saved", "count": len(ideas)}

@app.put("/api/project-ideas/status")
def update_idea_status(req: UpdateIdeaStatusRequest):
    ideas = json.loads(_IDEAS_PATH.read_text())
    now = datetime.now(timezone.utc).isoformat()
    for idea in ideas:
        if idea.get("id") == req.idea_id or idea.get("name") == req.idea_id:
            prev = idea.get("status", "idea")
            idea["status"] = req.status
            idea["status_updated_at"] = now
            idea.setdefault("status_history", []).append({
                "from": prev, "to": req.status, "at": now,
            })
    _IDEAS_PATH.write_text(json.dumps(ideas, indent=2))
    return {"status": "updated"}

@app.delete("/api/project-ideas/{idea_name}")
def delete_idea(idea_name: str):
    ideas = json.loads(_IDEAS_PATH.read_text())
    ideas = [i for i in ideas if i.get("name") != idea_name]
    _IDEAS_PATH.write_text(json.dumps(ideas, indent=2))
    return {"status": "deleted"}


# ── Coverage map ──────────────────────────────────────────────────────────────

@app.get("/api/coverage-map")
def get_coverage_map():
    kw_module.reload()
    return kw_module.MASTER_KEYWORDS


# ── Serve frontend ────────────────────────────────────────────────────────────
_STATIC_PATH.mkdir(exist_ok=True)
app.mount("/", StaticFiles(directory=str(_STATIC_PATH), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
