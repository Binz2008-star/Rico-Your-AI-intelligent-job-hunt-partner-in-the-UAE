"""
sandbox/indeed_apply_v2/monitoring.py
Comprehensive logging and monitoring for Indeed Apply V2

Features:
- Structured logging with context
- Performance metrics tracking
- Error categorization
- Success rate monitoring
- Alert thresholds
- Log file rotation
"""

import json
import logging
import logging.handlers
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOG_DIR = BASE_DIR / "sandbox" / "indeed_apply_v2" / "logs"
METRICS_FILE = BASE_DIR / "sandbox" / "indeed_apply_v2" / "metrics.json"


@dataclass
class PerformanceMetrics:
    """Performance metrics for a single run."""
    run_id: str
    timestamp: str
    duration_seconds: float
    jobs_scanned: int
    easy_apply_found: int
    title_filtered: int
    applied: int
    failed: int
    skipped: int
    success_rate: float
    avg_apply_time: float
    errors_by_type: Dict[str, int]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MetricsTracker:
    """Track performance metrics across runs."""
    
    def __init__(self, metrics_file: Path = METRICS_FILE) -> None:
        self._metrics_file = metrics_file
        self._current_run: Optional[Dict[str, Any]] = None
        self._history: List[Dict[str, Any]] = []
        self._load_history()
    
    def _load_history(self) -> None:
        """Load historical metrics."""
        try:
            if self._metrics_file.exists():
                with self._metrics_file.open() as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "history" in data:
                        self._history = data["history"][-100:]  # Keep last 100 runs
        except Exception:
            self._history = []
    
    def _save_history(self) -> None:
        """Save historical metrics."""
        try:
            self._metrics_file.parent.mkdir(parents=True, exist_ok=True)
            with self._metrics_file.open("w") as f:
                json.dump({"history": self._history}, f, indent=2)
        except Exception as exc:
            logging.warning("Failed to save metrics: %s", exc)
    
    def start_run(self, run_id: str) -> None:
        """Start tracking a new run."""
        self._current_run = {
            "run_id": run_id,
            "timestamp": datetime.utcnow().isoformat(),
            "start_time": datetime.utcnow().isoformat(),
            "jobs_scanned": 0,
            "easy_apply_found": 0,
            "title_filtered": 0,
            "applied": 0,
            "failed": 0,
            "skipped": 0,
            "errors": {},
            "apply_times": [],
        }
    
    def record_job_scanned(self) -> None:
        """Record a job was scanned."""
        if self._current_run:
            self._current_run["jobs_scanned"] += 1
    
    def record_easy_apply_found(self) -> None:
        """Record an Easy Apply job was found."""
        if self._current_run:
            self._current_run["easy_apply_found"] += 1
    
    def record_title_filtered(self) -> None:
        """Record a job was filtered by title."""
        if self._current_run:
            self._current_run["title_filtered"] += 1
    
    def record_apply(self, success: bool, apply_time: float, error_type: str = "") -> None:
        """Record an apply attempt."""
        if self._current_run:
            if success:
                self._current_run["applied"] += 1
            else:
                self._current_run["failed"] += 1
                if error_type:
                    self._current_run["errors"][error_type] = \
                        self._current_run["errors"].get(error_type, 0) + 1
            self._current_run["apply_times"].append(apply_time)
    
    def record_skipped(self) -> None:
        """Record a job was skipped."""
        if self._current_run:
            self._current_run["skipped"] += 1
    
    def end_run(self) -> Optional[PerformanceMetrics]:
        """End the current run and calculate metrics."""
        if not self._current_run:
            return None
        
        start_time = datetime.fromisoformat(self._current_run["start_time"])
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        apply_times = self._current_run.get("apply_times", [])
        avg_apply_time = sum(apply_times) / len(apply_times) if apply_times else 0
        
        total_attempts = self._current_run["applied"] + self._current_run["failed"]
        success_rate = self._current_run["applied"] / total_attempts if total_attempts > 0 else 1.0
        
        metrics = PerformanceMetrics(
            run_id=self._current_run["run_id"],
            timestamp=self._current_run["timestamp"],
            duration_seconds=duration,
            jobs_scanned=self._current_run["jobs_scanned"],
            easy_apply_found=self._current_run["easy_apply_found"],
            title_filtered=self._current_run["title_filtered"],
            applied=self._current_run["applied"],
            failed=self._current_run["failed"],
            skipped=self._current_run["skipped"],
            success_rate=success_rate,
            avg_apply_time=avg_apply_time,
            errors_by_type=self._current_run["errors"],
        )
        
        self._history.append(metrics.to_dict())
        self._save_history()
        self._current_run = None
        
        return metrics
    
    def get_recent_metrics(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get recent metrics."""
        return self._history[-count:]
    
    def get_success_rate_trend(self, hours: int = 24) -> List[float]:
        """Get success rate trend over time."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        recent = [
            m for m in self._history
            if datetime.fromisoformat(m["timestamp"]) > cutoff
        ]
        return [m["success_rate"] for m in recent]


