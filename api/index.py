"""
CloudFormation Accelerator - Vercel Serverless Entry Point

This file adapts the Flask app for Vercel's serverless platform.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from web.app import app

# Vercel expects the Flask app as 'app'
app = app
