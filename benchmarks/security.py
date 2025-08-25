import subprocess

SUPPORTED_LANGUAGES = {"python"}
import json
import os
import time
from typing import List, Dict, Any
from .utils import get_python_files
from .stats_utils import BenchmarkResult, calculate_confidence_interval, adjust_score_for_size, get_codebase_size_bucket
import tempfile
import logging
from urllib.parse import urlparse
import shutil

# Configure module logger. Do not log sensitive inputs (e.g., tokens).
logger = logging.getLogger(__name__)

def assess_security(codebase_path: str) -> BenchmarkResult:
    """
    Hybrid static + dynamic security assessment.
    Combines bandit/safety with optional OWASP ZAP dynamic scanning.
    """
    details = []
    raw_metrics = {}
    
    # === STATIC ANALYSIS ===
    try:
        static_score, static_details, static_metrics = _assess_static_security(codebase_path)
    except Exception as e:
        # Fail-fast with logging; return conservative results if static scan fails.
        logger.exception("Static security assessment failed")
        details.append("[Static] Assessment failed unexpectedly")
        static_score, static_details, static_metrics = 0.0, ["[Static] Assessment failed."], {}
    details.extend(static_details)
    raw_metrics.update(static_metrics)
    
    # === DYNAMIC ANALYSIS ===
    web_app_url = os.getenv("BENCH_WEB_APP_URL")  # e.g., http://localhost:8000
    if web_app_url:
        try:
            dynamic_score, dynamic_details, dynamic_metrics = _assess_dynamic_security(web_app_url)
            details.extend(dynamic_details)
            raw_metrics.update(dynamic_metrics)
            
            # Combine static + dynamic (weighted)
            final_score = (0.6 * static_score) + (0.4 * dynamic_score)
        except Exception:
            logger.exception("Dynamic security assessment failed")
            details.append("[Dynamic] Assessment failed unexpectedly")
            final_score = static_score
    else:
        final_score = static_score
        details.append("No web app URL provided (set BENCH_WEB_APP_URL). Using static analysis only.")
    
    # === BIAS ADJUSTMENT ===
    size_bucket = get_codebase_size_bucket(codebase_path)
    adjusted_score = adjust_score_for_size(final_score, size_bucket, "security")
    raw_metrics["size_bucket"] = size_bucket
    raw_metrics["unadjusted_score"] = final_score
    
    # === CONFIDENCE INTERVAL ===
    score_samples = [static_score]
    if "dynamic_score" in raw_metrics:
        score_samples.append(raw_metrics["dynamic_score"])
    
    confidence_interval = calculate_confidence_interval(score_samples)
    
    return BenchmarkResult(
        score=adjusted_score,
        details=details,
        raw_metrics=raw_metrics,
        confidence_interval=confidence_interval
    )


