import json
import os
import uuid
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask, g, jsonify, redirect, request

import auth
import db
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

import re  # noqa: E402  (kept next to its only user)


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def valid_body(body):
    """A post body is a TipTap doc: {"type": "doc", "content": [...]}."""
    if not isinstance(body, dict) or body.get("type") != "doc":
        return False
    if not isinstance(body.get("content", []), list):
        return False
    return len(json.dumps(body)) <= MAX_BODY_BYTES


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


def referenced_image_urls():
    """Every image URL still referenced anywhere, by any user: hero
    images plus in-body figures. See the call site in delete_entry for the
    ordering requirement.
    """
    urls = db.all_entry_images()
    for doc in db.all_post_docs():
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
    if db.find_topic(g.user_id, slug):
        return jsonify({"error": f"A topic '{name}' already exists."}), 409

    color = data.get("color")
    if color not in COLORS:
        color = COLORS[0]
    layout = data.get("layout")
    if layout not in LAYOUTS:
        layout = LAYOUTS[0]

    fields = []
    for f in data.get("fields", []):
        label = (f.get("label") or "").strip()
        if not label:
            continue
        ftype = f.get("type", "number")
        direction = f.get("direction", "none")
        if ftype == "text":
            direction = "none"
        fields.append(
            {"key": slugify(label), "label": label, "type": ftype, "direction": direction}
        )

    topic = {"slug": slug, "name": name, "color": color, "layout": layout, "fields": fields}
    db.add_topic(g.user_id, topic)
    return jsonify(topic), 201


@app.route("/api/topics/<slug>", methods=["PATCH"])
@auth.login_required
def update_topic(slug):
    topic = db.find_topic(g.user_id, slug)
    if not topic:
        return jsonify({"error": "Unknown topic."}), 404

    data = request.get_json(force=True)
    if "layout" in data:
        if data["layout"] not in LAYOUTS:
            return jsonify({"error": "Invalid layout."}), 400
        topic = db.set_topic_layout(g.user_id, slug, data["layout"])

    return jsonify(topic)


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

    db.save_entry(g.user_id, slug, entry)
    return jsonify(entry), 201


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

    # Only now, with the row already gone, can "is this still referenced?"
    # be answered correctly -- otherwise the entry being deleted would count
    # as its own reference and nothing would ever be cleaned up. Skip the
    # scan entirely when there's nothing that could possibly be freed.
    orphaned = candidates - referenced_image_urls() if candidates else set()
    for url in orphaned:
        # The row is already gone; a 500 here would be a lie regardless of
        # cause, so the whole per-URL body -- including resolving the name,
        # which can raise on a storage misconfiguration -- is best-effort.
        try:
            name = storage.object_name_for(url)
            if not name:  # not one of our own objects (or an unsafe key) -- skip
                continue
            storage.delete_object(name)
        except Exception as exc:
            app.logger.warning("failed to delete storage object for %s: %s", url, exc)

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True, port=5000)  # local only; Vercel imports `app` instead
