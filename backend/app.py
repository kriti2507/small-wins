import json
import os
import uuid
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask, g, jsonify, redirect, request

import auth
import db
import grants
import storage

# Local dev reads DB/storage config from backend/.env; on Vercel these come
# from the dashboard and this call is a harmless no-op.
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# API only: the React frontend is served separately (Vite in dev, Vercel static
# in prod). This app exposes just the /api/* contract.
app = Flask(__name__, static_folder=None)
# Caps JSON request bodies. Image bytes no longer come through here at all —
# see sign_upload — so this sits well above anything a real request sends.
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

# --- Auth ------------------------------------------------------------------
# Google sign-in lives in auth.py; local dev uses it too (see README).
app.secret_key = os.environ.get("SECRET_KEY", auth.DEV_SECRET)
auth.check_config(os.environ, app.secret_key)

app.permanent_session_lifetime = timedelta(days=30)
app.config["SESSION_COOKIE_HTTPONLY"] = True
# Lax: sent on the top-level redirect back from Google, withheld from
# cross-site POSTs (which is what protects the MCP consent form).
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = bool(os.environ.get("VERCEL"))

# Behind Vercel (a reverse proxy), trust X-Forwarded-* so url_for builds the
# https Google callback URL. Set TRUST_PROXY=1 in the Vercel env.
if os.environ.get("TRUST_PROXY"):
    from werkzeug.middleware.proxy_fix import ProxyFix

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

auth.init_app(app)
app.register_blueprint(grants.bp)


@app.teardown_appcontext
def _close_db(exc):
    conn = g.pop("db_conn", None)
    if conn is not None:
        conn.close()


# Color ids the frontend palette offers; the first is the default.
COLORS = [
    "green", "blue", "orange", "purple", "teal", "rose",
    "red", "amber", "indigo", "cyan", "lime", "slate",
]

# Tile layouts a topic can use for its entry list; the first is the default.
LAYOUTS = ("photo-top", "thumbnail")

ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_BODY_BYTES = 1_000_000  # serialized cap; well under the 5 MB request limit
UPLOAD_URL_TTL_SECONDS = 600  # long enough to upload a photo on a slow phone
READ_URL_TTL_SECONDS = 3600
# The browser may reuse a redirect this long; it must end before the signed
# URL it points at does.
READ_REDIRECT_MAX_AGE = 3000

# Per-user caps while signup is open to any Google account: a stopgap
# against one account filling the database or bucket. Set well above what a
# real user reaches for a long while.
MAX_TOPICS_PER_USER = 50
MAX_ENTRIES_PER_USER = 5000
MAX_IMAGES_PER_USER = 2000  # originals; their thumbnails ride along
MAX_TOPIC_BYTES = 20_000  # serialized name + fields
MAX_ENTRY_BYTES = 100_000  # serialized date, image and field values

import re  # noqa: E402  (kept next to its only user)


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


FIELD_TYPES = ("text", "number", "pace")
DIRECTIONS = ("higher", "lower", "none")
# Entry columns outside the "values" jsonb; a field keyed the same would be
# silently dropped (save_entry) or overwrite it (_flatten).
RESERVED_KEYS = ("id", "date", "image", "body")


