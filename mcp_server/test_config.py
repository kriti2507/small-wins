import pytest

from config import load_config

ENV = {
    "APP_BASE_URL": "https://sw.example.com/",
    "MCP_TOKEN_SECRET": "tok",
    "MCP_SERVICE_TOKEN": "svc",
    "ADMIN_PASSWORD_HASH": "hash",
}


def test_load_config_reads_env_and_strips_trailing_slash():
    config = load_config(ENV)
    assert config.base_url == "https://sw.example.com"
    assert config.api_url == "https://sw.example.com"
    assert (config.token_secret, config.service_token, config.admin_password_hash) == ("tok", "svc", "hash")


def test_api_url_can_point_somewhere_else_for_local_dev():
    config = load_config({**ENV, "SMALL_WINS_API_URL": "http://localhost:5000/"})
    assert config.api_url == "http://localhost:5000"


def test_load_config_names_every_missing_var():
    with pytest.raises(RuntimeError) as err:
        load_config({"APP_BASE_URL": "https://sw.example.com"})
    for name in ("MCP_TOKEN_SECRET", "MCP_SERVICE_TOKEN", "ADMIN_PASSWORD_HASH"):
        assert name in str(err.value)
