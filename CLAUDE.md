# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**OpenBase** is an enterprise-grade codebase quality analysis tool that provides comprehensive, statistical comparisons between codebases across 10 critical quality dimensions. The tool uses scientific analysis with confidence intervals and z-score normalization to provide objective, data-driven insights into code quality.

## Architecture & Core Components

### Main Entry Point
- **main.py**: Primary CLI application built with `typer` and `rich` for beautiful terminal output
  - `compare` command: Compares two individual codebases
  - `compare-collections` command: Compares collections of repositories (batch analysis)

### Benchmark System (`benchmarks/` directory)
The tool implements a modular benchmark system with 10 quality dimensions:

1. **Readability** (`readability.py`) - Code complexity, PEP8 compliance, naming conventions
2. **Maintainability** (`maintainability.py`) - Maintainability Index, technical debt indicators  
3. **Performance** (`performance.py`) - Runtime efficiency, memory usage, anti-patterns
4. **Testability** (`testability.py`) - Test coverage, test quality, testable design
5. **Robustness** (`robustness.py`) - Error handling, logging practices, resilience
6. **Security** (`security.py`) - Vulnerability detection, security best practices
7. **Scalability** (`scalability.py`) - Architectural patterns, bottleneck detection
8. **Documentation** (`documentation.py`) - Docstring coverage, quality, completeness
9. **Consistency** (`consistency.py`) - Naming conventions, code style uniformity
10. **Git Health** (`git_health.py`) - Commit patterns, bus factor, code churn

### Core Infrastructure
- **plugin_base.py**: Abstract base class `BenchmarkPlugin` for all benchmark implementations
- **language_utils.py**: Multi-language detection system supporting C/C++, Go, Rust, Java, JavaScript/TypeScript, Python, and more
- **stats_utils.py**: Statistical utilities for normalization, confidence intervals, and z-score calculations
- **db.py**: SQLite database for historical tracking of benchmark runs
- **utils.py**: Common utilities for file operations and analysis

### Data Storage
- **benchmark_results.db**: SQLite database storing all comparison results with timestamps
- **reports/**: Generated HTML, JSON, and Markdown reports from analysis runs

## Common Development Commands

### Running Analysis
```bash
# Basic codebase comparison
python main.py compare --codebase1 ./project-a --codebase2 ./project-b

# Verbose analysis with detailed breakdown
python main.py compare -c1 ./project-a -c2 ./project-b --verbose

# Export results to JSON
python main.py compare -c1 ./project-a -c2 ./project-b --export results.json

# Compare collections of repositories
python main.py compare-collections --folder1 ./repos --folder2 ./repos2

# Custom weights for different benchmarks
python main.py compare -c1 ./app-a -c2 ./app-b --weights '{"Security": 2.0, "Performance": 1.5}'

# Skip specific benchmarks
python main.py compare -c1 ./app-a -c2 ./app-b --skip "Performance,GitHealth"

# Runtime profiling with custom script
python main.py compare -c1 ./app-a -c2 ./app-b --profile ./benchmark_script.py
```

### Testing & Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run tests (basic pytest setup detected)
python -m pytest

# Run specific test files
python -m pytest testcursor/test_data_processor.py
python -m pytest testttt-mainp0/test_data_processor.py

# Lint code (ruff available)
ruff check .

# Type checking (mypy available)  
mypy .

# Test coverage
pytest --cov
```

### Analysis Tools Available
The repository includes several external analysis tools integrated into the benchmarks:
- **Radon**: Complexity analysis and maintainability metrics
- **Bandit**: Security vulnerability scanning
- **Safety**: Dependency vulnerability checking  
- **pycodestyle**: PEP8 compliance checking
- **pytest & coverage**: Test analysis
- **pyinstrument**: Performance profiling
- **memory_profiler**: Memory usage analysis
- **lizard**: Cyclomatic complexity analysis

## Key Implementation Details

### Language Support
The system automatically detects programming languages in codebases and runs appropriate benchmarks. Each benchmark module defines `SUPPORTED_LANGUAGES` (defaulting to Python if not specified).

### Statistical Analysis
- Uses z-score normalization to prevent metric dominance
- Provides confidence intervals for statistical rigor
- Size-aware scoring with adjustments for small/large codebases
- Weighted scoring system for custom priorities

### Database Schema
```sql
CREATE TABLE runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    codebase1 TEXT,
    codebase2 TEXT, 
    total1 REAL,
    total2 REAL,
    details_json TEXT
);
```

### Configuration Options
- Environment variables: `BENCH_WEB_APP_URL`, `BENCH_PROFILE_SCRIPT`
- Custom weights via JSON: `{"Security": 2.0, "Performance": 1.5}`
- Benchmark filtering via `--skip` parameter

## Repository Structure Notes

The `repos/` and `repos2/` directories contain sample codebases for testing:
- Various Python projects (smart cane, umbrella reminder, snake game, etc.)
- Test applications in `testcursor/`, `testttt-mainp0/`, etc.
- Mix of IoT projects, web applications, and ML training code

Each benchmark is designed to work across multiple programming languages, with fallback heuristics when language-specific analysis isn't available.