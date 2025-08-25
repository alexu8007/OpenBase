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
from datetime import datetime
import re

from dotenv import load_dotenv

from llm_tools import perfect_code_with_model

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

app = typer.Typer(context_settings={"help_option_names": ["-h", "--help"]})
console = Console()

# Dynamically collect benchmarks
def _load_benchmarks():
    mapping = {}
    for mod in BUILT_IN_MODULES:
        raw_name = mod.__name__.split(".")[-1]
        display_name = raw_name.replace("_", " ").title().replace(" ", "")  # e.g., git_health -> GitHealth
        func_name = f"assess_{raw_name}"
        if not hasattr(mod, func_name):
            # try camel variant (legacy)
            func_name_alt = func_name.replace("_", "")
            if hasattr(mod, func_name_alt):
                func_name = func_name_alt
        mapping[display_name] = getattr(mod, func_name)
    return mapping

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


def _list_immediate_repo_dirs(folder: Path):
    """Return a list of immediate subdirectories for a folder, excluding hidden ones.

    Any errors while listing are reported to the console and an empty list is returned.
    """
    try:
        return [entry for entry in folder.iterdir() if entry.is_dir() and not entry.name.startswith('.')]
    except (OSError, PermissionError) as exc:
        console.print(f"[yellow]Could not list directory {folder}: {exc}[/yellow]")
        return []


def _analyze_single_codebase(path: Path, skip_set, benchmark_weights):
    """Run benchmarks on a single codebase directory and return raw score dict."""
    from benchmarks.language_utils import detect_languages
    langs = detect_languages(path)
    raw_scores = {}

    for name, func in BENCHMARK_FUNCS.items():
        if name in skip_set:
            continue
        supported = BENCHMARK_LANGS.get(name, {"any"})
        if "any" not in supported and not (langs & supported):
            continue
        result = func(str(path))
        if isinstance(result, BenchmarkResult):
            raw_scores[name] = result.score
        else:
            raw_scores[name] = result[0] if isinstance(result, tuple) else result
    return raw_scores


def _slugify(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in value).strip("-")


def _copy_tests_for_file(src_file: Path, dest_dir: Path) -> None:
    """Best-effort copy of co-located tests for a given file into dest_dir/tests.

    Looks for siblings matching test_*.py or *_test.py and a `tests` directory in the same tree level.
    Errors encountered while reading/writing individual test files are reported but do not raise.
    """
    tests_dir = dest_dir / "tests"
    try:
        tests_dir.mkdir(parents=True, exist_ok=True)
    except (OSError, PermissionError) as exc:
        console.print(f"[yellow]Could not create tests directory {tests_dir}: {exc}[/yellow]")
        return

    parent = src_file.parent
    # Copy sibling tests matching patterns
    for cand in parent.glob("test_*.py"):
        try:
            content = cand.read_text()
            (tests_dir / cand.name).write_text(content)
        except (OSError, UnicodeDecodeError) as exc:
            console.print(f"[yellow]Failed to copy test file {cand} -> {tests_dir}: {exc}[/yellow]")

    for cand in parent.glob("*_test.py"):
        try:
            content = cand.read_text()
            (tests_dir / cand.name).write_text(content)
        except (OSError, UnicodeDecodeError) as exc:
            console.print(f"[yellow]Failed to copy test file {cand} -> {tests_dir}: {exc}[/yellow]")

    # If there's an immediate `tests` folder next to the file, copy its simple tests
    neighbor_tests = parent / "tests"
    if neighbor_tests.is_dir():
        for cand in neighbor_tests.rglob("*.py"):
            rel = cand.relative_to(neighbor_tests)
            out_path = tests_dir / rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                out_path.write_text(cand.read_text())
            except (OSError, UnicodeDecodeError) as exc:
                console.print(f"[yellow]Failed to copy nested test file {cand} -> {out_path}: {exc}[/yellow]")


