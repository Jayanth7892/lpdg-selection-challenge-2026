#!/usr/bin/env python3
"""Top-level entrypoint for LPDG Gateway Prediction Service.

Executes the robust gateway ranking pipeline:
    python run.py --data data --out predictions.csv
"""

import sys
from pathlib import Path

# Ensure src is in python path
here = Path(__file__).resolve().parent
sys.path.insert(0, str(here))

from src.predictor import main

if __name__ == "__main__":
    raise SystemExit(main())
