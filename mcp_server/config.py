import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    base_url: str  # public origin of this server, no trailing slash
    api_url: str  # where the Flask API lives; the same origin on Vercel
    token_secret: str  # signs OAuth clients, codes and tokens; rotate to log everyone out
    service_token: str  # sent to Flask as Authorization: Bearer
    admin_password_hash: str  # the same werkzeug hash the Flask login checks


REQUIRED = {
    "base_url": "APP_BASE_URL",
    "token_secret": "MCP_TOKEN_SECRET",
    "service_token": "MCP_SERVICE_TOKEN",
    "admin_password_hash": "ADMIN_PASSWORD_HASH",
}


def load_config(environ=os.environ):
    missing = [name for name in REQUIRED.values() if not environ.get(name)]
    if missing:
        raise RuntimeError(f"MCP server is missing env vars: {', '.join(missing)}")
    values = {field: environ[name] for field, name in REQUIRED.items()}
    values["base_url"] = values["base_url"].rstrip("/")
    values["api_url"] = (environ.get("SMALL_WINS_API_URL") or values["base_url"]).rstrip("/")
    return Config(**values)
