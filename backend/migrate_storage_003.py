"""Phase 3: move images from the public bucket's flat keys to private
per-user keys, with thumbnails, and point the DB at /api/images/ paths.

Run from the repo root against production, with the service key:

    DATABASE_URL=... SUPABASE_URL=... SUPABASE_SERVICE_KEY=... \\
    .venv/bin/python backend/migrate_storage_003.py --dry-run
    .venv/bin/python backend/migrate_storage_003.py
    # later, once the bucket is private and everything checks out:
    .venv/bin/python backend/migrate_storage_003.py --delete-old [--dry-run]

Idempotent: values already under /api/images/ are skipped, and uploads
overwrite. Old objects are only removed by --delete-old. Needs Pillow
(backend/requirements.txt), which Vercel doesn't install.
"""
import argparse
import io
import os

import psycopg
from dotenv import load_dotenv
from PIL import Image, ImageOps
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

import storage

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

THUMB_DIM = 600  # matches the frontend's THUMB_DIM


def old_prefix():
    """Where the public bucket served objects before Phase 3."""
    base = os.environ["SUPABASE_URL"].rstrip("/")
    bucket = os.environ.get("SUPABASE_BUCKET", "uploads")
    return f"{base}/storage/v1/object/public/{bucket}/"


def strip_old_prefix(url):
    """The raw name after our bucket's old public prefix, else None. Not yet
    checked against safe_name, so the caller can tell "not ours" apart from
    "ours, but the name is unsafe"."""
    prefix = old_prefix()
    if not isinstance(url, str) or not url.startswith(prefix):
        return None
    return url[len(prefix):]


def old_name(url):
    """The flat key behind an old public URL of our bucket, else None."""
    raw = strip_old_prefix(url)
    return raw if raw is not None and storage.safe_name(raw) else None


def make_thumb(data):
    """WebP bytes no larger than THUMB_DIM on the long edge (never upscaled)."""
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    img.thumbnail((THUMB_DIM, THUMB_DIM))
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")
    out = io.BytesIO()
    img.save(out, "WEBP", quality=85)
    return out.getvalue()


class SupabaseStore:
    """The real storage calls; tests pass a fake with the same methods."""

    def download(self, name):
        return storage.download(name)

    def upload(self, name, data, content_type, cache_control):
        storage.upload_bytes(name, data, content_type, cache_control=cache_control)

    def list_root(self):
        return storage.list_root_objects()

    def delete(self, name):
        storage.delete_object(name)


def walk_srcs(doc, fn):
    """Copy of a TipTap doc with every figure src passed through fn."""
    def walk(node):
        if not isinstance(node, dict):
            return node
        out = dict(node)
        attrs = out.get("attrs")
        if out.get("type") == "figure" and isinstance(attrs, dict) and attrs.get("src"):
            out["attrs"] = {**attrs, "src": fn(attrs["src"])}
        if isinstance(out.get("content"), list):
            out["content"] = [walk(c) for c in out["content"]]
        return out
    return walk(doc)


def move(store, user_id, name, dry_run):
    """Copy old object `name` to the user's prefix (+ thumbnail); return its
    new app path."""
    new = f"users/{user_id}/{name}"
    is_gif = name.lower().endswith(".gif")
    print(f"copy {name} -> {new}" + ("" if is_gif else f" (+ {storage.thumb_name_for(new)})"))
    if not dry_run:
        data, ctype = store.download(name)
        store.upload(new, data, ctype, storage.IMMUTABLE_CACHE)
        if not is_gif and not ctype.startswith("image/gif"):
            store.upload(storage.thumb_name_for(new), make_thumb(data), "image/webp",
                         storage.IMMUTABLE_CACHE)
    return storage.image_path_for(new)


def migrate_user(conn, store, user_id, dry_run):
    moved = {}  # old url -> new path, so a reused image is copied once

    def rewrite(url):
        name = old_name(url)
        if name is None:
            # Under our old prefix but safe_name refuses the raw name (eg. a
            # space): don't silently leave it. (safe_name is a strict
            # allowlist, so this can't be migrated automatically.)
            raw = strip_old_prefix(url)
            if raw is not None and not storage.safe_name(raw):
                print(f"skip (unsafe name, migrate by hand): {url}")
            return url  # already migrated, or not ours
        if url not in moved:
            moved[url] = move(store, user_id, name, dry_run)
        return moved[url]

    entries = conn.execute(
        "select topic_slug, id, image from entries where user_id=%s and image is not null",
        (user_id,),
    ).fetchall()
    posts = conn.execute(
        "select topic_slug, entry_id, doc from posts where user_id=%s", (user_id,)
    ).fetchall()

    entry_updates = [(rewrite(e["image"]), e) for e in entries]
    post_updates = [(walk_srcs(p["doc"], rewrite), p) for p in posts]

    for new, e in entry_updates:
        if new != e["image"]:
            print(f"user {user_id} entry {e['topic_slug']}/{e['id']}: {e['image']} -> {new}")
    for new, p in post_updates:
        if new != p["doc"]:
            print(f"user {user_id} post {p['topic_slug']}/{p['entry_id']}: figures rewritten")
    if dry_run:
        return

    with conn.transaction():
        for new, e in entry_updates:
            if new != e["image"]:
                conn.execute(
                    "update entries set image=%s where user_id=%s and topic_slug=%s and id=%s",
                    (new, user_id, e["topic_slug"], e["id"]),
                )
        for new, p in post_updates:
            if new != p["doc"]:
                conn.execute(
                    "update posts set doc=%s where user_id=%s and topic_slug=%s and entry_id=%s",
                    (Jsonb(new), user_id, p["topic_slug"], p["entry_id"]),
                )


def migrate(conn, store, dry_run):
    for row in conn.execute("select id from users order by id").fetchall():
        migrate_user(conn, store, row["id"], dry_run)


def referenced_old_names(conn):
    """Old flat keys any row still points at."""
    names = set()

    def note(url):
        name = old_name(url)
        if name:
            names.add(name)
        return url

    for r in conn.execute("select image from entries where image is not null").fetchall():
        note(r["image"])
    for r in conn.execute("select doc from posts").fetchall():
        walk_srcs(r["doc"], note)
    return names


def delete_old(conn, store, dry_run):
    """Delete every object outside users/ that no row references."""
    keep = referenced_old_names(conn)
    for name in store.list_root():
        if not storage.safe_name(name):
            # A referenced-but-unsafe name can't be recognised as referenced
            # (its URL never matches old_name), so it must never be
            # auto-deleted either.
            print(f"skip (unsafe name): {name}")
            continue
        if name in keep:
            continue
        print(f"delete {name}")
        if not dry_run:
            store.delete(name)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="print the plan; change nothing")
    parser.add_argument("--delete-old", action="store_true",
                        help="delete unreferenced objects outside users/ instead of migrating")
    args = parser.parse_args()
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True,
                         prepare_threshold=None, row_factory=dict_row) as conn:
        if args.delete_old:
            delete_old(conn, SupabaseStore(), args.dry_run)
        else:
            migrate(conn, SupabaseStore(), args.dry_run)


if __name__ == "__main__":
    main()
