import pytest

import auth


# --- is_allowed ----------------------------------------------------------------

def test_is_allowed_matches_the_list_case_and_space_insensitively(monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAILS", " Me@Example.com , friend@example.com ")
    assert auth.is_allowed("me@example.com")
    assert auth.is_allowed("ME@example.COM")
    assert auth.is_allowed("friend@example.com")
    assert not auth.is_allowed("stranger@example.com")


def test_is_allowed_refuses_everyone_when_unset_or_blank(monkeypatch):
    monkeypatch.delenv("ALLOWED_EMAILS", raising=False)
    assert not auth.is_allowed("me@example.com")
    monkeypatch.setenv("ALLOWED_EMAILS", " , ")
    assert not auth.is_allowed("")


# --- safe_next -----------------------------------------------------------------

@pytest.mark.parametrize("value", ["/", "/topic/runs", "/topic/runs/entry/3?x=1",
                                   "/oauth/login?req=abc"])
def test_safe_next_keeps_same_site_paths(value):
    assert auth.safe_next(value) == value


@pytest.mark.parametrize("value", [None, "", "topic", "//evil.com", "https://evil.com",
                                   "/\\evil.com", "\\\\evil.com", 42])
def test_safe_next_replaces_anything_else_with_root(value):
    assert auth.safe_next(value) == "/"


# --- check_config ----------------------------------------------------------------

def test_check_config_refuses_dev_login_on_vercel():
    with pytest.raises(RuntimeError, match="DEV_LOGIN_EMAIL"):
        auth.check_config({"DEV_LOGIN_EMAIL": "me@example.com", "VERCEL": "1"}, "s3cret")


def test_check_config_requires_a_real_secret_with_google():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        auth.check_config({"GOOGLE_CLIENT_ID": "cid"}, auth.DEV_SECRET)


def test_check_config_accepts_dev_and_production_setups():
    auth.check_config({"DEV_LOGIN_EMAIL": "me@example.com"}, auth.DEV_SECRET)
    auth.check_config({"GOOGLE_CLIENT_ID": "cid", "VERCEL": "1"}, "s3cret")
    auth.check_config({}, auth.DEV_SECRET)