def merge_fields(old, submitted):
    """Validate an edited, ordered field list against a topic's current fields.

    Items with a `key` are existing fields: label and direction may change,
    the stored type may not. Items without one are new: they get a key from
    their label that no current field uses, so a removed field's values can't
    resurface under a new field. Existing keys left out are removed.
    Returns (fields, removed_keys); raises ValueError with a user-facing
    message on bad input."""
    if not isinstance(submitted, list):
        raise ValueError("Fields must be a list.")
    by_key = {f["key"]: f for f in old}
    taken = set(by_key) | set(RESERVED_KEYS)
    seen = set()
    fields = []
    for f in submitted:
        if not isinstance(f, dict):
            raise ValueError("Invalid field.")
        label = f.get("label")
        label = label.strip() if isinstance(label, str) else ""
        if not label:
            raise ValueError("Every field needs a label.")
        key = f.get("key")
        if key is not None and not isinstance(key, str):
            raise ValueError("Invalid field.")
        if key is not None:
            if key not in by_key:
                raise ValueError("That field no longer exists.")
            if key in seen:
                raise ValueError("A field is listed twice.")
            ftype = by_key[key]["type"]
            default_direction = by_key[key]["direction"]
        else:
            ftype = f.get("type", "number")
            if ftype not in FIELD_TYPES:
                raise ValueError("Invalid field type.")
            base = slugify(label)
            if not base:
                raise ValueError(f"'{label}' needs at least one letter or number.")
            key, n = base, 2
            while key in taken:
                key, n = f"{base}_{n}", n + 1
            default_direction = "none"
        taken.add(key)
        seen.add(key)
        direction = f.get("direction", default_direction)
        if ftype == "text":
            direction = "none"
        elif direction not in DIRECTIONS:
            raise ValueError("Invalid scoring direction.")
        fields.append({"key": key, "label": label, "type": ftype, "direction": direction})
    removed = [k for k in by_key if k not in seen]
    return fields, removed


def valid_body(body):
    """A post body is a TipTap doc: {"type": "doc", "content": [...]}."""
    if not isinstance(body, dict) or body.get("type") != "doc":
        return False
    if not isinstance(body.get("content", []), list):
        return False
    return len(json.dumps(body)) <= MAX_BODY_BYTES


def limit_reached(what, limit):
    return jsonify({"error": f"You've reached the limit of {limit:,} {what}."}), 403


def with_body(slug, entry):
    """API view of a stored entry: join the post body in if one exists."""
    out = dict(entry)
    doc = db.load_post(g.user_id, slug, entry["id"])
    if doc is not None:
        out["body"] = doc
    return out


def image_urls_in(doc):
    """Every attrs.src on a 'figure' node, anywhere in a TipTap doc (figures
    can nest inside blockquotes, list items, etc. to arbitrary depth).
    """
    urls = set()

    def walk(node):
        if not isinstance(node, dict):
            return
        if node.get("type") == "figure":
            src = (node.get("attrs") or {}).get("src")
            if src:
                urls.add(src)
        content = node.get("content")
        if isinstance(content, list):
            for child in content:
                walk(child)

    walk(doc)
    return urls


def referenced_image_urls(user_id):
    """Every image URL user_id still references: hero images plus in-body
    figures. Nobody else can reference this user's objects. See the call site
    in delete_entry for the ordering requirement.
    """
    urls = db.all_entry_images(user_id)
    for doc in db.all_post_docs(user_id):
        urls |= image_urls_in(doc)
    return urls


# --- Topics API ------------------------------------------------------------

@app.route("/api/topics", methods=["GET"])
@auth.login_required
def get_topics():
    return jsonify(db.load_topics(g.user_id))


@app.route("/api/topics", methods=["POST"])
@auth.login_required
def add_topic():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    slug = slugify(name)
    if not slug:
        return jsonify({"error": "A topic name is required."}), 400
    topics = db.load_topics(g.user_id)
    if any(t["slug"] == slug for t in topics):
        return jsonify({"error": f"A topic '{name}' already exists."}), 409
    if len(topics) >= MAX_TOPICS_PER_USER:
        return limit_reached("topics", MAX_TOPICS_PER_USER)

    color = data.get("color")
    if color not in COLORS:
        color = COLORS[0]
    layout = data.get("layout")
    if layout not in LAYOUTS:
        layout = LAYOUTS[0]

    # Silently drop blank-label rows (unchanged behaviour), then let
    # merge_fields assign keys, reject reserved/invalid ones, and validate
    # types and directions just like editing an existing topic's fields does.
    raw_fields = data.get("fields", [])
    if isinstance(raw_fields, list):
        raw_fields = [f for f in raw_fields
                      if isinstance(f, dict) and isinstance(f.get("label"), str)
                      and f.get("label").strip()]
    try:
        fields, _ = merge_fields([], raw_fields)
    except ValueError as err:
        return jsonify({"error": str(err)}), 400

    topic = {"slug": slug, "name": name, "color": color, "layout": layout, "fields": fields}
    if len(json.dumps(topic)) > MAX_TOPIC_BYTES:
        return jsonify({"error": "That topic is too large."}), 400
    db.add_topic(g.user_id, topic)
    return jsonify(topic), 201


