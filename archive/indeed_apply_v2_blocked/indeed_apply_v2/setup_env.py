"""
sandbox/indeed_apply_v2/setup_env.py
Comprehensive environment setup for Indeed Apply V2

This script:
1. Validates all required dependencies
2. Creates necessary directories
3. Validates environment variables
4. Sets up browser profile
5. Validates CV file
6. Creates configuration files
7. Runs pre-flight checks
"""

import os
import sys
from pathlib import Path
from typing import List, Tuple

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def print_section(title: str) -> None:
    """Print a section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def check_dependencies() -> Tuple[bool, List[str]]:
    """Check if all required dependencies are installed."""
    print_section("CHECKING DEPENDENCIES")
    
    required = {
        'playwright': 'playwright',
        'dotenv': 'python-dotenv',
        'filelock': 'filelock',
    }
    
    optional = {
        'requests': 'requests',
    }
    
    missing = []
    optional_missing = []
    
    for module, package in required.items():
        try:
            __import__(module)
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package} - MISSING")
            missing.append(package)
    
    for module, package in optional.items():
        try:
            __import__(module)
            print(f"  ✅ {package} (optional)")
        except ImportError:
            print(f"  ⚠️  {package} - MISSING (optional)")
            optional_missing.append(package)
    
    if missing:
        print(f"\n❌ Missing required packages: {', '.join(missing)}")
        print(f"   Install with: pip install {' '.join(missing)}")
    
    if optional_missing:
        print(f"\n⚠️  Missing optional packages: {', '.join(optional_missing)}")
        print(f"   Install with: pip install {' '.join(optional_missing)}")
    
    return len(missing) == 0, missing


def create_directories() -> bool:
    """Create necessary directories."""
    print_section("CREATING DIRECTORIES")
    
    base_dir = Path(__file__).resolve().parent.parent.parent
    directories = [
        base_dir / "data",
        base_dir / "data" / "ng_profile_v2",
        base_dir / "sandbox" / "indeed_apply_v2",
        base_dir / "sandbox" / "indeed_apply_v2" / "logs",
        base_dir / "sandbox" / "indeed_apply_v2" / "cache",
    ]
    
    all_created = True
    for directory in directories:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"  ✅ {directory.relative_to(base_dir)}")
        except Exception as exc:
            print(f"  ❌ {directory.relative_to(base_dir)} - {exc}")
            all_created = False
    
    return all_created


def validate_env_variables() -> Tuple[bool, List[str]]:
    """Validate environment variables."""
    print_section("VALIDATING ENVIRONMENT VARIABLES")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    # Required for live apply
    required_live = [
        "INDEED_V2_NAME",
        "INDEED_V2_EMAIL",
        "INDEED_V2_STREET_ADDRESS",
    ]
    
    # Optional but recommended
    optional = [
        "INDEED_V2_PHONE",
        "INDEED_V2_RELEVANT_JOB_TITLE",
        "INDEED_V2_RELEVANT_COMPANY",
    ]
    
    # Configuration
    config = [
        "INDEED_V2_ENABLED",
        "INDEED_V2_DRY_RUN",
        "INDEED_V2_MAX_PER_RUN",
        "INDEED_V2_DAILY_LIMIT",
    ]
    
    missing_required = []
    missing_optional = []
    missing_config = []
    
    for var in required_live:
        value = os.getenv(var)
        if value:
            print(f"  ✅ {var} = {'*' * len(value)}")
        else:
            print(f"  ❌ {var} - MISSING (required for live apply)")
            missing_required.append(var)
    
    for var in optional:
        value = os.getenv(var)
        if value:
            print(f"  ✅ {var} = {'*' * len(value)}")
        else:
            print(f"  ⚠️  {var} - NOT SET (optional)")
            missing_optional.append(var)
    
    for var in config:
        value = os.getenv(var)
        if value:
            print(f"  ✅ {var} = {value}")
        else:
            default = "false" if "ENABLED" in var or "DRY_RUN" in var else "3"
            print(f"  ⚠️  {var} - NOT SET (default: {default})")
            missing_config.append(var)
    
    if missing_required:
        print(f"\n❌ Missing required variables for live apply: {', '.join(missing_required)}")
        print(f"   Add these to your .env file")
    
    return len(missing_required) == 0, missing_required


def validate_cv_file() -> bool:
    """Validate CV file exists."""
    print_section("VALIDATING CV FILE")
    
    base_dir = Path(__file__).resolve().parent.parent.parent
    cv_path = base_dir / os.getenv("CV_PATH", "data/cv.pdf")
    
    if cv_path.exists():
        size = cv_path.stat().st_size
        print(f"  ✅ CV file found: {cv_path.relative_to(base_dir)}")
        print(f"     Size: {size / 1024:.1f} KB")
        return True
    else:
        print(f"  ❌ CV file not found: {cv_path.relative_to(base_dir)}")
        print(f"     Place your CV at: {cv_path}")
        return False


def setup_playwright() -> bool:
    """Setup Playwright browsers."""
    print_section("SETTING UP PLAYWRIGHT")
    
    try:
        import subprocess
        print("  Installing Playwright browsers...")
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            print("  ✅ Playwright browsers installed")
            return True
        else:
            print(f"  ❌ Playwright installation failed: {result.stderr}")
            return False
    except Exception as exc:
        print(f"  ❌ Playwright setup error: {exc}")
        return False


def create_config_files() -> bool:
    """Create configuration files."""
    print_section("CREATING CONFIGURATION FILES")
    
    base_dir = Path(__file__).resolve().parent.parent.parent
    
    # Create example .env file if not exists
    env_example = base_dir / ".env.example"
    if not env_example.exists():
        try:
            env_content = """# Indeed Apply V2 Configuration

