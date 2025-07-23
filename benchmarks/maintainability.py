from radon.metrics import mi_visit

SUPPORTED_LANGUAGES = {"python"}
from .utils import get_python_files
from .stats_utils import BenchmarkResult, calculate_confidence_interval, adjust_score_for_size, get_codebase_size_bucket

def process_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        code = f.read()
    if code.strip():
        try:
            mi = mi_visit(code, multi=True)
            return mi, None
        except Exception:
            return None, f"Could not parse {file_path}"
    else:
        return None, None

def assess_maintainability(codebase_path: str) -> BenchmarkResult:
    """
    Assesses the maintainability of a codebase using the Maintainability Index (MI).
    Includes bias adjustment for codebase size and confidence intervals.
    """
    python_files = get_python_files(codebase_path)
    if not python_files:
        return BenchmarkResult(0.0, ["No Python files found."])

    file_mis = []  # Store individual file MI scores for confidence calculation
    details = []
    raw_metrics = {}
    
    for file_path in python_files:
        mi, message = process_file(file_path)
        if mi is not None:
            file_mis.append(mi)
            if mi < 40:
                details.append(f"Low maintainability index ({mi:.2f}) in {file_path}")
        if message:
            details.append(message)

    if not file_mis:
        return BenchmarkResult(0.0, ["No parseable Python files found."])

    avg_mi = sum(file_mis) / len(file_mis)
    raw_metrics["file_mi_scores"] = file_mis
    raw_metrics["avg_mi"] = avg_mi
    
    # Raw score calculation
    raw_score = avg_mi / 10.0
    
    # === BIAS ADJUSTMENT ===
    size_bucket = get_codebase_size_bucket(codebase_path)
    adjusted_score = adjust_score_for_size(raw_score, size_bucket, "maintainability")
    raw_metrics["size_bucket"] = size_bucket
    raw_metrics["unadjusted_score"] = raw_score
    
    details.insert(0, f"Average maintainability index (MI): {avg_mi:.2f} (size: {size_bucket})")
    
    # === CONFIDENCE INTERVAL ===
    # Use file-level MI scores to calculate confidence
    confidence_interval = calculate_confidence_interval(file_mis)
    
    return BenchmarkResult(
        score=min(10.0, max(0.0, adjusted_score)),
        details=details,
        raw_metrics=raw_metrics,
        confidence_interval=(confidence_interval[0]/10.0, confidence_interval[1]/10.0)  # Scale to 0-10
    )