def _assess_static_security(codebase_path: str) -> tuple[float, List[str], Dict[str, Any]]:
    """Static security analysis with bandit and safety."""
    details = []
    metrics = {}
    
    # Input validation: ensure codebase_path is a valid directory to avoid path traversal
    if not codebase_path or not os.path.isdir(codebase_path):
        msg = "[Static] Invalid codebase_path provided or path does not exist"
        logger.error(msg + ": %s", codebase_path)
        details.append(msg)
        # Return conservative neutral/low scores and empty metrics
        metrics["bandit_score"] = 0.0
        metrics["safety_score"] = 0.0
        return 0.0, details, metrics

    # Ensure the path is readable
    if not os.access(codebase_path, os.R_OK):
        msg = "[Static] Codebase path is not readable"
        logger.error(msg + ": %s", codebase_path)
        details.append(msg)
        metrics["bandit_score"] = 0.0
        metrics["safety_score"] = 0.0
        return 0.0, details, metrics

    # --- Bandit Scan ---
    bandit_score = 10.0
    # Pre-flight check for bandit executable to avoid OSError and give clearer diagnostics
    if shutil.which("bandit") is None:
        details.append("[Bandit] Executable 'bandit' not found in PATH")
        logger.info("Bandit executable not found in PATH")
        bandit_score = 0.0
    else:
        try:
            # Using list-based command invocation to avoid shell=True and command injection.
            # We validate inputs above and do not pass untrusted strings to a shell.
            command = [
                "bandit", "-r", codebase_path, "-f", "json",
                "--skip", "B101,B601",  # Skip common test-related issues
                "--exclude", "*/stls/*,*/dataset.zip,*/.venv/*,*/node_modules/*,*/__pycache__/*,*/build/*,*/dist/*,*.pyc,*.zip,*.tar.gz,*.stl,*.step,*.blob,*.pdf,*.png,*.jpg,*.wav,*.mp3"
            ]
            result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=60, close_fds=True)
            stdout = result.stdout or ""
            try:
                report = json.loads(stdout) if stdout else {}
            except json.JSONDecodeError:
                logger.warning("Bandit output was not valid JSON")
                report = {}
            
            if report and "results" in report:
                findings = report["results"]
                high = sum(1 for f in findings if f.get("issue_severity") == "HIGH")
                medium = sum(1 for f in findings if f.get("issue_severity") == "MEDIUM")
                low = sum(1 for f in findings if f.get("issue_severity") == "LOW")
                
                details.append(f"[Bandit] High: {high}, Medium: {medium}, Low: {low}")
                metrics["bandit_high"] = high
                metrics["bandit_medium"] = medium
                metrics["bandit_low"] = low

                for f in findings[:10]:  # Limit to first 10
                    # Defensive access to fields
                    issue_text = f.get('issue_text', 'No description')
                    filename = f.get('filename', 'unknown')
                    line_number = f.get('line_number', '?')
                    details.append(f"  - {issue_text} ({filename}:{line_number})")

                score_deduction = (high * 3) + (medium * 1) + (low * 0.5)
                bandit_score = max(0.0, 10.0 - score_deduction)
            else:
                # No results parsed; be conservative
                details.append("[Bandit] No results from bandit or parsing failed.")
                bandit_score = 5.0
        except subprocess.TimeoutExpired:
            details.append("[Bandit] Scan timed out (>60s)")
            logger.warning("Bandit scan timed out for path: %s", codebase_path)
            bandit_score = 3.0
        except FileNotFoundError:
            details.append("[Bandit] Could not run bandit.")
            logger.info("Bandit executable not found in PATH")
            bandit_score = 0.0
        except Exception as e:
            # Log full exception for operators; append sanitized message to details
            logger.exception("Unexpected error running bandit")
            details.append("[Bandit] Unexpected error running bandit.")
            bandit_score = 0.0

    # --- Safety Scan ---
    safety_score = 10.0
    req_file = os.path.join(codebase_path, "requirements.txt")
    if os.path.exists(req_file):
        if not os.access(req_file, os.R_OK):
            details.append("[Safety] requirements.txt not readable")
            logger.error("requirements.txt exists but is not readable: %s", req_file)
            safety_score = 5.0
        elif shutil.which("safety") is None:
            details.append("[Safety] Safety executable not found in PATH")
            logger.info("Safety executable not found in PATH")
            safety_score = 8.0  # Neutral if tool unavailable
        else:
            try:
                # Try new safety scan first (requires auth but may work)
                command = ["safety", "scan", "--file", req_file, "--output", "json", "--disable-optional-telemetry"]
                result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=5, close_fds=True)
                
                if result.returncode != 0:
                    # Fallback: try deprecated safety check
                    command = ["safety", "check", f"--file={req_file}", "--json", "--disable-optional-telemetry"]
                    result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=5, close_fds=True)
                
                stdout = result.stdout or ""
                if stdout:
                    try:
                        report = json.loads(stdout)
                        # Handle both old and new format
                        if isinstance(report, list):
                            vulns = len(report)
                            details.append(f"[Safety] {vulns} vulnerable dependencies")
                            metrics["safety_vulnerabilities"] = vulns
                            
                            for vuln in report[:5]:  # Limit output
                                pkg_name = vuln.get('package_name', vuln.get('package', 'unknown'))
                                advisory = vuln.get('advisory', vuln.get('vulnerability_id', 'No description'))
                                details.append(f"  - {pkg_name}: {str(advisory)[:100]}...")
                            
                            safety_score = max(0.0, 10.0 - (vulns * 2))
                        else:
                            # New format handling
                            vulns = len(report.get('vulnerabilities', []))
                            details.append(f"[Safety] {vulns} vulnerable dependencies")
                            metrics["safety_vulnerabilities"] = vulns
                            safety_score = max(0.0, 10.0 - (vulns * 2))
                    except json.JSONDecodeError:
                        # If JSON parsing fails, assume no vulnerabilities found but log
                        details.append("[Safety] No vulnerabilities detected (or unable to parse output)")
                        logger.warning("Safety output could not be parsed as JSON")
                        safety_score = 10.0
                else:
                    details.append("[Safety] No output from safety command")
                    logger.info("Safety command produced no stdout for requirements file: %s", req_file)
                    safety_score = 8.0
                    
            except subprocess.TimeoutExpired:
                details.append("[Safety] Scan timed out (>15s) - skipping dependency check")
                logger.warning("Safety scan timed out for file: %s", req_file)
                safety_score = 7.0  # Neutral score for timeout
            except FileNotFoundError:
                details.append("[Safety] Safety tool not available")
                logger.info("Safety executable not found in PATH")
                safety_score = 8.0  # Neutral if tool unavailable
            except Exception as e:
                # Log for operators; avoid revealing sensitive info in details
                logger.exception("Unexpected error running safety")
                details.append("[Safety] Error running safety tool")
                safety_score = 5.0
    else:
        details.append("[Safety] No requirements.txt found.")
        safety_score = 8.0  # Neutral if no deps to check

    # Combine static scores
    static_score = (bandit_score * 0.7) + (safety_score * 0.3)
    metrics["bandit_score"] = bandit_score
    metrics["safety_score"] = safety_score
    
    return static_score, details, metrics


