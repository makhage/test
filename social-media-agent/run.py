#!/usr/bin/env python3
"""Launch the Social Agent dashboard."""

import subprocess
import sys
from pathlib import Path

dashboard = Path(__file__).parent / "src" / "social_agent" / "dashboard" / "app.py"
subprocess.run([sys.executable, "-m", "streamlit", "run", str(dashboard), "--server.headless=true"])
