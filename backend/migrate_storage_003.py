"""Phase 3: move images from the public bucket's flat keys to private
per-user keys, with thumbnails, and point the DB at /api/images/ paths.

Run from the repo root against production, with the service key:

    DATABASE_URL=... SUPABASE_URL=... SUPABASE_SERVICE_KEY=... \\
    .venv/bin/python backend/migrate_storage_003.py --dry-run
    .venv/bin/python backend/migrate_storage_003.py
    # later, once the bucket is private and everything checks out:
    .venv/bin/python backend/migrate_storage_003.py --delete-old --dry-run
    .venv/bin/python backend/migrate_storage_003.py --delete-old       # reports a count only
    .venv/bin/python backend/migrate_storage_003.py --delete-old --yes # actually deletes

Idempotent: values already under /api/images/ are skipped, and uploads
overwrite. Old objects are only removed by --delete-old. Needs Pillow
(backend/requirements.txt), which Vercel doesn't install.

A missing or corrupt source object is logged and skipped rather than
aborting the whole run - a later run (once the object is restored, or by
hand) will pick it up.
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


def distinct_name(name):
    """A deterministic alternate for `name` - <stem>-<ext>.<ext> - used when
    another name in this run already claimed the thumbnail key `name` would
    use (eg. photo.jpg and photo.png both naturally become ".../photo.thumb").
    """
    if "." not in name:
        return f"{name}-dup"
    stem, ext = name.rsplit(".", 1)
    return f"{stem}-{ext}.{ext}"


def move(store, user_id, name, dry_run, used_thumbs):
    """Copy old object `name` to the user's prefix (+ thumbnail, unless it's
    a GIF). If another name in this run already claimed the thumbnail key
    this one would use, it's renamed (distinct_name) so both thumbnails
    exist. Returns the new app path, or None if the object is missing (the
    caller then leaves the referencing URL alone, for a later run to retry).
    """
    data = ctype = None
    if not dry_run:
        try:
            data, ctype = store.download(name)
        except storage.NotFound:
            print(f"skip (missing object): {name}")
            return None
        is_gif = name.lower().endswith(".gif") or ctype.startswith("image/gif")
    else:
        # No download yet, so GIF-ness can only be guessed from the name.
        is_gif = name.lower().endswith(".gif")

    target_name = name
    new = f"users/{user_id}/{target_name}"
    thumb_key = storage.thumb_name_for(new)
    if not is_gif and thumb_key in used_thumbs:
        target_name = distinct_name(name)
        new = f"users/{user_id}/{target_name}"
        thumb_key = storage.thumb_name_for(new)
        print(f"warn (thumbnail collision): renaming {name} -> {target_name}")

    print(f"copy {name} -> {new}" + ("" if is_gif else f" (+ {thumb_key})"))
    if not is_gif:
        used_thumbs[thumb_key] = name

    if dry_run:
        return storage.image_path_for(new)

    store.upload(new, data, ctype, storage.IMMUTABLE_CACHE)
    if not is_gif:
        # Only the thumbnail *generation* is allowed to fail softly (eg.
        # corrupt source bytes): the read route falls back to the full
        # image when there's no .thumb. A failure uploading it (or the main
        # object, above) propagates, so this run aborts before any DB write
        # and a rerun retries the whole thing.
        try:
            thumb_bytes = make_thumb(data)
        except Exception as exc:
            print(f"warn (no thumbnail): {new}: {exc}")
        else:
            store.upload(thumb_key, thumb_bytes, "image/webp", storage.IMMUTABLE_CACHE)
    return storage.image_path_for(new)


def migrate_user(conn, store, user_id, dry_run):
    moved = {}        # old url -> new path, so a reused image is copied once
    used_thumbs = {}  # thumb key -> name, so two names can't clobber one thumb

    def rewrite(url):
        name = old_name(url)
        if name is None:
            raw = strip_old_prefix(url)
            if raw is not None:
                print(f"skip (unsafe name, migrate by hand): {url}")
            return url  # already migrated, or not ours
        if url not in moved:
            new = move(store, user_id, name, dry_run, used_thumbs)
            # A missing object isn't a successful rewrite: leave the URL as
            # it was rather than caching None into something that would get
            # written into a figure's src.
            moved[url] = new if new is not None else url
        return moved[url]

    entries = conn.execute(
        "select topic_slug, id, image from entries where user_id=%s and image is not null",
        (user_id,),
    ).fetchall()
    posts = conn.execute(
        "select topic_slug, entry_id, doc from posts where user_id=%s", (user_id,)
    ).fetchall()

    # All the slow network work (download/upload/thumbnail) happens here,
    # against this first read, and nowhere else. The DB write below re-reads
    # and re-applies `moved` inside a transaction, so a concurrent edit to
    # the same row (made while a big upload was in flight) can't be
    # clobbered by a copy of the row read minutes earlier.
    for e in entries:
        rewrite(e["image"])
    for p in posts:
        walk_srcs(p["doc"], rewrite)

    def apply_moved(url):
        return moved.get(url, url)

    if dry_run:
        for e in entries:
            new = apply_moved(e["image"])
            if new != e["image"]:
                print(f"user {user_id} entry {e['topic_slug']}/{e['id']}: {e['image']} -> {new}")
        for p in posts:
            new_doc = walk_srcs(p["doc"], apply_moved)
            if new_doc != p["doc"]:
                print(f"user {user_id} post {p['topic_slug']}/{p['entry_id']}: figures rewritten")
        return

    if not moved:
        return  # nothing under the old prefix for this user; no row to lock

    with conn.transaction():
        fresh_entries = conn.execute(
            "select topic_slug, id, image from entries "
            "where user_id=%s and image is not null for update",
            (user_id,),
        ).fetchall()
        fresh_posts = conn.execute(
            "select topic_slug, entry_id, doc from posts where user_id=%s for update",
            (user_id,),
        ).fetchall()

        # No network calls from here on - only the `moved` map built above.
        # A URL that isn't in it (eg. added by a concurrent edit after the
        # first read) is left untouched; the next run will pick it up.
        for e in fresh_entries:
            new = apply_moved(e["image"])
            if new != e["image"]:
                print(f"user {user_id} entry {e['topic_slug']}/{e['id']}: {e['image']} -> {new}")
                conn.execute(
                    "update entries set image=%s where user_id=%s and topic_slug=%s and id=%s",
                    (new, user_id, e["topic_slug"], e["id"]),
                )
        for p in fresh_posts:
            new_doc = walk_srcs(p["doc"], apply_moved)
            if new_doc != p["doc"]:
                print(f"user {user_id} post {p['topic_slug']}/{p['entry_id']}: figures rewritten")
                conn.execute(
                    "update posts set doc=%s where user_id=%s and topic_slug=%s and entry_id=%s",
                    (Jsonb(new_doc), user_id, p["topic_slug"], p["entry_id"]),
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


def unrecognised_public_marker():
    """The path segment any URL serving our configured bucket's objects
    would contain, regardless of host - used to catch a misconfigured
    SUPABASE_URL before --delete-old trusts its own judgement."""
    bucket = os.environ.get("SUPABASE_BUCKET", "uploads")
    return f"/storage/v1/object/public/{bucket}/"


def check_recognised(url):
    """Raise if `url` looks like it serves our bucket (same marker) but
    doesn't match old_prefix() (eg. a different host) - that almost
    certainly means SUPABASE_URL/SUPABASE_BUCKET is wrong for this database,
    and --delete-old must never guess in that situation."""
    marker = unrecognised_public_marker()
    if isinstance(url, str) and marker in url and not url.startswith(old_prefix()):
        raise SystemExit(
            f"abort: {url!r} contains {marker!r} but doesn't start with "
            f"old_prefix() ({old_prefix()!r}) - check SUPABASE_URL/"
            "SUPABASE_BUCKET before running --delete-old; deleted nothing"
        )
    return url


def delete_old(conn, store, dry_run, confirmed=False):
    """Delete every object outside users/ that no row references.

    Without --dry-run, also requires confirmed=True (the CLI's --yes) -
    otherwise this only reports the target and how many objects would go,
    and deletes nothing. A sanity check before a real run touches
    production storage.
    """
    for r in conn.execute("select image from entries where image is not null").fetchall():
        check_recognised(r["image"])
    for r in conn.execute("select doc from posts").fetchall():
        walk_srcs(r["doc"], check_recognised)

    keep = referenced_old_names(conn)
    names = store.list_root()

    if not dry_run and not confirmed:
        to_delete = [n for n in names if storage.safe_name(n) and n not in keep]
        base = os.environ["SUPABASE_URL"].rstrip("/")
        bucket = os.environ.get("SUPABASE_BUCKET", "uploads")
        print(f"{len(to_delete)} object(s) at {base} bucket {bucket!r} would be deleted")
        print("re-run with --yes to actually delete them")
        return

    for name in names:
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
    parser.add_argument("--yes", action="store_true",
                        help="actually delete with --delete-old (otherwise just report a count)")
    args = parser.parse_args()
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True,
                         prepare_threshold=None, row_factory=dict_row) as conn:
        if args.delete_old:
            delete_old(conn, SupabaseStore(), args.dry_run, confirmed=args.yes)
        else:
            migrate(conn, SupabaseStore(), args.dry_run)


if __name__ == "__main__":
    main()
