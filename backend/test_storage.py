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
