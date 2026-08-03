def test_upload_bytes_posts_and_returns_public_url(monkeypatch):
    import storage
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "svc")
    monkeypatch.setenv("SUPABASE_BUCKET", "uploads")

    calls = {}

    class FakeResp:
        def read(self):
            return b""

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

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
    import storage
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "svc")
    monkeypatch.setenv("SUPABASE_BUCKET", "uploads")

    calls = {}

    class FakeResp:
        def read(self):
            return b""

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

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


def test_object_name_for_returns_key_for_matching_bucket_url(monkeypatch):
    import storage
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "svc")
    monkeypatch.setenv("SUPABASE_BUCKET", "uploads")

    url = "https://proj.supabase.co/storage/v1/object/public/uploads/abc.png"
    assert storage.object_name_for(url) == "abc.png"


def test_object_name_for_returns_none_for_external_url(monkeypatch):
    import storage
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "svc")
    monkeypatch.setenv("SUPABASE_BUCKET", "uploads")

    url = "https://evil.example.com/storage/v1/object/public/uploads/abc.png"
    assert storage.object_name_for(url) is None


def test_object_name_for_returns_none_for_same_host_wrong_path(monkeypatch):
    import storage
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "svc")
    monkeypatch.setenv("SUPABASE_BUCKET", "uploads")

    url = "https://proj.supabase.co/some/other/path/abc.png"
    assert storage.object_name_for(url) is None


def test_object_name_for_returns_none_for_empty_string(monkeypatch):
    import storage
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "svc")
    monkeypatch.setenv("SUPABASE_BUCKET", "uploads")

    assert storage.object_name_for("") is None


def test_object_name_for_returns_none_for_none(monkeypatch):
    import storage
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "svc")
    monkeypatch.setenv("SUPABASE_BUCKET", "uploads")

    assert storage.object_name_for(None) is None
