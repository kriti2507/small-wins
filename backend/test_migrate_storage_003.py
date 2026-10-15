import io

import pytest
from PIL import Image

import db
import migrate_storage_003 as m
import storage
from conftest import make_user

OLD = "https://proj.supabase.co/storage/v1/object/public/uploads/"


@pytest.fixture(autouse=True)
def storage_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "svc")
    monkeypatch.setenv("SUPABASE_BUCKET", "uploads")


def png(w=1200, h=800):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), "red").save(buf, "PNG")
    return buf.getvalue()


class FakeStore:
    """Stands in for storage.download / upload_bytes / list / delete."""

    def __init__(self, objects):
        self.objects = dict(objects)  # name -> (bytes, content_type)
        self.uploads = []             # (name, content_type, cache_control)
        self.deleted = []

    def download(self, name):
        if name not in self.objects:
            raise storage.NotFound(name)
        return self.objects[name]

    def upload(self, name, data, content_type, cache_control):
        self.objects[name] = (data, content_type)
        self.uploads.append((name, content_type, cache_control))

    def list_root(self):
        return [n for n in self.objects if "/" not in n]

    def delete(self, name):
        self.deleted.append(name)
        self.objects.pop(name, None)


def seed(user_id, image=None, figure=None, slug="runs", entry_id=1):
    conn = db.get_conn()
    db.load_topics(user_id)  # seeds "runs"
    conn.execute(
        'insert into entries (user_id, topic_slug, id, date, image, "values") '
        "values (%s, %s, %s, '2026-01-01', %s, '{}')",
        (user_id, slug, entry_id, image),
    )
    if figure:
        db.save_post(user_id, slug, entry_id, {"type": "doc", "content": [
            {"type": "blockquote", "content": [
                {"type": "figure", "attrs": {"src": figure, "width": "wide"}}]}]})


def test_rewrites_hero_and_figure_urls_to_per_user_paths(app_ctx):
    uid = make_user("sub-a", "a@example.com")
    seed(uid, image=OLD + "hero.jpg", figure=OLD + "fig.png")
    store = FakeStore({"hero.jpg": (png(), "image/jpeg"), "fig.png": (png(), "image/png")})

    m.migrate(db.get_conn(), store, dry_run=False)

    entry = db.find_entry(uid, "runs", 1)
    assert entry["image"] == f"/api/images/users/{uid}/hero.jpg"
    fig = db.load_post(uid, "runs", 1)["content"][0]["content"][0]
    assert fig["attrs"] == {"src": f"/api/images/users/{uid}/fig.png", "width": "wide"}
    assert store.objects[f"users/{uid}/hero.jpg"][1] == "image/jpeg"
    for name, _ctype, cache in store.uploads:
        assert cache == "max-age=31536000", name


def test_makes_a_600px_webp_thumbnail_for_non_gifs_only(app_ctx):
    uid = make_user("sub-a", "a@example.com")
    seed(uid, image=OLD + "big.png", entry_id=1)
    seed(uid, image=OLD + "anim.gif", entry_id=2)
    store = FakeStore({"big.png": (png(1800, 900), "image/png"),
                       "anim.gif": (b"GIF89a...", "image/gif")})

    m.migrate(db.get_conn(), store, dry_run=False)

    data, ctype = store.objects[f"users/{uid}/big.thumb"]
    assert ctype == "image/webp"
    assert Image.open(io.BytesIO(data)).size == (600, 300)
    assert f"users/{uid}/anim.thumb" not in store.objects
    assert f"users/{uid}/anim.gif" in store.objects


def test_never_upscales_a_small_image(app_ctx):
    uid = make_user("sub-a", "a@example.com")
    seed(uid, image=OLD + "small.png")
    store = FakeStore({"small.png": (png(300, 200), "image/png")})
    m.migrate(db.get_conn(), store, dry_run=False)
    data, _ = store.objects[f"users/{uid}/small.thumb"]
    assert Image.open(io.BytesIO(data)).size == (300, 200)


