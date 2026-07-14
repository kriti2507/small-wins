import os
import sys

# The Flask app lives in backend/; make it importable from this function.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app import app  # noqa: E402  — Vercel's @vercel/python serves the WSGI `app`