@app.route("/api/topics/<slug>", methods=["PATCH"])
@auth.login_required
def update_topic(slug):
    topic = db.find_topic(g.user_id, slug)
    if not topic:
        return jsonify({"error": "Unknown topic."}), 404

    data = request.get_json(force=True)
    changes = {}
    if "layout" in data:
        if data["layout"] not in LAYOUTS:
            return jsonify({"error": "Invalid layout."}), 400
        changes["layout"] = data["layout"]
    if "color" in data:
        if data["color"] not in COLORS:
            return jsonify({"error": "Invalid color."}), 400
        changes["color"] = data["color"]
    if "name" in data:
        name = (data["name"] or "").strip()
        if not slugify(name):
            return jsonify({"error": "A topic name is required."}), 400
        # The slug stays put on rename, so check the new name against both the
        # other topics' slugs (what add_topic checks) and their names.
        others = [t for t in db.load_topics(g.user_id) if t["slug"] != slug]
        if any(slugify(name) in (t["slug"], slugify(t["name"])) for t in others):
            return jsonify({"error": f"A topic '{name}' already exists."}), 409
        changes["name"] = name
    removed = []
    if "fields" in data:
        try:
            changes["fields"], removed = merge_fields(topic["fields"], data["fields"])
        except ValueError as err:
            return jsonify({"error": str(err)}), 400

    if len(json.dumps({**topic, **changes})) > MAX_TOPIC_BYTES:
        return jsonify({"error": "That topic is too large."}), 400
    return jsonify(db.update_topic(g.user_id, slug, changes, removed_keys=removed))


@app.route("/api/topics/<slug>", methods=["DELETE"])
@auth.login_required
def delete_topic(slug):
    topics = db.load_topics(g.user_id)
    if not any(t["slug"] == slug for t in topics):
        return jsonify({"error": "Unknown topic."}), 404
    # New accounts start with no topics and pick some on the home page; keeping
    # at least one means only brand-new accounts ever see that picker.
    if len(topics) == 1:
        return jsonify({"error": "You need at least one aspect."}), 400

    # Gather the topic's images before it's gone, as delete_entry does.
    candidates = {e["image"] for e in db.load_entries(g.user_id, slug) if e.get("image")}
    for doc in db.topic_post_docs(g.user_id, slug):
        candidates |= image_urls_in(doc)

    db.delete_topic(g.user_id, slug)  # entries and posts cascade with it
    delete_orphaned_images(candidates)
    return jsonify({"ok": True})


# --- Uploads API -----------------------------------------------------------

