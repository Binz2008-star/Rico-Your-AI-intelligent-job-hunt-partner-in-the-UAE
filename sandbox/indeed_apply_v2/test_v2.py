"""
sandbox/indeed_apply_v2/test_v2.py
Test script for Indeed Apply V2

Usage:
    python test_v2.py --dry-run          # Test scanning only
    python test_v2.py --dry-run --debug  # Test with debug logging
    python test_v2.py --max 1            # Test with 1 application
"""

import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from sandbox.indeed_apply_v2.indeed_apply_v2 import (
    IndeedApplyEngineV2,
    INDEED_V2_ENABLED,
    INDEED_V2_DRY_RUN,
    INDEED_V2_MAX_PER_RUN,
)


def setup_logging(debug: bool = False) -> None:
    """Setup logging configuration."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def test_dry_run(engine: IndeedApplyEngineV2) -> bool:
    """Test dry run mode (scanning only)."""
    print("\n" + "=" * 70)
    print("TEST: DRY RUN MODE")
    print("=" * 70)
    
    try:
        results = engine.run(dry_run=True, max_applies=10)
        print(f"\n✅ Dry run completed successfully")
        print(f"   Jobs found: {len(results)}")
        return True
    except Exception as exc:
        print(f"\n❌ Dry run failed: {exc}")
        import traceback
        traceback.print_exc()
        return False


def test_live_apply(engine: IndeedApplyEngineV2, max_applies: int = 1) -> bool:
    """Test live apply mode."""
    print("\n" + "=" * 70)
    print(f"TEST: LIVE APPLY MODE (max {max_applies} applications)")
    print("=" * 70)
    
    if not INDEED_V2_ENABLED:
        print("\n⚠️  INDEED_V2_ENABLED is false")
        print("   Set INDEED_V2_ENABLED=true in .env to test live applies")
        return False
    
    try:
        results = engine.run(dry_run=False, max_applies=max_applies)
        
        print(f"\n✅ Live apply completed")
        print(f"   Total results: {len(results)}")
        
        success_count = sum(1 for r in results if r.status.value == "success")
        print(f"   Successful: {success_count}")
        
        for r in results:
            print(f"   - {r.status.value}: {r.title[:40]}")
        
        return success_count > 0
    except Exception as exc:
        print(f"\n❌ Live apply failed: {exc}")
        import traceback
        traceback.print_exc()
        return False


def test_profile_validation() -> bool:
    """Test profile data validation."""
    print("\n" + "=" * 70)
    print("TEST: PROFILE DATA VALIDATION")
    print("=" * 70)
    
    from sandbox.indeed_apply_v2.indeed_apply_v2 import (
        _validate_profile_data,
        INDEED_V2_NAME,
        INDEED_V2_EMAIL,
        INDEED_V2_STREET_ADDRESS,
    )
    
    valid, missing = _validate_profile_data()
    
    print(f"\nProfile Data Status:")
    print(f"  Name: {'✅ Set' if INDEED_V2_NAME else '❌ Missing'}")
    print(f"  Email: {'✅ Set' if INDEED_V2_EMAIL else '❌ Missing'}")
    print(f"  Address: {'✅ Set' if INDEED_V2_STREET_ADDRESS else '❌ Missing'}")
    
    if valid:
        print(f"\n✅ All required profile data is set")
        return True
    else:
        print(f"\n❌ Missing required data: {', '.join(missing)}")
        return False


def test_selectors(engine: IndeedApplyEngineV2) -> bool:
    """Test selector detection on Indeed homepage."""
    print("\n" + "=" * 70)
    print("TEST: SELECTOR DETECTION")
    print("=" * 70)
    
    try:
        from sandbox.indeed_apply_v2.indeed_apply_v2 import INDEED_BASE, _S
        
        engine._page.goto(INDEED_BASE, wait_until="domcontentloaded", timeout=30_000)
        
        # Test basic selectors
        tests = [
            ("Job Card", _S.JOB_CARD),
            ("Title", _S.TITLE),
            ("Company", _S.COMPANY),
        ]
        
        results = []
        for name, selector in tests:
            try:
                count = engine._page.locator(selector).count()
                status = "✅" if count > 0 else "⚠️ "
                results.append(f"{status} {name}: {count} elements")
            except Exception as exc:
                results.append(f"❌ {name}: {exc}")
        
        print("\nSelector Test Results:")
        for result in results:
            print(f"  {result}")
        
        return all("✅" in r for r in results)
    except Exception as exc:
        print(f"\n❌ Selector test failed: {exc}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="Test Indeed Apply V2")
    parser.add_argument("--dry-run", action="store_true", help="Test dry run mode")
    parser.add_argument("--live", action="store_true", help="Test live apply mode")
    parser.add_argument("--max", type=int, default=1, help="Max applications for live test")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--profile-only", action="store_true", help="Test profile validation only")
    parser.add_argument("--selectors-only", action="store_true", help="Test selector detection only")
    
    args = parser.parse_args()
    
    setup_logging(args.debug)
    
    print("\n" + "=" * 70)
    print("INDEED APPLY V2 - TEST SUITE")
    print("=" * 70)
    
    # Profile validation test
    if not args.selectors_only:
        profile_ok = test_profile_validation()
        if args.profile_only:
            return
    
    # Selector test
    if args.selectors_only or (not args.dry_run and not args.live):
        with IndeedApplyEngineV2() as engine:
            selectors_ok = test_selectors(engine)
        if args.selectors_only:
            return
    
    # Dry run test
    if args.dry_run or (not args.live and not args.selectors_only and not args.profile_only):
        with IndeedApplyEngineV2() as engine:
            dry_run_ok = test_dry_run(engine)
    
    # Live apply test
    if args.live:
        if not profile_ok:
            print("\n⚠️  Skipping live test - profile data incomplete")
            return
        with IndeedApplyEngineV2() as engine:
            live_ok = test_live_apply(engine, max_applies=args.max)
    
    print("\n" + "=" * 70)
    print("TEST SUITE COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    main()
