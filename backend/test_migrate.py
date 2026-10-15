import json

import migrate_to_supabase as m
from conftest import make_user


def test_to_doc_passthrough_for_docs():
    doc = {"type": "doc", "content": []}
    assert m.to_doc(doc) is doc


def test_to_doc_converts_legacy_blocks():
    blocks = [{"type": "text", "text": "a\n\nb"},
              {"type": "image", "url": "/api/uploads/x.jpg"}]
    assert m.to_doc(blocks) == {"type": "doc", "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "a"}]},
        {"type": "paragraph", "content": [{"type": "text", "text": "b"}]},
        {"type": "figure", "attrs": {"src": "/api/uploads/x.jpg", "width": "normal"}},
    ]}


def test_public_url_points_at_the_old_public_bucket(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co/")
    monkeypatch.setenv("SUPABASE_BUCKET", "uploads")
    assert m.public_url("a.jpg") == "https://proj.supabase.co/storage/v1/object/public/uploads/a.jpg"


def test_rewrite_srcs_maps_known_urls_and_leaves_original():
    doc = {"type": "doc", "content": [
        {"type": "figure", "attrs": {"src": "/api/uploads/x.jpg", "width": "wide"}}]}
    out = m.rewrite_srcs(doc, {"/api/uploads/x.jpg": "https://cdn/x.jpg"})
    assert out["content"][0]["attrs"]["src"] == "https://cdn/x.jpg"
    assert out["content"][0]["attrs"]["width"] == "wide"
    assert doc["content"][0]["attrs"]["src"] == "/api/uploads/x.jpg"


def test_migrate_writes_every_row_for_the_owner(app_ctx, tmp_path, monkeypatch):
    import db
    (tmp_path / "topics.json").write_text(json.dumps([
        {"slug": "runs", "name": "Runs", "color": "green", "fields": []}]))
    (tmp_path / "runs.json").write_text(json.dumps([
        {"id": 1, "date": "2026-01-01", "image": "/api/uploads/a.jpg",
         "title": "Run", "body": [{"type": "text", "text": "hi"}]}]))
    monkeypatch.setattr(m, "DATA_DIR", str(tmp_path))
    owner = make_user("sub-owner", "owner@example.com")

    m.migrate(db.get_conn(), {"/api/uploads/a.jpg": "https://cdn/a.jpg"}, owner)
    m.migrate(db.get_conn(), {"/api/uploads/a.jpg": "https://cdn/a.jpg"}, owner)  # idempotent

    assert [t["slug"] for t in db.load_topics(owner)] == ["runs"]
    entry = db.find_entry(owner, "runs", 1)
    assert entry["image"] == "https://cdn/a.jpg"
    assert entry["title"] == "Run"
    assert db.load_post(owner, "runs", 1)["type"] == "doc"
