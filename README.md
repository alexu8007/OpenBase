# 🔍 OpenBase - Professional Codebase Quality Analysis

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Quality](https://img.shields.io/badge/code%20quality-enterprise-green.svg)](https://github.com/yourusername/openbase)

OpenBase is an enterprise-grade codebase quality analysis tool that provides comprehensive, statistical comparisons between codebases across 10 critical quality dimensions. Built for developers, architects, and engineering teams who need objective, data-driven insights into code quality.

## 🎯 Why OpenBase?

- **🔬 Scientific Approach**: Uses statistical analysis with confidence intervals and z-score normalization
- **📊 10 Quality Dimensions**: Comprehensive analysis across readability, security, performance, and more
- **⚡ Hybrid Analysis**: Combines static analysis with dynamic runtime profiling
- **🎨 Beautiful CLI**: Rich, interactive interface with progress bars and detailed reports
- **🔧 Enterprise Ready**: Configurable weights, historical tracking, and JSON export
- **🚀 CI/CD Integration**: Perfect for automated quality gates and code reviews

## 📋 Quality Dimensions Analyzed

| Dimension | What It Measures | Tools Used |
|-----------|------------------|------------|
| **Readability** | Code complexity, PEP8 compliance, naming conventions | Radon, pycodestyle |
| **Maintainability** | Maintainability Index, technical debt indicators | Radon |
| **Performance** | Runtime efficiency, memory usage, anti-patterns | pyinstrument, memory_profiler |
| **Testability** | Test coverage, test quality, testable design | pytest, coverage.py |
| **Robustness** | Error handling, logging practices, resilience | AST analysis |
| **Security** | Vulnerability detection, security best practices | Bandit, Safety, OWASP ZAP |
| **Scalability** | Architectural patterns, bottleneck detection | Custom analysis |
| **Documentation** | Docstring coverage, quality, completeness | Custom quality heuristics |
| **Consistency** | Naming conventions, code style uniformity | AST analysis |
| **Git Health** | Commit patterns, bus factor, code churn | GitPython |

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/openbase.git
cd openbase

# Install dependencies
pip install -r requirements.txt

# Run your first comparison
python main.py --codebase1 ./project-a --codebase2 ./project-b
```

### Basic Usage

```bash
# Simple comparison
python main.py --codebase1 ./codebase-a --codebase2 ./codebase-b

# With verbose output
python main.py -c1 ./codebase-a -c2 ./codebase-b --verbose

# Export results to JSON
python main.py -c1 ./codebase-a -c2 ./codebase-b --export results.json
```

## 🎨 Beautiful Output

OpenBase provides rich, interactive output with:

- **Progress bars** showing analysis progress
- **Color-coded results** with winner indicators
- **Detailed tree views** in verbose mode
- **Summary assessments** with actionable insights
- **Confidence intervals** for statistical rigor

### Example Output

```
🔍 OpenBase - Professional Codebase Quality Analysis
        Comparing project-a vs project-b

⠋ Analyzing readability... ████████████████████████████████ 100%

📊 Codebase Quality Comparison Results
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┓
┃       Benchmark ┃      🔵 project-a      ┃      🟢 project-b      ┃ Winner ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━┩
│     Readability │          7.2           │          6.8           │   🔵   │
│ Maintainability │          8.1           │          7.9           │   🔵   │
│     Performance │          6.5           │          5.2           │   🔵   │
│        Security │          9.1           │          8.7           │   🔵   │
│                 │                        │                        │        │
│     TOTAL SCORE │         68.4           │         62.1           │ 🔵 project-a │
└─────────────────┴────────────────────────┴────────────────────────┴────────┘

🎯 Summary
project-a is moderately better than the other codebase.
```

## ⚙️ Advanced Features

### Custom Weights

Weight different quality dimensions based on your priorities:

```bash
python main.py -c1 ./app-a -c2 ./app-b \
  --weights '{"Security": 2.0, "Performance": 1.5, "Documentation": 0.5}'
```

### Skip Benchmarks

Skip specific analyses:

```bash
python main.py -c1 ./app-a -c2 ./app-b --skip "Performance,GitHealth"
```

### Runtime Profiling

Include dynamic performance analysis:

```bash
python main.py -c1 ./app-a -c2 ./app-b --profile ./benchmark_script.py
```

### Historical Tracking

OpenBase automatically tracks all comparisons in a SQLite database for trend analysis and historical insights.

## 🔧 Configuration

### Environment Variables

```bash
# For web application security scanning
export BENCH_WEB_APP_URL="http://localhost:8000"

# For runtime profiling
export BENCH_PROFILE_SCRIPT="./performance_test.py"
```

### Weights Configuration

Create a `weights.json` file:

```json
{
  "Security": 2.0,
  "Performance": 1.5,
  "Maintainability": 1.2,
  "Documentation": 0.8,
  "Testability": 1.3
}
```

## 📊 Statistical Features

### Confidence Intervals

OpenBase provides confidence intervals for metrics with multiple samples:

```
Performance: 7.2 ±0.8
```

### Size-Aware Scoring

Automatically adjusts scores based on codebase size to prevent bias:

- **Small codebases** (<100 LOC): Bonus multipliers for certain metrics
- **Large codebases** (>1000 LOC): Appropriate complexity adjustments

### Z-Score Normalization

Prevents any single metric from dominating the final score while preserving meaningful differences.

## 🏢 Enterprise Use Cases

### Code Review Gates

```bash
# In your CI/CD pipeline
python main.py -c1 ./main-branch -c2 ./feature-branch --export review.json
if [ $(jq '.total_score2 < .total_score1' review.json) ]; then
  echo "Quality regression detected!"
  exit 1
fi
```

### Architecture Decisions

Compare different architectural approaches:

```bash
python main.py -c1 ./monolith -c2 ./microservices --verbose
```

### Technical Debt Assessment

Track quality improvements over time:

```bash
python main.py -c1 ./v1.0 -c2 ./v2.0 --weights '{"Maintainability": 2.0}'
```

## 🔌 Integration

### JSON Export Format

```json
{
  "codebase1": "./project-a",
  "codebase2": "./project-b",
  "total_score1": 68.4,
  "total_score2": 62.1,
  "raw_scores1": { "Readability": 7.2, "Security": 9.1 },
  "normalized_scores1": { "Readability": 7.2, "Security": 9.1 },
  "raw_metrics1": { "Readability": {"complexity": 2.1, "pep8_violations": 23} },
  "confidence_intervals": { "Performance": [6.8, 7.6] }
}
```

### Database Schema

OpenBase stores results in SQLite with full historical tracking:

```sql
CREATE TABLE benchmark_runs (
    id INTEGER PRIMARY KEY,
    codebase1_path TEXT,
    codebase2_path TEXT,
    total_score1 REAL,
    total_score2 REAL,
    detailed_results TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## 🛠️ Development

### Requirements

- Python 3.8+
- Git (for GitHealth analysis)
- Optional: OWASP ZAP (for dynamic security testing)

### Dependencies

```txt
typer>=0.9.0
rich>=13.0.0
radon>=6.0.1
pycodestyle>=2.11.0
bandit>=1.7.5
safety>=2.3.0
pytest>=7.4.0
coverage>=7.2.0
gitpython>=3.1.0
pyinstrument>=4.5.0
memory-profiler>=0.61.0
scipy>=1.10.0
numpy>=1.24.0
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📈 Roadmap

- [ ] **Plugin System**: Custom benchmark plugins
- [ ] **Web Dashboard**: Interactive web interface
- [ ] **Team Analytics**: Multi-developer insights
- [ ] **ML Insights**: Predictive quality analysis
- [ ] **IDE Integration**: VS Code extension
- [ ] **Language Support**: JavaScript, Java, C++ analysis

## 🤝 Support

- **Documentation**: [Full documentation](https://github.com/yourusername/openbase/wiki)
- **Issues**: [GitHub Issues](https://github.com/yourusername/openbase/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/openbase/discussions)
- **Email**: support@openbase.dev

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Radon** for complexity analysis
- **Bandit** for security scanning
- **Rich** for beautiful terminal output
- **Typer** for CLI framework
- The open-source community for inspiration and tools

---

**Made with ❤️ for better code quality**

*OpenBase - Because every codebase deserves a fair comparison.* 
