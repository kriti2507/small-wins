import io
import urllib.error

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


def http_error(status, body=b""):
    return urllib.error.HTTPError("u", status, "err", {}, io.BytesIO(body))


def test_image_path_and_user_key_round_trip():
    assert storage.image_path_for("users/7/abc.jpg") == "/api/images/users/7/abc.jpg"
    assert storage.user_key("users/7/abc.jpg", 7) == "users/7/abc.jpg"


@pytest.mark.parametrize("key", [
    "users/8/abc.jpg",          # another user
    "users/70/abc.jpg",         # prefix of a longer id must not match
    "abc.jpg",                  # outside users/
    "users/7/",                 # empty name
    "users/7/a/b.jpg",          # nested
    "users/7/../8/abc.jpg",     # traversal
    "users/7/%2e%2e.jpg",       # encoded
    "users/7/a.jpg?x=1",
    "users/7/a.jpg#x",
    "users/7/.",                # a lone "."
    "users/7/a b.jpg",          # space
    "users/7/a\\b.jpg",         # backslash
    "users/7/é.jpg",            # non-ASCII
    "users/7/.hidden",          # leading dot
    "",
    None,
])
def test_user_key_refuses_anything_else(key):
    assert storage.user_key(key, 7) is None


def test_user_key_refuses_a_missing_user_id():
    assert storage.user_key("users/None/x.jpg", None) is None


def test_thumb_name_for_swaps_the_extension():
    assert storage.thumb_name_for("users/7/abc.jpg") == "users/7/abc.thumb"
    assert storage.thumb_name_for("users/7/abc") == "users/7/abc.thumb"


def test_signed_read_url_signs_and_absolutizes(monkeypatch):
    calls = {}

    def fake_urlopen(req):
        calls["url"] = req.full_url
        calls["method"] = req.get_method()
        calls["auth"] = req.get_header("Authorization")
        calls["data"] = req.data
        return FakeResp(b'{"signedURL": "/object/sign/uploads/users/7/a.jpg?token=t"}')

    monkeypatch.setattr(storage.urllib.request, "urlopen", fake_urlopen)

    url = storage.signed_read_url("users/7/a.jpg", 3600)

    assert calls["url"] == "https://proj.supabase.co/storage/v1/object/sign/uploads/users/7/a.jpg"
    assert calls["method"] == "POST"
    assert calls["auth"] == "Bearer svc"
    assert calls["data"] == b'{"expiresIn": 3600}'
    assert url == "https://proj.supabase.co/storage/v1/object/sign/uploads/users/7/a.jpg?token=t"


@pytest.mark.parametrize("err", [
    pytest.param(lambda: http_error(404), id="404"),
    # Supabase Storage reports a missing object as HTTP 400 with this body.
    pytest.param(lambda: http_error(
        400, b'{"statusCode":"404","error":"not_found","message":"Object not found"}'),
        id="400-not-found-body"),
])
def test_signed_read_url_raises_not_found_for_a_missing_object(monkeypatch, err):
    def fake_urlopen(req):
        raise err()
    monkeypatch.setattr(storage.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(storage.NotFound):
        storage.signed_read_url("users/7/a.thumb", 3600)


@pytest.mark.parametrize("err", [
    pytest.param(lambda: http_error(500, b"boom"), id="500"),
    # statusCode isn't "404" and error isn't "not_found" - a real client error.
    pytest.param(lambda: http_error(
        400, b'{"statusCode":"400","error":"InvalidKey"}'), id="400-other-error"),
    # Valid JSON but not an object - can't be mistaken for a not-found body.
    pytest.param(lambda: http_error(400, b"null"), id="400-json-null-body"),
    # Not JSON at all.
    pytest.param(lambda: http_error(400, b"oops"), id="400-non-json-body"),
])
def test_signed_read_url_lets_other_errors_through(monkeypatch, err):
    def fake_urlopen(req):
        raise err()
    monkeypatch.setattr(storage.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(urllib.error.HTTPError) as exc:
        storage.signed_read_url("users/7/a.jpg", 3600)
    assert not isinstance(exc.value, storage.NotFound)


def test_delete_object_raises_not_found_for_a_missing_object(monkeypatch):
    def fake_urlopen(req):
        raise http_error(400, b'{"statusCode":"404","error":"not_found"}')
    monkeypatch.setattr(storage.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(storage.NotFound):
        storage.delete_object("users/7/a.thumb")


def test_download_returns_bytes_and_content_type(monkeypatch):
    calls = {}

    class Resp(FakeResp):
        headers = {"Content-Type": "image/png"}

    def fake_urlopen(req):
        calls["url"] = req.full_url
        calls["auth"] = req.get_header("Authorization")
        return Resp(b"png-bytes")

    monkeypatch.setattr(storage.urllib.request, "urlopen", fake_urlopen)

    assert storage.download("abc.png") == (b"png-bytes", "image/png")
    assert calls["url"] == "https://proj.supabase.co/storage/v1/object/uploads/abc.png"
    assert calls["auth"] == "Bearer svc"


def test_upload_bytes_sends_cache_control_when_given(monkeypatch):
    seen = {}

    def fake_urlopen(req):
        seen["cache"] = req.get_header("Cache-control")
        return FakeResp()

    monkeypatch.setattr(storage.urllib.request, "urlopen", fake_urlopen)
    storage.upload_bytes("users/7/a.jpg", b"x", "image/jpeg", cache_control="max-age=31536000")
    assert seen["cache"] == "max-age=31536000"


def test_upload_bytes_sends_no_cache_control_when_not_given(monkeypatch):
    seen = {}

    def fake_urlopen(req):
        seen["cache"] = req.get_header("Cache-control")
        return FakeResp()

    monkeypatch.setattr(storage.urllib.request, "urlopen", fake_urlopen)
    storage.upload_bytes("users/7/a.jpg", b"x", "image/jpeg")
    assert seen["cache"] is None
