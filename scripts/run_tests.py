#!/usr/bin/env python3
"""scripts/run_tests.py — Simple test runner for the project.

Usage:
    python scripts/run_tests.py          # Run all tests with verbose output
    python scripts/run_tests.py --fast   # Run tests without coverage
    python scripts/run_tests.py --cov    # Run tests with coverage report
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Run pytest with appropriate options."""
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

    # Base pytest command
    cmd = ["pytest", "tests/", "-v", "--tb=short"]

    # Check for command-line arguments
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--cov":
            cmd.extend(["--cov=src", "--cov-report=html", "--cov-report=term"])
            print("🔍 Running tests with coverage...")
        elif arg == "--fast":
            cmd = ["pytest", "tests/", "-v", "--tb=line"]
            print("⚡ Running tests (fast mode)...")
        elif arg == "--api":
            cmd = ["pytest", "tests/test_api.py", "-v", "--tb=short"]
            print("🔌 Running API tests...")
        else:
            print(f"❓ Unknown option: {arg}")
            print("   Use: --cov (coverage), --fast (fast), --api (API tests only)")
            return 1
    else:
        print("🧪 Running all tests...")

    # Run pytest
    result = subprocess.run(cmd, cwd=str(project_root))
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