# Core Settings
INDEED_V2_ENABLED=false
INDEED_V2_DRY_RUN=true
INDEED_V2_HEADLESS=false
INDEED_V2_DEBUG=false

# Rate Limiting
INDEED_V2_MAX_PER_RUN=3
INDEED_V2_DAILY_LIMIT=15
INDEED_V2_COOLDOWN_SECONDS=120
INDEED_V2_MAX_RETRIES=2

# Anti-Detection
INDEED_V2_SLOW_MO=800
INDEED_V2_MAX_JOB_AGE_DAYS=14

# Scoring
INDEED_V2_SCORE_THRESHOLD=0

# Profile Data (Required for Live Apply)
INDEED_V2_NAME=Your Full Name
INDEED_V2_EMAIL=your.email@example.com
INDEED_V2_PHONE=
INDEED_V2_STREET_ADDRESS=Your Street Address, City, Country
INDEED_V2_RELEVANT_JOB_TITLE=Your Current Job Title
INDEED_V2_RELEVANT_COMPANY=Your Current Company

# Paths
NG_PROFILE_DIR=data/ng_profile_v2
CV_PATH=data/cv.pdf
INDEED_V2_SKIP_COMPANIES=
"""
            env_example.write_text(env_content)
            print(f"  ✅ Created .env.example")
        except Exception as exc:
            print(f"  ❌ Failed to create .env.example: {exc}")
            return False
    else:
        print(f"  ✅ .env.example already exists")
    
    # Create rate file
    rate_file = base_dir / "sandbox" / "indeed_apply_v2" / "rate.json"
    if not rate_file.exists():
        try:
            rate_file.write_text('{"date": "", "count": 0, "last_apply": null}')
            print(f"  ✅ Created rate.json")
        except Exception as exc:
            print(f"  ❌ Failed to create rate.json: {exc}")
            return False
    else:
        print(f"  ✅ rate.json already exists")
    
    return True


def run_preflight_checks() -> Tuple[bool, List[str]]:
    """Run pre-flight checks."""
    print_section("RUNNING PRE-FLIGHT CHECKS")
    
    issues = []
    
    # Check if we can import the module
    try:
        from sandbox.indeed_apply_v2.indeed_apply_v2 import IndeedApplyEngineV2
        print("  ✅ Can import IndeedApplyEngineV2")
    except ImportError as exc:
        print(f"  ❌ Cannot import IndeedApplyEngineV2: {exc}")
        issues.append("Import error")
    
    # Check if we can import scoring
    try:
        from src.scoring import score_job
        print("  ✅ Can import score_job")
    except ImportError as exc:
        print(f"  ⚠️  Cannot import score_job: {exc}")
        issues.append("Scoring module unavailable")
    
    # Check if we can import applications
    try:
        from src.applications import is_applied, mark_applied
        print("  ✅ Can import applications module")
    except ImportError as exc:
        print(f"  ⚠️  Cannot import applications module: {exc}")
        issues.append("Applications module unavailable")
    
    # Check if we can import LLM scorer
    try:
        from src.llm_scorer import get_llm_response
        print("  ✅ Can import LLM scorer")
    except ImportError as exc:
        print(f"  ⚠️  Cannot import LLM scorer: {exc}")
        issues.append("LLM scorer unavailable")
    
    return len(issues) == 0, issues


def print_summary(results: dict) -> None:
    """Print setup summary."""
    print_section("SETUP SUMMARY")
    
    all_passed = True
    
    for check, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} - {check}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 70)
    if all_passed:
        print("  ✅ ALL CHECKS PASSED - READY FOR TESTING")
        print("=" * 70)
        print("\nNext steps:")
        print("  1. Add your profile data to .env file")
        print("  2. Place your CV at data/cv.pdf")
        print("  3. Run: python sandbox/indeed_apply_v2/test_v2.py --dry-run")
        print("  4. If dry-run passes, run: python sandbox/indeed_apply_v2/test_v2.py --live --max 1")
    else:
        print("  ❌ SOME CHECKS FAILED - FIX ISSUES BEFORE TESTING")
        print("=" * 70)
        print("\nPlease fix the failed checks above before proceeding.")


def main():
    """Run complete environment setup."""
    print("\n" + "=" * 70)
    print("  INDEED APPLY V2 - ENVIRONMENT SETUP")
    print("=" * 70)
    
    results = {}
    
    # Check dependencies
    deps_ok, _ = check_dependencies()
    results["Dependencies"] = deps_ok
    
    # Create directories
    dirs_ok = create_directories()
    results["Directories"] = dirs_ok
    
    # Validate environment variables
    env_ok, _ = validate_env_variables()
    results["Environment Variables"] = env_ok
    
    # Validate CV file
    cv_ok = validate_cv_file()
    results["CV File"] = cv_ok
    
    # Setup Playwright
    playwright_ok = setup_playwright()
    results["Playwright"] = playwright_ok
    
    # Create config files
    config_ok = create_config_files()
    results["Config Files"] = config_ok
    
    # Run pre-flight checks
    preflight_ok, _ = run_preflight_checks()
    results["Pre-flight Checks"] = preflight_ok
    
    # Print summary
    print_summary(results)
    
    # Return exit code
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
