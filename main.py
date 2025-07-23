import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.live import Live
from rich.tree import Tree
from rich.text import Text
from rich.align import Align
from rich import box
from pathlib import Path
import json
from collections import defaultdict
import os
import time

# built-in benchmarks
from benchmarks import (
    readability,
    maintainability,
    performance,
    testability,
    robustness,
    security,
    scalability,
    documentation,
    consistency,
    git_health,
)
from benchmarks.db import record_run
from benchmarks.stats_utils import normalize_scores_zscore, BenchmarkResult
from main_utils import _load_benchmarks, _analyze_single_codebase, _collect  # Import from new module

BUILT_IN_MODULES = [
    readability,
    maintainability,
    performance,
    testability,
    robustness,
    security,
    scalability,
    documentation,
    consistency,
    git_health,
]

BENCHMARK_FUNCS = _load_benchmarks()

# Map of benchmark name -> supported languages set (lowercase)
BENCHMARK_LANGS = {}
for mod in BUILT_IN_MODULES:
    raw_name = mod.__name__.split(".")[-1]
    display_name = raw_name.replace("_", " ").title().replace(" ", "")
    langs = getattr(mod, "SUPPORTED_LANGUAGES", {"python"})  # default python if not specified
    if langs == "any":
        langs = {"any"}
    BENCHMARK_LANGS[display_name] = {lang.lower() for lang in langs}

@app.command()
def compare_collections(
    folder1: Path = typer.Option(..., "--folder1", help="Directory containing multiple repos (collection 1)"),
    folder2: Path = typer.Option(..., "--folder2", help="Directory containing multiple repos (collection 2)"),
    skip: str = typer.Option('', "--skip", help="Comma-separated list of benchmark names to skip."),
    weights: str = typer.Option('{}', "--weights", help='JSON string to weight benchmarks.'),
):
    """Compare two *collections* of repositories (every immediate subdirectory is treated as a repo)."""
    if not folder1.is_dir() or not folder2.is_dir():
        console.print("[bold red]Error: Both folders must be valid directories.[/bold red]")
        raise typer.Exit(code=1)

    try:
        benchmark_weights = json.loads(weights)
    except json.JSONDecodeError:
        console.print("[bold red]Error: Invalid JSON format for weights.[/bold red]")
        raise typer.Exit(code=1)

    skip_set = {s.strip().capitalize() for s in skip.split(',') if s.strip()}

    total_repos = sum(1 for _ in folder1.iterdir() if _.is_dir() and not _.name.startswith('.')) + sum(1 for _ in folder2.iterdir() if _.is_dir() and not _.name.startswith('.'))
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
        transient=True
    ) as progress:
        task_id = progress.add_task("Analyzing repositories...", total=total_repos)
        avg1, n1 = _collect(folder1, progress, task_id, skip_set, benchmark_weights)
        avg2, n2 = _collect(folder2, progress, task_id, skip_set, benchmark_weights)

    console.print(Align.center("[bold blue]🔍 OpenBase Collection Analysis[/bold blue]"))
    console.print(Align.center(f"Comparing collection [magenta]{folder1.name}[/magenta] ({n1} repos) vs [green]{folder2.name}[/green] ({n2} repos)"))
    console.print()

    # Build table
    table = Table(title="📊 Collection Quality Comparison", box=box.ROUNDED)
    table.add_column("Benchmark", style="cyan")
    table.add_column("".join(["🔵 ", folder1.name]))  # Modified
    table.add_column("".join(["🟢 ", folder2.name]))  # Modified
    table.add_column("Winner")

    total1 = total2 = 0.0
    for name in sorted(set(list(avg1.keys()) + list(avg2.keys()))):
        score1 = avg1.get(name, 0.0)
        score2 = avg2.get(name, 0.0)
        weight = benchmark_weights.get(name, 1.0)
        total1 += score1 * weight
        total2 += score2 * weight
        winner = "🔵" if score1 > score2 else ("🟢" if score2 > score1 else "🤝")
        table.add_row(name, f"{score1:.2f}", f"{score2:.2f}", winner)

    table.add_row("", "", "", "")
    table.add_row("TOTAL", f"{total1:.2f}", f"{total2:.2f}", "🔵" if total1 > total2 else ("🟢" if total2 > total1 else "🤝"))
    console.print(table)

