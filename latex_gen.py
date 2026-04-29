"""
Patches Rajat_Ref_Resume.tex:
  - Work experience: marker-based (%%BULLETS:id%% / %%END:id%%)
  - Projects: fully dynamic via %%PROJECTS_BLOCK%%
  - Suggested project (ephemeral): appended to projects block if provided
"""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

_TEMPLATE = Path(__file__).parent / "Rajat_Ref_Resume.tex"
_DATA_PATH = Path(__file__).parent / "source_truth.json"


def _esc(text: str) -> str:
    """Minimal LaTeX escaping for plain-text fields (not bullets, which have their own latex field)."""
    return (text
        .replace("&", r"\&")
        .replace("%", r"\%")
        .replace("#", r"\#")
        .replace("–", "--")
        .replace("—", "---"))


def _build_links(links: dict) -> str:
    parts = []
    if links.get("live"):
        parts.append(f"\\href{{{links['live']}}}{{[\\textcolor{{blue}}{{Live}}]}}")
    if links.get("demo"):
        parts.append(f"\\href{{{links['demo']}}}{{[\\textcolor{{blue}}{{Demo}}]}}")
    if links.get("github"):
        parts.append(f"\\href{{{links['github']}}}{{[\\textcolor{{blue}}{{GitHub}}]}}")
    return "\n   ".join(parts)


def _project_block(proj: dict, selected: set) -> str:
    """Generate LaTeX for one project using only selected bullets."""
    bullets = [b for b in proj.get("bullets", []) if b["id"] in selected]
    if not bullets:
        return ""
    name = _esc(proj["name"])
    links_str = _build_links(proj.get("links", {}))
    links_arg = "{" + links_str + "}" if links_str else "{}"
    tex = f"\\projectentry\n  {{{name}}}\n  {{}}\n  {{}}\n  {links_arg}\n"
    tex += "\\begin{myitemize}\n"
    for b in bullets:
        tex += f"  \\item {b.get('latex', b['text'])}\n"
    tex += "\\end{myitemize}\n\n"
    return tex


def _suggested_block(proj: dict, selected: set) -> str:
    """Generate LaTeX for a suggested (ephemeral) project."""
    bullets = [b for b in proj.get("bullets", []) if b["id"] in selected]
    if not bullets:
        return ""
    name = _esc(proj.get("name", "New Project"))
    links_str = _build_links(proj.get("links", {}))
    links_arg = "{" + links_str + "}" if links_str else "{}"
    tex = f"\\projectentry\n  {{{name}}}\n  {{}}\n  {{}}\n  {links_arg}\n"
    tex += "\\begin{myitemize}\n"
    for b in bullets:
        tex += f"  \\item {b.get('latex', b.get('text', ''))}\n"
    tex += "\\end{myitemize}\n\n"
    return tex


def _personal_header(personal: dict) -> str:
    name     = _esc(personal.get("name", ""))
    location = _esc(personal.get("location", ""))
    phone    = _esc(personal.get("phone", ""))
    email    = personal.get("email", "")
    linkedin = personal.get("linkedin", "")
    github   = personal.get("github", "")
    note     = _esc(personal.get("note", ""))
    li_url   = linkedin if linkedin.startswith("http") else f"https://{linkedin}"
    gh_url   = github   if github.startswith("http")   else f"https://{github}"
    return (
        f"\\begin{{center}}\n"
        f"  \\textbf{{\\LARGE {name}}} \\\\[0.4em]\n"
        f"  \\small\n"
        f"  {location} \\textbar{{}}\n"
        f"  {phone} \\textbar{{}}\n"
        f"  \\href{{mailto:{email}}}{{{_esc(email)}}} \\textbar{{}}\n"
        f"  \\href{{{li_url}}}{{{_esc(linkedin)}}} \\textbar{{}}\n"
        f"  \\href{{{gh_url}}}{{{_esc(github)}}}\\\\[0.3em]\n"
        f"  \\vspace{{-0.5em}}\\rule{{0.7\\linewidth}}{{0.2pt}}\\\\[0.2em]\n"
        f"  {note}\n"
        f"\\end{{center}}"
    )