class IndeedApplyLogger:
    """Structured logger for Indeed Apply V2."""
    
    def __init__(self, log_dir: Path = LOG_DIR, debug: bool = False) -> None:
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger = logging.getLogger("indeed_apply_v2")
        self.logger.setLevel(logging.DEBUG if debug else logging.INFO)
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # File handler with rotation
        log_file = self.log_dir / f"indeed_apply_v2_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        self.metrics = MetricsTracker()
    
    def log_run_start(self, run_id: str, config: Dict[str, Any]) -> None:
        """Log run start with configuration."""
        self.logger.info("=" * 70)
        self.logger.info(f"RUN START: {run_id}")
        self.logger.info("=" * 70)
        self.logger.info(f"Configuration:")
        for key, value in config.items():
            if "password" in key.lower() or "secret" in key.lower():
                self.logger.info(f"  {key}: ***REDACTED***")
            else:
                self.logger.info(f"  {key}: {value}")
        self.metrics.start_run(run_id)
    
    def log_run_end(self, metrics: PerformanceMetrics) -> None:
        """Log run end with metrics."""
        self.logger.info("=" * 70)
        self.logger.info("RUN SUMMARY")
        self.logger.info("=" * 70)
        self.logger.info(f"Duration: {metrics.duration_seconds:.1f}s")
        self.logger.info(f"Jobs Scanned: {metrics.jobs_scanned}")
        self.logger.info(f"Easy Apply Found: {metrics.easy_apply_found}")
        self.logger.info(f"Title Filtered: {metrics.title_filtered}")
        self.logger.info(f"Applied: {metrics.applied}")
        self.logger.info(f"Failed: {metrics.failed}")
        self.logger.info(f"Skipped: {metrics.skipped}")
        self.logger.info(f"Success Rate: {metrics.success_rate:.1%}")
        self.logger.info(f"Avg Apply Time: {metrics.avg_apply_time:.1f}s")
        
        if metrics.errors_by_type:
            self.logger.info("Errors by Type:")
            for error_type, count in metrics.errors_by_type.items():
                self.logger.info(f"  {error_type}: {count}")
        
        self.logger.info("=" * 70)
    
    def log_job_scan(self, role: str, count: int) -> None:
        """Log job scanning for a role."""
        self.logger.info(f"Scanning role: {role}, cards found: {count}")
        self.metrics.record_job_scanned()
    
    def log_easy_apply_card(self, title: str, company: str, score: int) -> None:
        """Log an Easy Apply card found."""
        self.logger.debug(f"Easy Apply card: {title[:50]} @ {company[:30]} (score: {score})")
        self.metrics.record_easy_apply_found()
    
    def log_title_filtered(self, title: str, reason: str) -> None:
        """Log a job filtered by title."""
        self.logger.debug(f"Title filtered: {title[:50]} - {reason}")
        self.metrics.record_title_filtered()
    
    def log_apply_start(self, title: str, company: str) -> None:
        """Log apply attempt start."""
        self.logger.info(f"Applying to: {title[:50]} @ {company[:30]}")
    
    def log_apply_success(self, title: str, apply_time: float) -> None:
        """Log successful apply."""
        self.logger.info(f"✅ Applied successfully: {title[:50]} ({apply_time:.1f}s)")
        self.metrics.record_apply(success=True, apply_time=apply_time)
    
    def log_apply_failure(self, title: str, error_type: str, error_msg: str, apply_time: float) -> None:
        """Log failed apply."""
        self.logger.warning(f"❌ Apply failed: {title[:50]} - {error_type}: {error_msg}")
        self.metrics.record_apply(success=False, apply_time=apply_time, error_type=error_type)
    
    def log_job_skipped(self, title: str, reason: str) -> None:
        """Log skipped job."""
        self.logger.info(f"⏭️  Skipped: {title[:50]} - {reason}")
        self.metrics.record_skipped()
    
    def log_error(self, error_type: str, error_msg: str, context: Dict[str, Any] = None) -> None:
        """Log error with context."""
        self.logger.error(f"Error [{error_type}]: {error_msg}")
        if context:
            self.logger.error(f"Context: {json.dumps(context, indent=2)}")
    
    def log_warning(self, warning_type: str, warning_msg: str) -> None:
        """Log warning."""
        self.logger.warning(f"Warning [{warning_type}]: {warning_msg}")
    
    def log_debug(self, message: str) -> None:
        """Log debug message."""
        self.logger.debug(message)
    
    def get_metrics(self) -> MetricsTracker:
        """Get the metrics tracker."""
        return self.metrics


# Global logger instance
_logger_instance: Optional[IndeedApplyLogger] = None


def get_logger(debug: bool = False) -> IndeedApplyLogger:
    """Get or create the global logger instance."""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = IndeedApplyLogger(debug=debug)
    return _logger_instance


def reset_logger() -> None:
    """Reset the global logger instance."""
    global _logger_instance
    _logger_instance = None