@app.command()
def compare(
    codebase1: Path = typer.Option(..., "--codebase1", "-c1", help="Path to the first codebase."),
    codebase2: Path = typer.Option(..., "--codebase2", "-c2", help="Path to the second codebase."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output with details for each benchmark."),
    weights: str = typer.Option('{}', "--weights", "-w", help='JSON string to weight benchmarks. e.g., \'{"Readability": 1.2, "Security": 0.8}\''),
    skip: str = typer.Option('', "--skip", help="Comma-separated list of benchmark names to skip."),
    export: Path = typer.Option(None, "--export", help="Path to write JSON export of results."),
    profile: Path = typer.Option(None, "--profile", help="Python script to execute for runtime profiling (pyinstrument)"),
):
    if not codebase1.is_dir() or not codebase2.is_dir():
        console.print("[bold red]Error: Both codebases must be valid directories.[/bold red]")
        raise typer.Exit(code=1)

    try:
        benchmark_weights = json.loads(weights)
    except json.JSONDecodeError:
        console.print("[bold red]Error: Invalid JSON format for weights.[/bold red]")
        raise typer.Exit(code=1)

    skip_set = {s.strip().capitalize() for s in skip.split(',') if s.strip()}

    if profile:
        os.environ["BENCH_PROFILE_SCRIPT"] = str(profile)

    welcome_text = Text.assemble(
        ("🔍 OpenBase", "bold blue"),
        (" - Professional Codebase Quality Analysis", "bold white")
    )
    console.print(Align.center(welcome_text))
    console.print(Align.center(f"Comparing [magenta]{codebase1.name}[/magenta] vs [green]{codebase2.name}[/green]"))
    console.print()

    from benchmarks.language_utils import detect_languages
    langs1 = detect_languages(codebase1)
    langs2 = detect_languages(codebase2)

    benchmarks_to_run = []
    for name, func in BENCHMARK_FUNCS.items():
        if name in skip_set:
            continue
        supported = BENCHMARK_LANGS.get(name, {"any"})
        if "any" in supported or (langs1 & supported) or (langs2 & supported):
            benchmarks_to_run.append((name, func))

    raw_scores1, raw_scores2 = {}, {}
    details1, details2 = {}, {}
    raw_metrics1, raw_metrics2 = {}, {}
    result_objects1, result_objects2 = {}, {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
        transient=True
    ) as progress:
        
        main_task = progress.add_task("Running quality analysis...", total=len(benchmarks_to_run))
        
        for name, func in benchmarks_to_run:
            progress.update(main_task, description=f"Analyzing {name.lower()}...")
            
            weight = benchmark_weights.get(name, 1.0)
            
            result1 = func(str(codebase1))
            result2 = func(str(codebase2))
            
            if isinstance(result1, BenchmarkResult):
                score1, detail1 = result1.score, result1.details
                raw_metrics1[name] = result1.raw_metrics
            else:
                score1, detail1 = result1
                raw_metrics1[name] = {}
                
            if isinstance(result2, BenchmarkResult):
                score2, detail2 = result2.score, result2.details
                raw_metrics2[name] = result2.raw_metrics
            else:
                score2, detail2 = result2
                raw_metrics2[name] = {}
            
            result_objects1[name] = result1
            result_objects2[name] = result2

            raw_scores1[name] = score1
            raw_scores2[name] = score2

            details1[name] = detail1
            details2[name] = detail2
            
            progress.advance(main_task)
            time.sleep(0.1)
    
    console.print("✅ Analysis complete!\n")
    
    if all(score == 0.0 for score in raw_scores1.values()):
        console.print(f"[yellow]Warning: {codebase1.name} appears to be empty or has no analyzable code.[/yellow]")
    if all(score == 0.0 for score in raw_scores2.values()):
        console.print(f"[yellow]Warning: {codebase2.name} appears to be empty or has no analyzable code.[/yellow]")
    
    normalized_scores1 = normalize_scores_zscore(raw_scores1)
    normalized_scores2 = normalize_scores_zscore(raw_scores2)
    
    table = Table(
        title="📊 Codebase Quality Comparison Results",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold white on blue"
    )
    table.add_column("Benchmark", justify="right", style="cyan", no_wrap=True)
    table.add_column("".join(["🔵 ", codebase1.name]))  # Modified
    table.add_column("".join(["🟢 ", codebase2.name]))  # Modified
    table.add_column("Winner", justify="center", style="bold yellow")
    
    total_score1, total_score2 = 0, 0
    for name, _ in benchmarks_to_run:
        weight = benchmark_weights.get(name, 1.0)
        weighted_score1 = normalized_scores1[name] * weight
        weighted_score2 = normalized_scores2[name] * weight
        
        total_score1 += weighted_score1
        total_score2 += weighted_score2

        result1 = result_objects1[name]
        result2 = result_objects2[name]
        
        if isinstance(result1, BenchmarkResult):
            score1_display = result1.format_score_with_ci()
        else:
            score1_display = f"{weighted_score1:.2f}"
            
        if isinstance(result2, BenchmarkResult):
            score2_display = result2.format_score_with_ci()
        else:
            score2_display = f"{weighted_score2:.2f}"
        
        if weight != 1.0:
            score1_display += f" (x{weight})"
            score2_display += f" (x{weight})"
        
        winner = "🔵" if weighted_score1 > weighted_score2 else ("🟢" if weighted_score2 > weighted_score1 else "🤝")
            
        table.add_row(name, score1_display, score2_display, winner)
    
    table.add_row("", "", "", "")
    
    if total_score1 > total_score2:
        overall_winner = "🔵 " + codebase1.name
        winner_style = "bold magenta"
    elif total_score2 > total_score1:
        overall_winner = "🟢 " + codebase2.name
        winner_style = "bold green"
    else:
        overall_winner = "🤝 Tie"
        winner_style = "bold yellow"
    
    table.add_row(
        "[bold]TOTAL SCORE[/bold]", 
        f"[bold magenta]{total_score1:.2f}[/bold magenta]", 
        f"[bold green]{total_score2:.2f}[/bold green]",
        f"[{winner_style}]{overall_winner}[/{winner_style}]"
    )
    
    console.print(table)
    
    score_diff = abs(total_score1 - total_score2)
    if score_diff > 10:
        assessment = "significantly better"
    elif score_diff > 5:
        assessment = "moderately better"
    elif score_diff > 2:
        assessment = "slightly better"
    else:
        assessment = "very similar to"
    
    summary_text = f"[bold]{overall_winner.split(' ', 1)[1] if ' ' in overall_winner else overall_winner}[/bold] is [bold]{assessment}[/bold] than the other codebase."
    summary_panel = Panel(
        summary_text,
        title="🎯 Summary",
        border_style="blue",
        padding=(1, 2)
    )
    console.print(summary_panel)

    enhanced_results = {
        "details1": details1, 
        "details2": details2,
        "raw_metrics1": raw_metrics1,
        "raw_metrics2": raw_metrics2,
        "raw_scores1": raw_scores1,
        "raw_scores2": raw_scores2,
        "normalized_scores1": normalized_scores1,
        "normalized_scores2": normalized_scores2
    }
    record_run(str(codebase1), str(codebase2), total_score1, total_score2, enhanced_results)

    if export:
        export_data = {
            "codebase1": str(codebase1),
            "codebase2": str(codebase2),
            "total_score1": total_score1,
            "total_score2": total_score2,
            **enhanced_results
        }
        os.makedirs(export.parent, exist_ok=True)
        export.write_text(json.dumps(export_data, indent=2))
        console.print(f"[green]Exported results to {export}")

    if verbose:
        console.print("\n" + "="*60)
        console.print(Align.center(Text("📋 Detailed Analysis Report", style="bold white on blue")))
        console.print("="*60)
        
        for name, _ in benchmarks_to_run:
            console.print(f"\n[bold cyan]🔍 {name} Analysis[/bold cyan]")
            
            tree = Tree(f"[bold]{name}[/bold]")
            
            cb1_branch = tree.add(f"[magenta]🔵 {codebase1.name}[/magenta] - Score: [bold]{normalized_scores1[name]:.2f}[/bold]")
            details1_content = details1[name] if details1[name] else ["✅ No issues found."]
            for detail in details1_content[:5]:
                cb1_branch.add(f"• {detail}")
            if len(details1_content) > 5:
                cb1_branch.add(f"[dim]... and {len(details1_content) - 5} more items[/dim]")
            
            cb2_branch = tree.add(f"[green]🟢 {codebase2.name}[/green] - Score: [bold]{normalized_scores2[name]:.2f}[/bold]")
            details2_content = details2[name] if details2[name] else ["✅ No issues found."]
            for detail in details2_content[:5]:
                cb2_branch.add(f"• {detail}")
            if len(details2_content) > 5:
                cb2_branch.add(f"[dim]... and {len(details2_content) - 5} more items[/dim]")
            
            console.print(tree)
            
            score1, score2 = normalized_scores1[name], normalized_scores2[name]
            if abs(score1 - score2) < 0.5:
                interpretation = "📊 Both codebases perform similarly in this area."
            elif score1 > score2:
                interpretation = f"📈 {codebase1.name} outperforms {codebase2.name} by {score1-score2:.1f} points."
            else:
                interpretation = f"📈 {codebase2.name} outperforms {codebase1.name} by {score2-score1:.1f} points."
            
            console.print(f"[dim]{interpretation}[/dim]")
            console.print()

if __name__ == "__main__":
    app()