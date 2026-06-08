#!/usr/bin/env python3
"""Run real subset test against local backend"""
import os
import sys

# Set env var BEFORE importing the test module
os.environ["RICO_API_BASE_URL"] = "http://127.0.0.1:8000"

print(f"Testing against: {os.environ['RICO_API_BASE_URL']}")

# Import and run the test
sys.path.insert(0, 'tests/evaluation')
from run_real_subset import main

if __name__ == "__main__":
    main()