def _is_valid_model_id(model: str) -> bool:
    """Validate model id contains only expected characters (alphanumeric, dot, dash, underscore, slash)."""
    if not isinstance(model, str) or not model.strip():
        return False
    # allow org/model or provider/name formats with limited set of chars
    return re.match(r'^[A-Za-z0-9._\-/]+$', model) is not None


@app.command()
def compare_collections(
    folder1: Path = typer.Option(..., "--folder1", help="Directory containing multiple repos (collection 1)"),
    folder2: Path = typer.Option(..., "--folder2", help="Directory containing multiple repos (collection 2)"),
    skip: str = typer.Option('', "--skip", help="Comma-separated list of benchmark names to skip."),
    weights: str = typer.Option('{}', "--weights", help='JSON string to weight benchmarks.'),
):
    """Compare two collections of repositories. Every immediate subdirectory is treated as a repository.

    This command computes per-benchmark averages across all repos in each collection and displays a comparison table.
    """
    if not folder1.is_dir() or not folder2.is_dir():
        console.print("[bold red]Error: Both folders must be valid directories.[/bold red]")
        raise typer.Exit(code=1)

    try:
        benchmark_weights = json.loads(weights)
    except json.JSONDecodeError:
        console.print("[bold red]Error: Invalid JSON format for weights.[/bold red]")
        raise typer.Exit(code=1)

    # Ensure weights values are numeric
    if isinstance(benchmark_weights, dict):
        sanitized_weights = {}
        for k, v in benchmark_weights.items():
            try:
                sanitized_weights[k] = float(v)
            except (TypeError, ValueError):
                console.print(f"[yellow]Warning: Invalid weight for '{k}' -> {v}. Defaulting to 1.0[/yellow]")
                sanitized_weights[k] = 1.0
        benchmark_weights = sanitized_weights
    else:
        console.print("[yellow]Warning: Weights should be a JSON object. Ignoring weights.[/yellow]")
        benchmark_weights = {}

    # Normalize skip tokens to internal benchmark display names (e.g., git_health -> GitHealth)
    def _to_display(name: str) -> str:
        return name.replace('_', ' ').title().replace(' ', '')
    skip_set = {_to_display(s.strip()) for s in skip.split(',') if s.strip()}

    def _collect(folder, progress, task_id):
        # List immediate repo directories and aggregate benchmark scores
        repo_dirs = _list_immediate_repo_dirs(folder)
        aggregate: defaultdict[str, list] = defaultdict(list)
        for repo in repo_dirs:
            # Update progress bar description for clarity
            progress.update(task_id, description=f"{folder.name}/{repo.name}")
            raw_scores = _analyze_single_codebase(repo, skip_set, benchmark_weights)
            for benchmark_name, score in raw_scores.items():
                aggregate[benchmark_name].append(score)
            progress.advance(task_id)
        avg_scores = {k: (sum(scores)/len(scores) if scores else 0.0) for k, scores in aggregate.items()}
        return avg_scores, len(repo_dirs)

    total_repos = len(_list_immediate_repo_dirs(folder1)) + len(_list_immediate_repo_dirs(folder2))
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
        avg1, n1 = _collect(folder1, progress, task_id)
        avg2, n2 = _collect(folder2, progress, task_id)

    console.print(Align.center("[bold blue]🔍 OpenBase Collection Analysis[/bold blue]"))
    console.print(Align.center(f"Comparing collection [magenta]{folder1.name}[/magenta] ({n1} repos) vs [green]{folder2.name}[/green] ({n2} repos)"))
    console.print()

    # Build comparison table
    table = Table(title="📊 Collection Quality Comparison", box=box.ROUNDED)
    table.add_column("Benchmark", style="cyan")
    table.add_column(f"🔵 {folder1.name}")
    table.add_column(f"🟢 {folder2.name}")
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
def llm_battle(
    config: Path = typer.Option(Path("openbase.config.json"), "--config", help="Path to openbase.config.json"),
):
    """Run an LLM vs LLM refactor 'battle' using a config file that specifies models and a benchmark folder.

    The command generates improved versions of files for each model, scores them with benchmarks, and reports a comparison.
    """
    load_dotenv()

    repo_root = Path(__file__).resolve().parent
    config_path = config if config else (repo_root / "openbase.config.json")
    if not config_path.exists():
        console.print("[bold red]Missing openbase.config.json at repo root.[/bold red]")
        console.print("Example:\n" + json.dumps({
            "models": ["x-ai/grok-2", "google/gemini-1.5-pro-latest"],
            "benchmark_folder": "benchmarkv01",
            "out_dir": "/runs",
            "skip": "GitHealth,Testability"
        }, indent=2))
        raise typer.Exit(code=1)

    try:
        cfg_text = config_path.read_text(encoding="utf-8")
    except (OSError, PermissionError) as exc:
        console.print(f"[bold red]Could not read config file {config_path}: {exc}[/bold red]")
        raise typer.Exit(code=1)

    try:
        cfg = json.loads(cfg_text)
    except json.JSONDecodeError:
        console.print("[bold red]Invalid JSON in openbase.config.json[/bold red]")
        raise typer.Exit(code=1)

    models_val = cfg.get("models") or cfg.get("model")
    if isinstance(models_val, str):
        model_ids = [m.strip() for m in models_val.split(",") if m.strip()]
    elif isinstance(models_val, list):
        model_ids = [str(m).strip() for m in models_val if str(m).strip()]
    else:
        model_ids = []
    if len(model_ids) != 2:
        console.print("[bold red]openbase.config.json must specify exactly 2 models under 'models'.[/bold red]")
        raise typer.Exit(code=1)

    # Validate model ids for safety
    for mid in model_ids:
        if not _is_valid_model_id(mid):
            console.print(f"[bold red]Invalid model id provided: '{mid}'. Allowed characters: letters, numbers, '.', '-', '_', '/'[/bold red]")
            raise typer.Exit(code=1)

    bench_folder = cfg.get("benchmark_folder", "benchmarkv01")
    target_dir = (repo_root / bench_folder).resolve()
    if not target_dir.is_dir():
        console.print(f"[bold red]Benchmark folder not found:[/bold red] {target_dir}")
        raise typer.Exit(code=1)

    # Collect all files in the folder (recursive)
    file_paths = [p for p in target_dir.rglob("*") if p.is_file()]
    if not file_paths:
        console.print(f"[bold red]No files found in {target_dir}[/bold red]")
        raise typer.Exit(code=1)

    # Output directory handling (default to /runs)
    configured_out = Path(cfg.get("out_dir", "/runs"))
    out_dir = configured_out
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except (PermissionError, OSError) as e:
        out_dir = repo_root / "runs"
        out_dir.mkdir(parents=True, exist_ok=True)
        console.print(f"[yellow]Could not write to {configured_out} ({e}). Falling back to {out_dir}[/yellow]")

    # Skip and weights
    skip = str(cfg.get("skip", "GitHealth,Testability"))
    def _to_display(name: str) -> str:
        return name.replace('_', ' ').title().replace(' ', '')
    skip_set = {_to_display(s.strip()) for s in skip.split(',') if s.strip()}

    weights_val = cfg.get("weights", {})
    if isinstance(weights_val, str):
        try:
            benchmark_weights = json.loads(weights_val)
        except json.JSONDecodeError:
            benchmark_weights = {}
    elif isinstance(weights_val, dict):
        benchmark_weights = weights_val
    else:
        benchmark_weights = {}

    # Ensure weights values are numeric
    if isinstance(benchmark_weights, dict):
        sanitized_weights = {}
        for k, v in benchmark_weights.items():
            try:
                sanitized_weights[k] = float(v)
            except (TypeError, ValueError):
                console.print(f"[yellow]Warning: Invalid weight for '{k}' -> {v}. Defaulting to 1.0[/yellow]")
                sanitized_weights[k] = 1.0
        benchmark_weights = sanitized_weights
    else:
        benchmark_weights = {}

    extra_instructions_path = cfg.get("extra_instructions")
    extra_text = None
    if extra_instructions_path:
        p = Path(extra_instructions_path)
        if p.exists():
            try:
                extra_text = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                console.print(f"[yellow]Could not read extra_instructions file {p}: {exc}[/yellow]")

    copy_tests = bool(cfg.get("copy_tests", True))

    # Prepare run directories
    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_root = out_dir / "llm_battle" / run_id
    model_dirs = {}
    for model in model_ids:
        mslug = _slugify(model)
        model_dir = run_root / mslug
        model_dir.mkdir(parents=True, exist_ok=True)
        model_dirs[model] = model_dir

    # Run refactors (temperature fixed to 0)
    console.print(Align.center("[bold blue]🤖 Running LLM refactors[/bold blue]"))
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Generating improved files...", total=len(file_paths) * len(model_ids))

        for file_path in file_paths:
            try:
                original_code = file_path.read_text(encoding="utf-8", errors="ignore")
            except (OSError, UnicodeDecodeError) as exc:
                console.print(f"[yellow]Could not read file {file_path}: {exc}[/yellow]")
                original_code = ""
            file_stem = file_path.stem
            for model in model_ids:
                out_repo = model_dirs[model] / file_stem
                out_repo.mkdir(parents=True, exist_ok=True)

                try:
                    new_code = perfect_code_with_model(
                        model=model,
                        code=original_code,
                        file_name=file_path.name,
                        temperature=0.0,
                        extra_instructions=extra_text,
                    )
                except Exception as e:
                    console.print(f"[yellow]Model '{model}' failed on {file_path.name}: {e}[/yellow]")
                    new_code = original_code

                if new_code is None:
                    console.print(f"[yellow]Model '{model}' returned no content for {file_path.name}; using original content.[/yellow]")
                    new_code = original_code

                # Write improved file (flatten nested names if needed)
                out_file = out_repo / file_path.name
                try:
                    out_file.write_text(new_code, encoding="utf-8")
                except (OSError, UnicodeEncodeError) as exc:
                    # attempt safe fallback name and log the failure
                    console.print(f"[yellow]Failed to write file {out_file}: {exc}. Attempting fallback filename.[/yellow]")
                    try:
                        out_file = out_repo / file_path.name.replace(os.sep, "_")
                        out_file.write_text(new_code, encoding="utf-8")
                    except (OSError, UnicodeEncodeError) as exc2:
                        console.print(f"[red]Failed to write fallback file {out_file}: {exc2}. Skipping file.[/red]")
                        # Skip to next file without raising
                        continue

                # Best-effort tests copy for python files
                if copy_tests and file_path.suffix == ".py":
                    _copy_tests_for_file(file_path, out_repo)

                progress.advance(task)

    # Analyze collections per model
    console.print(Align.center("[bold blue]📊 Scoring generated code[/bold blue]"))

    def _collect(folder: Path):
        repo_dirs = _list_immediate_repo_dirs(folder)
        aggregate = defaultdict(list)
        for repo in repo_dirs:
            raw_scores = _analyze_single_codebase(repo, skip_set, benchmark_weights)
            for k, v in raw_scores.items():
                aggregate[k].append(v)
        avg_scores = {k: (sum(vs)/len(vs) if vs else 0.0) for k, vs in aggregate.items()}
        return avg_scores, len(repo_dirs)

    model1, model2 = model_ids
    avg1, n1 = _collect(model_dirs[model1])
    avg2, n2 = _collect(model_dirs[model2])

    console.print(Align.center(f"Comparing [magenta]{_slugify(model1)}[/magenta] ({n1} repos) vs [green]{_slugify(model2)}[/green] ({n2} repos)"))
    console.print()

    table = Table(title="🏁 LLM Battle - Average Scores Across Files", box=box.ROUNDED)
    table.add_column("Benchmark", style="cyan")
    table.add_column(f"🔵 {_slugify(model1)}")
    table.add_column(f"🟢 {_slugify(model2)}")
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

    # Write summary JSON
    export_path = run_root / "summary.json"
    summary = {
        "run_root": str(run_root),
        "model1": model1,
        "model2": model2,
        "avg_scores_model1": avg1,
        "avg_scores_model2": avg2,
        "total1": total1,
        "total2": total2,
        "skip": list(skip_set),
        "weights": benchmark_weights,
        "files": [str(p) for p in file_paths],
    }
    export_path.write_text(json.dumps(summary, indent=2))
    console.print(f"[green]Saved run to {export_path.parent}")