@app.route("/api/uploads/sign", methods=["POST"])
@auth.login_required
def sign_upload():
    """Hand the browser a URL to upload one image straight to Supabase.

    The bytes deliberately skip this server: Vercel caps a function's request
    body at 4.5 MB (a hard platform limit, below a typical phone photo), so a
    multipart upload through here 413s at the edge before Flask ever runs.

    We mint the key rather than trusting the client's filename, which keeps
    the object under this user's prefix — the only place read_image and
    delete_entry will look.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    ext = str(data.get("ext") or "").lower().lstrip(".")
    if ext not in ALLOWED_EXT:
        return jsonify({"error": "Unsupported file type."}), 400

    name = f"users/{g.user_id}/{uuid.uuid4().hex}.{ext}"
    want_thumb = data.get("thumb") is True
    try:
        if storage.count_user_images(g.user_id, MAX_IMAGES_PER_USER) >= MAX_IMAGES_PER_USER:
            return limit_reached("images", MAX_IMAGES_PER_USER)
        out = {"upload_url": storage.signed_upload_url(name, UPLOAD_URL_TTL_SECONDS)}
        if want_thumb:
            out["thumb_upload_url"] = storage.signed_upload_url(
                storage.thumb_name_for(name), UPLOAD_URL_TTL_SECONDS
            )
    except Exception:
        # Never let this become Flask's HTML 500 page: the client parses every
        # response as JSON, so an HTML body surfaces as a parser error.
        app.logger.exception("could not sign an upload URL")
        return jsonify({"error": "Could not start the upload. Try again."}), 502

    out["url"] = storage.image_path_for(name)
    return jsonify(out), 201


# --- Images API ------------------------------------------------------------

@app.route("/api/images/<path:key>", methods=["GET"])
@auth.login_required
def read_image(key):
    """Send the browser to a short-lived signed URL for one of its own images.

    The bucket is private, so this ownership check is the only way in. Keys
    that aren't the caller's 404 rather than 403, so other users' keys can't
    be probed.
    """
    name = storage.user_key(key, g.user_id)
    if name is None:
        return jsonify({"error": "Not found."}), 404
    try:
        if request.args.get("size") == "thumb":
            try:
                url = storage.signed_read_url(storage.thumb_name_for(name), READ_URL_TTL_SECONDS)
            except storage.NotFound:
                # GIFs and images uploaded without one have no thumbnail.
                url = storage.signed_read_url(name, READ_URL_TTL_SECONDS)
        else:
            url = storage.signed_read_url(name, READ_URL_TTL_SECONDS)
    except storage.NotFound:
        return jsonify({"error": "Not found."}), 404
    except Exception:
        app.logger.exception("could not sign a read URL")
        return jsonify({"error": "Could not load the image."}), 502

    res = redirect(url, 302)
    res.headers["Cache-Control"] = f"private, max-age={READ_REDIRECT_MAX_AGE}"
    return res


# --- Entries API -----------------------------------------------------------

@app.route("/api/topics/<slug>/entries", methods=["GET"])
@auth.login_required
def get_entries(slug):
    if not db.find_topic(g.user_id, slug):
        return jsonify({"error": "Unknown topic."}), 404
    return jsonify([with_body(slug, e) for e in db.load_entries(g.user_id, slug)])


@app.route("/api/topics/<slug>/entries", methods=["POST"])
@auth.login_required
def add_entry(slug):
    topic = db.find_topic(g.user_id, slug)
    if not topic:
        return jsonify({"error": "Unknown topic."}), 404
    if db.count_entries(g.user_id) >= MAX_ENTRIES_PER_USER:
        return limit_reached("entries", MAX_ENTRIES_PER_USER)

    data = request.get_json(force=True)
    entry = {
        "id": db.next_entry_id(g.user_id, slug),
        "date": data.get("date", ""),
        "image": data.get("image") or None,
    }
    for field in topic["fields"]:
        key = field["key"]
        val = data.get(key)
        if field["type"] in ("number", "pace"):
            entry[key] = float(val) if val not in (None, "") else None
        else:
            entry[key] = val if val is not None else ""

    if len(json.dumps(entry)) > MAX_ENTRY_BYTES:
        return jsonify({"error": "That entry is too large."}), 400
    # Optional: quick add saves what the user typed as the post in one go.
    body = data.get("body")
    if body is not None and not valid_body(body):
        return jsonify({"error": "Invalid post body."}), 400
    db.save_entry(g.user_id, slug, entry, via=g.via)
    if body is not None:
        db.save_post(g.user_id, slug, entry["id"], body)
    return jsonify(with_body(slug, entry)), 201


@app.route("/api/topics/<slug>/entries/<int:entry_id>", methods=["GET"])
@auth.login_required
def get_entry(slug, entry_id):
    if not db.find_topic(g.user_id, slug):
        return jsonify({"error": "Unknown topic."}), 404
    entry = db.find_entry(g.user_id, slug, entry_id)
    if not entry:
        return jsonify({"error": "Unknown entry."}), 404
    return jsonify(with_body(slug, entry))


@app.route("/api/topics/<slug>/entries/<int:entry_id>", methods=["PATCH"])
@auth.login_required
def update_entry(slug, entry_id):
    topic = db.find_topic(g.user_id, slug)
    if not topic:
        return jsonify({"error": "Unknown topic."}), 404

    entry = db.find_entry(g.user_id, slug, entry_id)
    if not entry:
        return jsonify({"error": "Unknown entry."}), 404

    data = request.get_json(force=True)
    if "date" in data:
        entry["date"] = data.get("date", "")
    if "image" in data:
        entry["image"] = data.get("image") or None
    for field in topic["fields"]:
        key = field["key"]
        if key not in data:
            continue
        val = data.get(key)
        if field["type"] in ("number", "pace"):
            entry[key] = float(val) if val not in (None, "") else None
        else:
            entry[key] = val if val is not None else ""

    if len(json.dumps(entry)) > MAX_ENTRY_BYTES:
        return jsonify({"error": "That entry is too large."}), 400
    if "body" in data:
        body = data["body"]
        if not valid_body(body):
            return jsonify({"error": "Invalid post body."}), 400
        db.save_post(g.user_id, slug, entry_id, body)

    db.save_entry(g.user_id, slug, entry)
    return jsonify(with_body(slug, entry))


@app.route("/api/topics/<slug>/entries/<int:entry_id>", methods=["DELETE"])
@auth.login_required
def delete_entry(slug, entry_id):
    if not db.find_topic(g.user_id, slug):
        return jsonify({"error": "Unknown topic."}), 404

    entry = db.find_entry(g.user_id, slug, entry_id)
    if not entry:
        return jsonify({"error": "Unknown entry."}), 404

    # Gather this entry's images before it's gone, so we know what *might*
    # become orphaned.
    candidates = image_urls_in(db.load_post(g.user_id, slug, entry_id))
    if entry.get("image"):
        candidates.add(entry["image"])

    db.delete_entry(g.user_id, slug, entry_id)  # posts row cascades with it
    delete_orphaned_images(candidates)
    return jsonify({"ok": True})


def delete_orphaned_images(candidates):
    """Delete whichever of candidates the user no longer references.

    Call only after the rows that held them are gone -- otherwise the row
    being deleted would count as its own reference and nothing would ever be
    cleaned up. Skips the scan entirely when nothing could possibly be freed.
    """
    orphaned = candidates - referenced_image_urls(g.user_id) if candidates else set()
    for url in orphaned:
        # The row is already gone; a 500 here would be a lie regardless of
        # cause, so the whole per-URL body -- including resolving the name,
        # which can raise on a storage misconfiguration -- is best-effort.
        try:
            name = storage.object_name_for(url, g.user_id)
            if not name:  # not one of this user's objects (or an unsafe key) -- skip
                continue
            try:
                storage.delete_object(name)
            except storage.NotFound:
                pass  # already gone -- still try the thumbnail below
            try:
                storage.delete_object(storage.thumb_name_for(name))
            except storage.NotFound:
                pass  # GIFs and older uploads have no thumbnail
        except Exception as exc:
            app.logger.warning("failed to delete storage object for %s: %s", url, exc)


# --- Export ----------------------------------------------------------------

def doc_text(doc):
    """Plain text of a TipTap doc, one line per top-level block."""
    def text(node):
        if not isinstance(node, dict):
            return ""
        return node.get("text", "") + "".join(text(c) for c in node.get("content") or [])

    return "\n".join(t for t in (text(b) for b in (doc or {}).get("content") or []) if t)


@app.route("/api/export.csv", methods=["GET"])
@auth.login_required
def export_csv():
    """Every entry across every topic as one CSV; a topic's fields become
    columns, blank on rows from topics that don't have them.
    """
    import csv
    import io

    topics = db.load_topics(g.user_id)
    keys = list(dict.fromkeys(f["key"] for t in topics for f in t["fields"]))
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["topic", "id", "date", "image", *keys, "body"])
    for t in topics:
        for e in db.load_entries(g.user_id, t["slug"]):
            body = doc_text(db.load_post(g.user_id, t["slug"], e["id"]))
            row = [e.get(k) for k in keys]
            writer.writerow([t["name"], e["id"], e["date"], e["image"] or "", *row, body])
    return out.getvalue(), 200, {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": 'attachment; filename="small-wins.csv"',
    }


if __name__ == "__main__":
    app.run(debug=True, port=5000)  # local only; Vercel imports `app` instead
