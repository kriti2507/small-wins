import pytest

import storage


@pytest.fixture(autouse=True)
def storage_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "svc")
    monkeypatch.setenv("SUPABASE_BUCKET", "uploads")


class FakeResp:
    def __init__(self, body=b""):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_upload_bytes_posts_and_returns_public_url(monkeypatch):
    calls = {}

    def fake_urlopen(req):
        calls["url"] = req.full_url
        calls["auth"] = req.get_header("Authorization")
        calls["ctype"] = req.get_header("Content-type")
        calls["data"] = req.data
        return FakeResp()

    monkeypatch.setattr(storage.urllib.request, "urlopen", fake_urlopen)

    url = storage.upload_bytes("abc.png", b"binary-data", "image/png")

    assert calls["url"] == "https://proj.supabase.co/storage/v1/object/uploads/abc.png"
    assert calls["auth"] == "Bearer svc"
    assert calls["ctype"] == "image/png"
    assert calls["data"] == b"binary-data"
    assert url == "https://proj.supabase.co/storage/v1/object/public/uploads/abc.png"


def test_delete_object_issues_delete_with_auth_headers(monkeypatch):
    calls = {}

    def fake_urlopen(req):
        calls["url"] = req.full_url
        calls["method"] = req.get_method()
        calls["auth"] = req.get_header("Authorization")
        calls["apikey"] = req.get_header("Apikey")
        return FakeResp()

    monkeypatch.setattr(storage.urllib.request, "urlopen", fake_urlopen)

    storage.delete_object("abc.png")

    assert calls["url"] == "https://proj.supabase.co/storage/v1/object/uploads/abc.png"
    assert calls["method"] == "DELETE"
    assert calls["auth"] == "Bearer svc"
    assert calls["apikey"] == "svc"


def test_signed_upload_url_absolutizes_the_relative_url_supabase_returns(monkeypatch):
    calls = {}

    def fake_urlopen(req):
        calls["url"] = req.full_url
        calls["method"] = req.get_method()
        calls["auth"] = req.get_header("Authorization")
        calls["apikey"] = req.get_header("Apikey")
        calls["data"] = req.data
        return FakeResp(
            b'{"url": "/object/upload/sign/uploads/abc.png?token=eyJhbG"}'
        )

    monkeypatch.setattr(storage.urllib.request, "urlopen", fake_urlopen)

    url = storage.signed_upload_url("abc.png", expires_in=600)

    assert calls["url"] == (
        "https://proj.supabase.co/storage/v1/object/upload/sign/uploads/abc.png"
    )
    assert calls["method"] == "POST"
    assert calls["auth"] == "Bearer svc"
    assert calls["apikey"] == "svc"
    assert calls["data"] == b'{"expiresIn": 600}'
    # Supabase returns a path relative to /storage/v1; the browser needs it whole.
    assert url == (
        "https://proj.supabase.co/storage/v1"
        "/object/upload/sign/uploads/abc.png?token=eyJhbG"
    )


def test_signed_upload_url_rejects_a_response_without_a_url(monkeypatch):
    monkeypatch.setattr(storage.urllib.request, "urlopen",
                        lambda req: FakeResp(b'{"error": "Bucket not found"}'))
    with pytest.raises(KeyError):
        storage.signed_upload_url("abc.png")


def test_public_url_for_matches_what_upload_bytes_returns(monkeypatch):
    monkeypatch.setattr(storage.urllib.request, "urlopen", lambda req: FakeResp())
    assert storage.public_url_for("abc.png") == storage.upload_bytes(
        "abc.png", b"x", "image/png"
    )


def test_public_url_for_round_trips_through_object_name_for():
    assert storage.object_name_for(storage.public_url_for("abc.png")) == "abc.png"


def test_object_name_for_returns_key_for_matching_bucket_url():
    url = "https://proj.supabase.co/storage/v1/object/public/uploads/abc.png"
    assert storage.object_name_for(url) == "abc.png"


def test_object_name_for_round_trips_with_upload_bytes(monkeypatch):
    monkeypatch.setattr(storage.urllib.request, "urlopen", lambda req: FakeResp())
    url = storage.upload_bytes("abc.png", b"x", "image/png")
    assert storage.object_name_for(url) == "abc.png"


@pytest.mark.parametrize(
    "url",
    [
        pytest.param(None, id="none"),
        pytest.param("", id="empty-string"),
        pytest.param(
            "https://evil.example.com/storage/v1/object/public/uploads/abc.png",
            id="different-host",
        ),
        pytest.param(
            "https://proj.supabase.co/some/other/path/abc.png",
            id="same-host-wrong-path",
        ),
        pytest.param(
            "https://proj.supabase.co/storage/v1/object/public/uploads-archive/a.png",
            id="bucket-prefix-confusion",
        ),
        pytest.param(
            "https://proj.supabase.co/storage/v1/object/public/other-bucket/a.png",
            id="wrong-bucket",
        ),
        pytest.param(
            "https://proj.supabase.co/storage/v1/object/uploads/a.png",
            id="authenticated-not-public-path",
        ),
        pytest.param(
            "https://proj.supabase.co/storage/v1/object/public/uploads/../../x.png",
            id="dot-dot-traversal",
        ),
        pytest.param(
            "https://proj.supabase.co/storage/v1/object/public/uploads/%2e%2e%2fx.png",
            id="percent-encoded-traversal",
        ),
        pytest.param(
            "https://proj.supabase.co/storage/v1/object/public/uploads/",
            id="empty-key",
        ),
        pytest.param(
            "https://proj.supabase.co/storage/v1/object/public/uploads/a.png?download=1",
            id="query-string-appended",
        ),
    ],
)
def test_object_name_for_returns_none(url):
    assert storage.object_name_for(url) is None