def test_each_user_gets_their_own_copy_of_a_shared_object(app_ctx):
    a = make_user("sub-a", "a@example.com")
    b = make_user("sub-b", "b@example.com")
    seed(a, image=OLD + "shared.jpg")
    seed(b, figure=OLD + "shared.jpg")
    store = FakeStore({"shared.jpg": (png(), "image/jpeg")})

    m.migrate(db.get_conn(), store, dry_run=False)

    assert f"users/{a}/shared.jpg" in store.objects
    assert f"users/{b}/shared.jpg" in store.objects
    assert db.find_entry(a, "runs", 1)["image"] == f"/api/images/users/{a}/shared.jpg"


def test_dry_run_changes_nothing(app_ctx, capsys):
    uid = make_user("sub-a", "a@example.com")
    seed(uid, image=OLD + "hero.jpg")
    store = FakeStore({"hero.jpg": (png(), "image/jpeg")})

    m.migrate(db.get_conn(), store, dry_run=True)

    assert store.uploads == []
    assert db.find_entry(uid, "runs", 1)["image"] == OLD + "hero.jpg"
    out = capsys.readouterr().out
    assert f"users/{uid}/hero.jpg" in out  # the plan is printed


def test_second_run_is_a_no_op(app_ctx):
    uid = make_user("sub-a", "a@example.com")
    seed(uid, image=OLD + "hero.jpg")
    store = FakeStore({"hero.jpg": (png(), "image/jpeg")})

    m.migrate(db.get_conn(), store, dry_run=False)
    uploads = list(store.uploads)
    m.migrate(db.get_conn(), store, dry_run=False)

    assert store.uploads == uploads


def test_foreign_urls_are_left_alone(app_ctx):
    uid = make_user("sub-a", "a@example.com")
    seed(uid, image="https://example.com/x.jpg",
         figure="https://proj.supabase.co/storage/v1/object/public/other/x.jpg")
    store = FakeStore({})

    m.migrate(db.get_conn(), store, dry_run=False)

    assert store.uploads == []
    assert db.find_entry(uid, "runs", 1)["image"] == "https://example.com/x.jpg"


def test_migrate_user_skips_an_unsafe_name_instead_of_silently_leaving_it(app_ctx, capsys):
    """safe_name is a strict allowlist now, so an old URL whose name fails it
    (eg. a space) must be called out, not quietly left for someone to miss."""
    uid = make_user("sub-a", "a@example.com")
    seed(uid, image=OLD + "my photo.jpg")
    store = FakeStore({})

    m.migrate(db.get_conn(), store, dry_run=False)

    assert store.uploads == []
    assert db.find_entry(uid, "runs", 1)["image"] == OLD + "my photo.jpg"
    out = capsys.readouterr().out
    assert f"skip (unsafe name, migrate by hand): {OLD}my photo.jpg" in out


def test_delete_old_removes_only_unreferenced_root_objects(app_ctx):
    uid = make_user("sub-a", "a@example.com")
    seed(uid, image=OLD + "still-used.jpg")  # not migrated yet: must survive
    store = FakeStore({
        "still-used.jpg": (b"x", "image/jpeg"),
        "moved.jpg": (b"x", "image/jpeg"),
        f"users/{uid}/moved.jpg": (b"x", "image/jpeg"),
    })

    m.delete_old(db.get_conn(), store, dry_run=False)

    assert store.deleted == ["moved.jpg"]


def test_delete_old_skips_an_unsafe_root_object_name(app_ctx, capsys):
    """A referenced-but-unsafe name can't be recognised as referenced (its
    URL never matches old_name), so it must never be auto-deleted either."""
    store = FakeStore({"my photo.jpg": (b"x", "image/jpeg")})

    m.delete_old(db.get_conn(), store, dry_run=False)

    assert store.deleted == []
    out = capsys.readouterr().out
    assert "skip (unsafe name): my photo.jpg" in out


def test_a_missing_object_is_skipped_without_wedging_the_run(app_ctx, capsys):
    uid = make_user("sub-a", "a@example.com")
    seed(uid, image=OLD + "missing.jpg", entry_id=1)
    seed(uid, image=OLD + "ok.jpg", entry_id=2)
    store = FakeStore({"ok.jpg": (png(), "image/jpeg")})  # missing.jpg absent

    m.migrate(db.get_conn(), store, dry_run=False)

    assert db.find_entry(uid, "runs", 1)["image"] == OLD + "missing.jpg"
    assert db.find_entry(uid, "runs", 2)["image"] == f"/api/images/users/{uid}/ok.jpg"
    out = capsys.readouterr().out
    assert "skip (missing object): missing.jpg" in out


