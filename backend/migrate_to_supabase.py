"""One-time import of the JSON-file data into Supabase (Postgres + Storage).

Run once, from the repo root, with the Supabase env vars set:

    DATABASE_URL=... SUPABASE_URL=... SUPABASE_BUCKET=uploads \\
    SUPABASE_SERVICE_KEY=... .venv/bin/python backend/migrate_to_supabase.py \\
    --owner-user-id <users.id of the account that should own the data>

Idempotent: upserts rows and re-uploads files, so re-running is safe.
Prerequisite: schema.sql applied, the `uploads` bucket created, and the
owner has signed in once (so their users row exists).
"""
import argparse
import json
import os

import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Jsonb

import storage

# Read DB/storage config from backend/.env, same as app.py.
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")

MIME = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "gif": "image/gif", "webp": "image/webp"}


def to_doc(body):
    """Legacy Block[] bodies -> TipTap doc; docs pass through unchanged."""
    if isinstance(body, dict):
        return body
    content = []
    for b in body or []:
        if b.get("type") == "image":
            content.append({"type": "figure",
                            "attrs": {"src": b.get("url"), "width": "normal"}})
        else:
            for line in (b.get("text") or "").split("\n"):
                line = line.strip()
                if line:
                    content.append({"type": "paragraph",
                                    "content": [{"type": "text", "text": line}]})
    return {"type": "doc", "content": content}


def rewrite_srcs(doc, url_map):
    """Copy of a TipTap doc with any image src in url_map replaced."""
    def walk(node):
        if not isinstance(node, dict):
            return node
        out = dict(node)
        attrs = out.get("attrs")
        if isinstance(attrs, dict) and attrs.get("src") in url_map:
            out["attrs"] = {**attrs, "src": url_map[attrs["src"]]}
        if isinstance(out.get("content"), list):
            out["content"] = [walk(c) for c in out["content"]]
        return out
    return walk(doc)


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def upload_all_images():
    url_map = {}
    if not os.path.isdir(UPLOADS_DIR):
        return url_map
    for fname in sorted(os.listdir(UPLOADS_DIR)):
        ext = fname.rsplit(".", 1)[-1].lower()
        with open(os.path.join(UPLOADS_DIR, fname), "rb") as f:
            data = f.read()
        public = storage.upload_bytes(fname, data, MIME.get(ext, "application/octet-stream"))
        url_map[f"/api/uploads/{fname}"] = public
    return url_map


def resolve_legacy_post(entry):
    """The doc for an entry: from its post-file ref, or a legacy inline body."""
    ref = entry.get("post")
    if ref:
        path = os.path.normpath(os.path.join(DATA_DIR, ref))
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
        return None
    if "body" in entry:
        return to_doc(entry["body"])
    return None


def migrate(conn, url_map, owner_user_id):
    topics = load_json(os.path.join(DATA_DIR, "topics.json"), [])
    for pos, t in enumerate(topics):
        conn.execute(
            "insert into topics (user_id, slug, name, color, layout, fields, position) "
            "values (%s, %s, %s, %s, %s, %s, %s) "
            "on conflict (user_id, slug) do update set name=excluded.name, "
            "color=excluded.color, layout=excluded.layout, "
            "fields=excluded.fields, position=excluded.position",
            (owner_user_id, t["slug"], t["name"], t["color"], t.get("layout", "photo-top"),
             Jsonb(t.get("fields", [])), pos),
        )
        slug = t["slug"]
        for e in load_json(os.path.join(DATA_DIR, f"{slug}.json"), []):
            doc = resolve_legacy_post(e)
            image = url_map.get(e.get("image"), e.get("image"))
            values = {k: v for k, v in e.items()
                      if k not in ("id", "date", "image", "post", "body")}
            conn.execute(
                'insert into entries (user_id, topic_slug, id, date, image, "values") '
                "values (%s, %s, %s, %s, %s, %s) "
                "on conflict (user_id, topic_slug, id) do update set date=excluded.date, "
                'image=excluded.image, "values"=excluded."values"',
                (owner_user_id, slug, e["id"], e.get("date", ""), image, Jsonb(values)),
            )
            if doc is not None:
                conn.execute(
                    "insert into posts (user_id, topic_slug, entry_id, doc) "
                    "values (%s, %s, %s, %s) "
                    "on conflict (user_id, topic_slug, entry_id) do update set doc=excluded.doc",
                    (owner_user_id, slug, e["id"], Jsonb(rewrite_srcs(doc, url_map))),
                )


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--owner-user-id", type=int, required=True,
                        help="users.id of the account that will own the imported data")
    args = parser.parse_args()
    url_map = upload_all_images()
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
        migrate(conn, url_map, args.owner_user_id)
    print(f"migrated {len(url_map)} image(s) and all topics/entries/posts")


if __name__ == "__main__":
    main()
