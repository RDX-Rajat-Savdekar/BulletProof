"""Quick runner — Arch A only, no API key needed."""
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich import box
import arch_a
from diff import analyze

console = Console()
FIXTURE_DIR = Path(__file__).parent / "fixtures"
FIXTURES = ["faang_backend", "startup_fullstack", "ml_adjacent", "enterprise_java", "synonym_heavy"]

summary = Table(box=box.ROUNDED, title="Arch A — All Fixtures")
summary.add_column("JD")
summary.add_column("Extracted", justify="right")
summary.add_column("Covered", justify="right")
summary.add_column("Can Surface", justify="right")
summary.add_column("Skills Only", justify="right")
summary.add_column("Real Gaps", justify="right")
summary.add_column("Coverage %", justify="right")
summary.add_column("Grade")
summary.add_column("Apply?")
summary.add_column("Time")

for name in FIXTURES:
    path = FIXTURE_DIR / f"{name}.txt"
    jd = path.read_text()
    kw, t = arch_a.extract(jd)
    r = analyze(kw)
    summary.add_row(
        name,
        str(r["total_jd_keywords"]),
        str(len(r["covered"])),
        str(len(r["can_surface"])),
        str(len(r["skills_only"])),
        str(len(r["real_gap"])),
        f"{r['coverage_pct']}%",
        r["grade"],
        "✓" if r["apply_recommended"] else "✗",
        f"{t*1000:.0f}ms",
    )
    console.print(f"\n[bold]{name}[/] — gaps: {', '.join(r['real_gap']) or 'none'}")

console.print(summary)