def compare(
    codebase1: Path = typer.Option(..., "--codebase1", "-c1", help="Path to the first codebase."),
    codebase2: Path = typer.Option(..., "--codebase2", "-c2", help="Path to the second codebase."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output with details for each benchmark."),
    weights: str = typer.Option('{}', "--weights", "-w", help='JSON string to weight benchmarks. e.g., \'{"Readability": 1.2, "Security": 0.8}\''),
    skip: str = typer.Option('', "--skip", help="Comma-separated list of benchmark names to skip."),
    export: Path = typer.Option(None, "--export", help="Path to write JSON export of results."),
    profile: Path = typer.Option(None, "--profile", help="Python script to execute for runtime profiling (pyinstrument)"),
):
    """
    Compares two codebases and rates them on a scale based on different benchmarks.
    """
    if not codebase1.is_dir() or not codebase2.is_dir():
        console.print("[bold red]Error: Both codebases must be valid directories.[/bold red]")
        raise typer.Exit(code=1)

    try:
        benchmark_weights = json.loads(weights)
    except json.JSONDecodeError:
        console.print("[bold red]Error: Invalid JSON format for weights.[/bold red]")
        raise typer.Exit(code=1)

    # Ensure weights values are numeric
    if isinstance(benchmark_weights, dict):
        sanitized_weights = {}
        for k, v in benchmark_weights.items():
            try:
                sanitized_weights[k] = float(v)
            except (TypeError, ValueError):
                console.print(f"[yellow]Warning: Invalid weight for '{k}' -> {v}. Defaulting to 1.0[/yellow]")
                sanitized_weights[k] = 1.0
        benchmark_weights = sanitized_weights
    else:
        console.print("[yellow]Warning: Weights should be a JSON object. Ignoring weights.[/yellow]")
        benchmark_weights = {}

    skip_set = {s.strip().capitalize() for s in skip.split(',') if s.strip()}

    # Set env for runtime profiling
    if profile:
        os.environ["BENCH_PROFILE_SCRIPT"] = str(profile)

    # Welcome banner
    welcome_text = Text.assemble(
        ("🔍 OpenBase", "bold blue"),
        (" - Professional Codebase Quality Analysis", "bold white")
    )
    console.print(Align.center(welcome_text))
    console.print(Align.center(f"Comparing [magenta]{codebase1.name}[/magenta] vs [green]{codebase2.name}[/green]"))
    console.print()

    # Detect languages present in each codebase
    from benchmarks.language_utils import detect_languages
    langs1 = detect_languages(codebase1)
    langs2 = detect_languages(codebase2)

    # Prepare benchmarks to run, filtering by language support
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
    # Store full result objects so we don't need to re-run benchmarks later
    result_objects1, result_objects2 = {}, {}

    # Run benchmarks with progress tracking
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
            
            # Handle both old tuple format and new BenchmarkResult
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
            
            # cache result objects
            result_objects1[name] = result1
            result_objects2[name] = result2

            raw_scores1[name] = score1
            raw_scores2[name] = score2

            details1[name] = detail1
            details2[name] = detail2
            
            progress.advance(main_task)
            time.sleep(0.1)  # Small delay for visual effect
    
    console.print("✅ Analysis complete!\n")
    
    # Check for empty repositories
    if all(score == 0.0 for score in raw_scores1.values()):
        console.print(f"[yellow]Warning: {codebase1.name} appears to be empty or has no analyzable code.[/yellow]")
    if all(score == 0.0 for score in raw_scores2.values()):
        console.print(f"[yellow]Warning: {codebase2.name} appears to be empty or has no analyzable code.[/yellow]")
    
    # Apply z-score normalization to prevent metric dominance
    normalized_scores1 = normalize_scores_zscore(raw_scores1)
    normalized_scores2 = normalize_scores_zscore(raw_scores2)
    
    # Create enhanced results table
    table = Table(
        title="📊 Codebase Quality Comparison Results",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold white on blue"
    )
    table.add_column("Benchmark", justify="right", style="cyan", no_wrap=True)
    table.add_column(f"🔵 {codebase1.name}", justify="center", style="magenta")
    table.add_column(f"🟢 {codebase2.name}", justify="center", style="green")
    table.add_column("Winner", justify="center", style="bold yellow")
    
    # Apply weights and calculate totals
    total_score1, total_score2 = 0, 0
    for name in benchmarks_to_run:
        name = name[0]  # Extract name string from tuple
        func = BENCHMARK_FUNCS[name]
            
        weight = benchmark_weights.get(name, 1.0)
        weighted_score1 = normalized_scores1[name] * weight
        weighted_score2 = normalized_scores2[name] * weight
        
        # Accumulate total scores
        total_score1 += weighted_score1
        total_score2 += weighted_score2

        # Format scores with confidence intervals if available
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
        
        # Determine winner
        if weighted_score1 > weighted_score2:
            winner = "🔵"
        elif weighted_score2 > weighted_score1:
            winner = "🟢"
        else:
            winner = "🤝"
            
        table.add_row(name, score1_display, score2_display, winner)
    
    # Add separator and totals
    table.add_row("", "", "", "")
    
    # Overall winner
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
    
    # Summary panel
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

    # Store enhanced results
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

    # Export if requested
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
        
        for name, _func in benchmarks_to_run:
            console.print(f"\n[bold cyan]🔍 {name} Analysis[/bold cyan]")
            
            # Create a tree structure for better organization
            tree = Tree(f"[bold]{name}[/bold]")
            
            # Add codebase 1 details
            cb1_branch = tree.add(f"[magenta]🔵 {codebase1.name}[/magenta] - Score: [bold]{normalized_scores1[name]:.2f}[/bold]")
            details1_content = details1[name] if details1[name] else ["✅ No issues found."]
            for detail in details1_content[:5]:  # Limit to first 5 items
                cb1_branch.add(f"• {detail}")
            if len(details1_content) > 5:
                cb1_branch.add(f"[dim]... and {len(details1_content) - 5} more items[/dim]")
            
            # Add codebase 2 details
            cb2_branch = tree.add(f"[green]🟢 {codebase2.name}[/green] - Score: [bold]{normalized_scores2[name]:.2f}[/bold]")
            details2_content = details2[name] if details2[name] else ["✅ No issues found."]
            for detail in details2_content[:5]:  # Limit to first 5 items
                cb2_branch.add(f"• {detail}")
            if len(details2_content) > 5:
                cb2_branch.add(f"[dim]... and {len(details2_content) - 5} more items[/dim]")
            
            console.print(tree)
            
            # Add interpretation
            score1, score2 = normalized_scores1[name], normalized_scores2[name]
            if abs(score1 - score2) < 0.5:
                interpretation = "📊 Both codebases perform similarly in this area."
            elif score1 > score2:
                interpretation = f"📈 {codebase1.name} outperforms {codebase2.name} by {score1-score2:.1f} points."
            else:
                interpretation = f"📈 {codebase2.name} outperforms {codebase1.name} by {score2-score1:.1f} points."
            
            console.print(f"[dim]{interpretation}[/dim]")
            console.print()  # Add spacing


if __name__ == "__main__":
    app()