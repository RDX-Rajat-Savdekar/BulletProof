"""
Benchmark runner — runs Arch A and Arch B against a JD, prints side-by-side comparison.

Usage:
    python benchmark.py <jd_file_or_fixture_name>
    python benchmark.py fixtures/startup_fullstack.txt
    python benchmark.py fixtures/faang_backend.txt
    echo "paste JD here" | python benchmark.py -

Fixture names: faang_backend, startup_fullstack, ml_adjacent, enterprise_java, synonym_heavy
"""

import sys
import os
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
import arch_a
import arch_b
from diff import analyze

console = Console()

FIXTURE_DIR = Path(__file__).parent / "fixtures"

FIXTURE_ALIASES = {
    "faang_backend":     "faang_backend.txt",
    "startup_fullstack": "startup_fullstack.txt",
    "ml_adjacent":       "ml_adjacent.txt",
    "enterprise_java":   "enterprise_java.txt",
    "synonym_heavy":     "synonym_heavy.txt",
}


def load_jd(arg: str) -> tuple[str, str]:
    if arg == "-":
        return sys.stdin.read(), "stdin"
    if arg in FIXTURE_ALIASES:
        path = FIXTURE_DIR / FIXTURE_ALIASES[arg]
        return path.read_text(), arg
    path = Path(arg)
    return path.read_text(), path.stem


def run_both(jd_text: str, name: str):
    console.rule(f"[bold cyan]Benchmark: {name}")

    # --- Arch A ---
    console.print("\n[yellow]Running Arch A (deterministic regex)...[/]")
    a_keywords, a_time = arch_a.extract(jd_text)
    a_result = analyze(a_keywords)

    # --- Arch B ---
    console.print("[yellow]Running Arch B (Claude Haiku, temp=0)...[/]")
    b_keywords, b_time, b_cost = arch_b.extract(jd_text)
    b_result = analyze(b_keywords)

    # --- Side-by-side metrics ---
    metrics = Table(box=box.ROUNDED, title="Metrics", show_header=True)
    metrics.add_column("Metric", style="bold")
    metrics.add_column("Arch A (regex)", style="cyan")
    metrics.add_column("Arch B (LLM)", style="green")

    metrics.add_row("Keywords extracted", str(a_result["total_jd_keywords"]), str(b_result["total_jd_keywords"]))
    metrics.add_row("Covered (bullet)", str(len(a_result["covered"])), str(len(b_result["covered"])))
    metrics.add_row("Can surface (implicit)", str(len(a_result["can_surface"])), str(len(b_result["can_surface"])))
    metrics.add_row("Skills only", str(len(a_result["skills_only"])), str(len(b_result["skills_only"])))
    metrics.add_row("Real gaps", str(len(a_result["real_gap"])), str(len(b_result["real_gap"])))
    metrics.add_row("Coverage %", f"{a_result['coverage_pct']}%", f"{b_result['coverage_pct']}%")
    metrics.add_row("HH ratio", a_result["hh_ratio"], b_result["hh_ratio"])
    metrics.add_row("Grade", a_result["grade"], b_result["grade"])
    metrics.add_row("Apply?", "✓" if a_result["apply_recommended"] else "✗", "✓" if b_result["apply_recommended"] else "✗")
    metrics.add_row("Time", f"{a_time*1000:.0f}ms", f"{b_time*1000:.0f}ms")
    metrics.add_row("Cost", "$0.000", f"${b_cost:.5f}")

    console.print(metrics)

    # --- Keywords only in B (things regex missed) ---
    a_set = set(a_keywords)
    b_set = set(b_keywords)
    missed_by_a = sorted(b_set - a_set)
    missed_by_b = sorted(a_set - b_set)

    if missed_by_a:
        console.print(Panel(
            "\n".join(f"  [red]+ {k}[/]" for k in missed_by_a),
            title="[bold red]Arch A missed these (LLM found them)",
            border_style="red"
        ))
    if missed_by_b:
        console.print(Panel(
            "\n".join(f"  [cyan]+ {k}[/]" for k in missed_by_b),
            title="[bold cyan]Arch B missed these (regex found them)",
            border_style="cyan"
        ))

    # --- Gap detail for Arch B (the one we're likely using) ---
    if b_result["real_gap"]:
        console.print(Panel(
            "\n".join(f"  [red]✗ {k}[/]" for k in b_result["real_gap"]),
            title="[bold]Real gaps (Arch B) — not in resume",
            border_style="red"
        ))
    if b_result["can_surface"]:
        console.print(Panel(
            "\n".join(f"  [yellow]~ {k}[/]" for k in b_result["can_surface"]),
            title="[bold]Can surface (Arch B) — implied but not written",
            border_style="yellow"
        ))
    if b_result["skills_only"]:
        console.print(Panel(
            "\n".join(f"  [blue]• {k}[/]" for k in b_result["skills_only"]),
            title="[bold]Skills-only (Arch B) — needs a backing bullet",
            border_style="blue"
        ))

    console.rule()
    return {
        "name": name,
        "arch_a": {"keywords": len(a_keywords), "coverage": a_result["coverage_pct"], "grade": a_result["grade"], "time_ms": round(a_time * 1000)},
        "arch_b": {"keywords": len(b_keywords), "coverage": b_result["coverage_pct"], "grade": b_result["grade"], "time_ms": round(b_time * 1000), "cost_usd": round(b_cost, 5)},
        "a_missed": missed_by_a,
        "b_missed": missed_by_b,
    }


def run_all_fixtures():
    results = []
    for alias in FIXTURE_ALIASES:
        path = FIXTURE_DIR / FIXTURE_ALIASES[alias]
        if not path.exists():
            console.print(f"[dim]Skipping {alias} — fixture not found[/]")
            continue
        jd_text, name = load_jd(alias)
        r = run_both(jd_text, name)
        results.append(r)

    # Summary table
    summary = Table(box=box.SIMPLE_HEAVY, title="\nSummary Across All Fixtures", show_header=True)
    summary.add_column("JD")
    summary.add_column("A keywords", justify="right")
    summary.add_column("B keywords", justify="right")
    summary.add_column("A grade")
    summary.add_column("B grade")
    summary.add_column("A missed by regex")
    summary.add_column("B cost")

    for r in results:
        summary.add_row(
            r["name"],
            str(r["arch_a"]["keywords"]),
            str(r["arch_b"]["keywords"]),
            r["arch_a"]["grade"],
            r["arch_b"]["grade"],
            str(len(r["a_missed"])),
            f"${r['arch_b']['cost_usd']:.5f}",
        )

    console.print(summary)

    total_cost = sum(r["arch_b"]["cost_usd"] for r in results)
    daily_cost_15 = total_cost / len(results) * 15 if results else 0
    console.print(f"\n[bold green]Estimated daily cost @ 15 apps/day: ${daily_cost_15:.4f}[/]")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "all":
        run_all_fixtures()
    else:
        jd_text, name = load_jd(sys.argv[1])
        run_both(jd_text, name)