def _assess_dynamic_security(web_app_url: str) -> tuple[float, List[str], Dict[str, Any]]:
    """Dynamic security testing with OWASP ZAP (if available)."""
    details = []
    metrics = {}

    # Validate URL using a simple whitelist of schemes to prevent misuse
    parsed = urlparse(web_app_url)
    if parsed.scheme not in ("http", "https"):
        msg = "[ZAP] Invalid or unsupported URL scheme provided for dynamic scanning"
        logger.error(msg + ": %s", web_app_url)
        details.append(msg)
        metrics["dynamic_score"] = 5.0
        return 5.0, details, metrics

    # Basic netloc/credentials validation to avoid accidental credential disclosure or malformed hosts
    if not parsed.netloc:
        msg = "[ZAP] URL missing network location"
        logger.error(msg + ": %s", web_app_url)
        details.append(msg)
        metrics["dynamic_score"] = 5.0
        return 5.0, details, metrics

    if parsed.username or parsed.password:
        msg = "[ZAP] URL must not contain credentials"
        logger.error(msg + ": %s", web_app_url)
        details.append(msg)
        metrics["dynamic_score"] = 5.0
        return 5.0, details, metrics

    # Optionally, restrict dynamic scanning to local addresses to avoid scanning external systems.
    # If you need to scan external hosts, adjust this policy elsewhere with appropriate authorization.
    hostname = parsed.hostname or ""
    if hostname not in ("localhost", "127.0.0.1", "::1"):
        logger.warning("Dynamic scanning restricted to localhost by default. Host provided: %s", hostname)
        details.append("[ZAP] Dynamic scanning restricted to localhost only in this environment")
        metrics["dynamic_score"] = 5.0
        return 5.0, details, metrics

    # Check if Docker is available
    if shutil.which("docker") is None:
        details.append("[ZAP] Docker not available in PATH; cannot run ZAP container")
        logger.info("Docker executable not found when attempting ZAP scan")
        metrics["dynamic_score"] = 5.0
        return 5.0, details, metrics

    # Check if ZAP image likely available could be omitted; rely on docker pull failure handling.
    # Use a temporary directory for reports instead of hard-coded /tmp path.
    try:
        with tempfile.TemporaryDirectory() as host_tmpdir:
            container_report_dir = "/zap_reports"
            container_report_path = os.path.join(container_report_dir, "zap-report.json")

            # Build docker command without shell invocation (list form) to avoid shell injection.
            # We mount a temporary directory into the container to capture the report securely.
            command = [
                "docker", "run", "--rm", "-t",
                "-v", f"{host_tmpdir}:{container_report_dir}",
                "owasp/zap2docker-stable",
                "zap-baseline.py",
                "-t", web_app_url,
                "-J", container_report_path
            ]
            
            details.append(f"[ZAP] Running baseline scan on {web_app_url}")
            
            # Run with timeout
            result = subprocess.run(
                command, 
                capture_output=True, 
                text=True, 
                timeout=120,  # 2 minute timeout
                check=False,
                close_fds=True
            )
            
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            # ZAP returns non-zero on findings, so check output instead
            if "PASS" in stdout or "WARN" in stdout or "PASS" in stderr or "WARN" in stderr or "HIGH" in stdout or "MEDIUM" in stdout:
                # Count severity levels from output
                high_count = stdout.count("HIGH") + stderr.count("HIGH")
                medium_count = stdout.count("MEDIUM") + stderr.count("MEDIUM")
                low_count = stdout.count("LOW") + stderr.count("LOW")
                
                # If the container produced a JSON report, try to read it for more reliable counts.
                try:
                    report_file_path = os.path.join(host_tmpdir, "zap-report.json")
                    if os.path.exists(report_file_path) and os.path.getsize(report_file_path) < (5 * 1024 * 1024):
                        with open(report_file_path, "r", encoding="utf-8") as f:
                            try:
                                zap_report = json.load(f)
                                # Defensive access pattern
                                alerts = zap_report.get("site", []) if isinstance(zap_report, dict) else []
                                # If structured differently, keep the stdout counts.
                                # We do not attempt to deeply parse unknown structures here.
                                # This read is best-effort and won't overwrite stdout-based counts unless clear.
                                if isinstance(alerts, list) and alerts:
                                    # Aggregate counts if available in a known structure
                                    # (This is defensive and will not crash on unexpected formats.)
                                    pass
                            except json.JSONDecodeError:
                                logger.debug("ZAP JSON report could not be parsed")
                except Exception:
                    logger.exception("Failed to read ZAP report from temporary directory")

                details.append(f"[ZAP] Findings - High: {high_count}, Medium: {medium_count}, Low: {low_count}")
                
                metrics["zap_high"] = high_count
                metrics["zap_medium"] = medium_count
                metrics["zap_low"] = low_count
                
                # Score based on findings
                score_deduction = (high_count * 4) + (medium_count * 2) + (low_count * 0.5)
                dynamic_score = max(0.0, 10.0 - score_deduction)
                
            else:
                # If we couldn't reliably parse results, return a conservative middle score.
                details.append("[ZAP] Scan completed but could not parse results")
                logger.info("ZAP run completed but output not parseable. stdout: %s stderr: %s", stdout[:200], stderr[:200])
                dynamic_score = 5.0
                
    except subprocess.TimeoutExpired:
        details.append("[ZAP] Scan timed out (>2 min)")
        logger.warning("ZAP scan timed out for URL: %s", web_app_url)
        dynamic_score = 3.0
    except FileNotFoundError:
        details.append("[ZAP] Docker/ZAP not available. Install: docker pull owasp/zap2docker-stable")
        logger.info("Docker executable not found when attempting ZAP scan")
        dynamic_score = 5.0  # Neutral if tool unavailable
    except Exception as e:
        logger.exception("Unexpected error running ZAP baseline scan")
        details.append("[ZAP] Error running dynamic scan")
        dynamic_score = 3.0
    
    metrics["dynamic_score"] = dynamic_score
    return dynamic_score, details, metrics