def _education_block(education: list) -> str:
    tex = ""
    for edu in education:
        school  = _esc(edu.get("school", ""))
        gpa     = _esc(edu.get("gpa", ""))
        loc     = _esc(edu.get("location", ""))
        degree  = _esc(edu.get("degree", ""))
        period  = _esc(edu.get("period", ""))
        tex += f"\\eduentry\n  {{{school}}}\n  {{{gpa}}}\n  {{{loc}}}\n  {{{degree}}}\n  {{{period}}}\n"
    return tex.rstrip()


def generate(
    selected_bullet_ids: list[str],
    suggested_project: dict | None = None,
    project_order: list[str] | None = None,
) -> str:
    """
    Return patched LaTeX source.
    project_order: list of project IDs in desired order (e.g. ranked by JD score).
                   Defaults to source_truth order.
    suggested_project: ephemeral LLM-suggested project dict, included if any of
                       its bullet IDs are in selected_bullet_ids.
    """
    selected = set(selected_bullet_ids)
    data = json.loads(_DATA_PATH.read_text())
    template = _TEMPLATE.read_text()

    # ── 1. Patch work experience (marker-based) ────────────────────────────────
    marker_re = re.compile(
        r"%%BULLETS:(?P<id>[^%\n]+)%%\n(?P<block>.*?)%%END:(?P=id)%%",
        re.DOTALL,
    )

    def _patch_work(m: re.Match) -> str:
        sid = m.group("id")
        role = next((r for r in data.get("work_experience", []) if r["id"] == sid), None)
        if not role:
            return m.group(0)
        bullets = [b for b in role["bullets"] if b["id"] in selected]
        items = "\n".join(f"  \\item {b.get('latex', b['text'])}" for b in bullets) if bullets else "  % (none selected)"
        return f"%%BULLETS:{sid}%%\n\\begin{{myitemize}}\n{items}\n\\end{{myitemize}}\n%%END:{sid}%%"

    patched = marker_re.sub(_patch_work, template)

    # ── 2. Generate projects block ─────────────────────────────────────────────
    all_projects = {p["id"]: p for p in data.get("projects", [])}
    order = project_order if project_order else [p["id"] for p in data.get("projects", [])]

    projects_tex = ""
    for pid in order:
        proj = all_projects.get(pid)
        if proj:
            projects_tex += _project_block(proj, selected)

    # Append suggested project if any of its bullets are selected
    if suggested_project:
        sug_bullets = [b for b in suggested_project.get("bullets", []) if b["id"] in selected]
        if sug_bullets:
            projects_tex += _suggested_block(suggested_project, selected)

    patched = patched.replace("%%PROJECTS_BLOCK%%", projects_tex.rstrip())

    # ── 3. Patch skills from source_truth ─────────────────────────────────────
    skills = data.get("skills", {})
    skill_lines = {
        "Languages":      ", ".join(s for s in skills.get("languages", [])),
        "Frameworks":     ", ".join(s for s in skills.get("frameworks", [])),
        "Databases":      ", ".join(s for s in skills.get("databases", [])),
        "Infrastructure": ", ".join(s for s in skills.get("infrastructure", [])),
        "Other":          ", ".join(s for s in skills.get("other", [])),
    }
    for label, val in skill_lines.items():
        # Replace the specific skills line in the template
        patched = re.sub(
            rf"\\noindent\\textbf{{{label}:}}[^\n]*",
            f"\\\\noindent\\\\textbf{{{label}:}} {_esc(val)}",
            patched,
        )

    # ── 4. Patch personal header ───────────────────────────────────────────────
    patched = patched.replace("%%PERSONAL_HEADER%%", _personal_header(data.get("personal", {})))

    # ── 5. Patch education block ───────────────────────────────────────────────
    patched = patched.replace("%%EDUCATION_BLOCK%%", _education_block(data.get("education", [])))

    return patched


def compile_pdf(latex_source: str) -> bytes | None:
    try:
        result = subprocess.run(["which", "pdflatex"], capture_output=True)
        if result.returncode != 0:
            return None
    except Exception:
        return None

    with tempfile.TemporaryDirectory() as tmp:
        tex = os.path.join(tmp, "resume.tex")
        pdf = os.path.join(tmp, "resume.pdf")
        with open(tex, "w") as f:
            f.write(latex_source)
        for _ in range(2):
            subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-output-directory", tmp, tex],
                capture_output=True, cwd=tmp,
            )
        if os.path.exists(pdf):
            return Path(pdf).read_bytes()
    return None
