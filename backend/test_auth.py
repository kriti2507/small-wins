import pytest

import auth


# --- safe_next -----------------------------------------------------------------

@pytest.mark.parametrize("value", ["/", "/topic/runs", "/topic/runs/entry/3?x=1",
                                   "/oauth/login?req=abc"])
def test_safe_next_keeps_same_site_paths(value):
    assert auth.safe_next(value) == value


@pytest.mark.parametrize("value", [None, "", "topic", "//evil.com", "https://evil.com",
                                   "/\\evil.com", "\\\\evil.com", 42,
                                   "/\t/evil.com", "/x\ny"])
def test_safe_next_replaces_anything_else_with_root(value):
    assert auth.safe_next(value) == "/"


# --- check_config ----------------------------------------------------------------

def test_check_config_requires_a_real_secret_with_google():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        auth.check_config({"GOOGLE_CLIENT_ID": "cid"}, auth.DEV_SECRET)


def test_check_config_requires_a_real_secret_on_vercel():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        auth.check_config({"VERCEL": "1"}, auth.DEV_SECRET)


def test_check_config_accepts_dev_and_production_setups():
    auth.check_config({"GOOGLE_CLIENT_ID": "cid", "VERCEL": "1"}, "s3cret")
    auth.check_config({}, auth.DEV_SECRET)


# --- Google sign-in routes -----------------------------------------------------

from authlib.integrations.base_client import OAuthError  # noqa: E402
from flask import redirect  # noqa: E402

GOOGLE_USER = {"sub": "g-123", "email": "Me@Example.com", "email_verified": True,
               "name": "Me", "picture": "https://pic/me"}


class FakeGoogle:
    def __init__(self):
        self.user = dict(GOOGLE_USER)
        self.error = None
        self.redirect_uris = []


@pytest.fixture()
def google(monkeypatch):
    """Stands in for Google. Tests never make network calls."""
    fake = FakeGoogle()
    client = auth.oauth.google

    def authorize_redirect(redirect_uri, **kwargs):
        fake.redirect_uris.append(redirect_uri)
        return redirect("https://accounts.google.com/o/oauth2/v2/auth?fake=1")

    def authorize_access_token(**kwargs):
        if fake.error:
            raise fake.error
        return {"userinfo": fake.user}

    monkeypatch.setattr(client, "authorize_redirect", authorize_redirect)
    monkeypatch.setattr(client, "authorize_access_token", authorize_access_token)
    return fake


def sign_in(c, next_path="/topic/runs"):
    c.get("/api/auth/google", query_string={"next": next_path})
    return c.get("/api/auth/google/callback?code=x&state=y")


def test_google_login_sends_you_to_google_with_our_callback(db_anon_client, google):
    res = db_anon_client.get("/api/auth/google?next=/topic/runs")
    assert res.status_code == 302
    assert res.headers["Location"].startswith("https://accounts.google.com/")
    assert google.redirect_uris == ["http://localhost/api/auth/google/callback"]


def test_callback_signs_in_a_verified_user_and_returns_to_next(db_anon_client, google):
    res = sign_in(db_anon_client)
    assert res.status_code == 302
    assert res.headers["Location"] == "/topic/runs"
    user = db_anon_client.get("/api/auth/me").get_json()["user"]
    assert user["email"] == "me@example.com"  # lowercased
    assert (user["name"], user["avatar_url"]) == ("Me", "https://pic/me")
    assert db_anon_client.get("/api/topics").status_code == 200


def test_signing_in_again_updates_the_profile_without_a_duplicate(db_anon_client, google):
    sign_in(db_anon_client)
    first = db_anon_client.get("/api/auth/me").get_json()["user"]
    google.user["name"] = "Me Renamed"
    sign_in(db_anon_client)
    again = db_anon_client.get("/api/auth/me").get_json()["user"]
    assert again["id"] == first["id"]
    assert again["name"] == "Me Renamed"


def test_unverified_email_is_refused(db_anon_client, google):
    google.user["email_verified"] = False
    res = sign_in(db_anon_client)
    assert res.headers["Location"] == "/login?error=unverified"
    assert db_anon_client.get("/api/auth/me").status_code == 401


def test_missing_email_is_refused(db_anon_client, google):
    google.user["email"] = ""
    res = sign_in(db_anon_client)
    assert res.headers["Location"] == "/login?error=unverified"
    assert db_anon_client.get("/api/auth/me").status_code == 401


def test_any_verified_google_account_can_sign_in(db_anon_client, google):
    google.user.update(sub="g-stranger", email="Stranger@Example.com")
    res = sign_in(db_anon_client)
    assert res.headers["Location"] == "/topic/runs"
    user = db_anon_client.get("/api/auth/me").get_json()["user"]
    assert user["email"] == "stranger@example.com"


def test_cancelled_or_broken_google_sign_in_reports_failure(db_anon_client, google):
    google.error = OAuthError(error="access_denied")
    res = sign_in(db_anon_client)
    assert res.headers["Location"] == "/login?error=failed"
    assert db_anon_client.get("/api/auth/me").status_code == 401


def test_bad_id_token_claims_report_failure(db_anon_client, google):
    from joserfc.errors import ExpiredTokenError
    google.error = ExpiredTokenError("exp")
    res = sign_in(db_anon_client)
    assert res.headers["Location"] == "/login?error=failed"
    assert db_anon_client.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize("bad", ["//evil.com", "https://evil.com", "/\\evil.com", "evil"])
def test_unsafe_next_falls_back_to_root(db_anon_client, google, bad):
    assert sign_in(db_anon_client, bad).headers["Location"] == "/"


def test_a_leftover_dev_login_setting_no_longer_skips_google(db_anon_client, google, monkeypatch):
    monkeypatch.setenv("DEV_LOGIN_EMAIL", "dev@example.com")
    res = db_anon_client.get("/api/auth/google?next=/topic/runs")
    assert res.headers["Location"].startswith("https://accounts.google.com/")
    assert db_anon_client.get("/api/auth/me").status_code == 401
