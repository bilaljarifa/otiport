# -*- coding: utf-8 -*-
"""Ensures `backend` (and other top-level Optiport packages) import cleanly
regardless of the directory pytest is invoked from."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
