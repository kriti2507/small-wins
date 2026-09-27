import os
import sys

# The MCP server lives in mcp_server/; make it importable from this function.
# (Not named mcp.py: that would shadow the `mcp` SDK package.)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp_server"))

from config import load_config  # noqa: E402
from mcp_app import create_app  # noqa: E402

app = create_app(load_config())  # Vercel's Python runtime serves the ASGI `app`
