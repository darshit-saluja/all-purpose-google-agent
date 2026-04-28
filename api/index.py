"""Vercel serverless entrypoint for the Flask app.

Vercel's Python runtime looks for a WSGI-compatible object named `app`
(or `handler`) in files under the `api/` directory. This module imports
the Flask application from the project root and exposes it.
"""
import sys
import os

# Ensure the project root is on the Python path so `from app import app` works.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import app  # noqa: F401  – re-exported as the Vercel handler