def test_corrupt_bytes_still_migrate_the_main_object_without_a_thumbnail(app_ctx, capsys):
    uid = make_user("sub-a", "a@example.com")
    seed(uid, image=OLD + "bad.jpg")
    store = FakeStore({"bad.jpg": (b"not an image", "image/jpeg")})

    m.migrate(db.get_conn(), store, dry_run=False)

    assert store.objects[f"users/{uid}/bad.jpg"] == (b"not an image", "image/jpeg")
    assert f"users/{uid}/bad.thumb" not in store.objects
    assert db.find_entry(uid, "runs", 1)["image"] == f"/api/images/users/{uid}/bad.jpg"
    out = capsys.readouterr().out
    assert f"warn (no thumbnail): users/{uid}/bad.jpg" in out


def test_a_concurrent_edit_during_migration_is_not_clobbered(app_ctx):
    """move() downloads before the DB transaction opens, so another request
    can edit the same post in between. The update must re-read inside the
    transaction and apply only the rewrite, not overwrite with a stale doc."""
    uid = make_user("sub-a", "a@example.com")
    seed(uid, figure=OLD + "fig.png")

    class ConcurrentEditStore(FakeStore):
        def download(self, name):
            doc = db.load_post(uid, "runs", 1)
            doc["content"].append({"type": "paragraph", "content": []})
            db.save_post(uid, "runs", 1, doc)
            return super().download(name)

    store = ConcurrentEditStore({"fig.png": (png(), "image/png")})

    m.migrate(db.get_conn(), store, dry_run=False)

    doc = db.load_post(uid, "runs", 1)
    assert doc["content"][-1] == {"type": "paragraph", "content": []}
    fig = doc["content"][0]["content"][0]
    assert fig["attrs"]["src"] == f"/api/images/users/{uid}/fig.png"


def test_delete_old_aborts_if_a_url_cant_be_recognised_as_ours(app_ctx):
    """A URL whose path contains our configured bucket's public marker but
    whose host doesn't match SUPABASE_URL could mean SUPABASE_URL or
    SUPABASE_BUCKET is misconfigured for this database - delete_old must
    never guess, and must delete nothing in that case."""
    uid = make_user("sub-a", "a@example.com")
    seed(uid, image="https://other-project.supabase.co/storage/v1/object/public/uploads/x.jpg")
    store = FakeStore({"moved.jpg": (b"x", "image/jpeg")})

    with pytest.raises(SystemExit):
        m.delete_old(db.get_conn(), store, dry_run=False)

    assert store.deleted == []


def test_gif_detected_by_content_type_even_when_the_extension_isnt_gif(app_ctx, capsys):
    """The thumb-or-not decision and the printed line must agree: both use
    name-or-content-type, not just the name, once the bytes are in hand."""
    uid = make_user("sub-a", "a@example.com")
    seed(uid, image=OLD + "mystery.dat")
    store = FakeStore({"mystery.dat": (b"GIF89a...", "image/gif")})

    m.migrate(db.get_conn(), store, dry_run=False)

    assert f"users/{uid}/mystery.thumb" not in store.objects
    out = capsys.readouterr().out
    [copy_line] = [line for line in out.splitlines() if line.startswith("copy mystery.dat")]
    assert "+" not in copy_line


def test_thumbnail_key_collision_skips_the_second_thumbnail(app_ctx, capsys):
    uid = make_user("sub-a", "a@example.com")
    seed(uid, image=OLD + "photo.jpg", entry_id=1)
    seed(uid, image=OLD + "photo.png", entry_id=2)
    store = FakeStore({"photo.jpg": (png(), "image/jpeg"), "photo.png": (png(), "image/png")})

    m.migrate(db.get_conn(), store, dry_run=False)

    assert f"users/{uid}/photo.jpg" in store.objects
    assert f"users/{uid}/photo.png" in store.objects
    # Exactly one of the two claimed the shared thumbnail key.
    thumb_uploads = [n for n, _c, _cc in store.uploads if n == f"users/{uid}/photo.thumb"]
    assert len(thumb_uploads) == 1
    out = capsys.readouterr().out
    assert f"warn (thumbnail collision): users/{uid}/photo.thumb" in out
