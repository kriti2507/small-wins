import json
import os
import time
import uuid
from datetime import timedelta
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, g, jsonify, request, session
from werkzeug.security import check_password_hash

import db
import storage

# Local dev reads DB/storage config from backend/.env; on Vercel these come
# from the dashboard and this call is a harmless no-op.
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# API only: the React frontend is served separately (Vite in dev, Vercel static
# in prod). This app exposes just the /api/* contract.
app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB per upload

# --- Auth ------------------------------------------------------------------
# Single-admin auth. If ADMIN_PASSWORD_HASH is unset (local dev), every request
# is treated as admin. In production, set ADMIN_PASSWORD_HASH and SECRET_KEY.
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH")
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-not-secret")
if ADMIN_PASSWORD_HASH and app.secret_key == "dev-only-not-secret":
    raise RuntimeError("SECRET_KEY must be set when ADMIN_PASSWORD_HASH is configured")
app.permanent_session_lifetime = timedelta(days=30)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = bool(ADMIN_PASSWORD_HASH)

# Behind Vercel (a reverse proxy), trust X-Forwarded-For so the login rate
# limit sees real client IPs. Set TRUST_PROXY=1 in the Vercel env.
if os.environ.get("TRUST_PROXY"):
    from werkzeug.middleware.proxy_fix import ProxyFix

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

# Failed-login timestamps per IP. Best-effort on serverless (resets on cold
# starts); acceptable for a single admin.
LOGIN_ATTEMPTS = {}
MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 60


@app.teardown_appcontext
def _close_db(exc):
    conn = g.pop("db_conn", None)
    if conn is not None:
        conn.close()


def is_admin():
    return ADMIN_PASSWORD_HASH is None or bool(session.get("is_admin"))


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not is_admin():
            return jsonify({"error": "Only admin can make changes."}), 403
        return fn(*args, **kwargs)

    return wrapper


def too_many_attempts(ip):
    now = time.time()
    recent = [t for t in LOGIN_ATTEMPTS.get(ip, []) if now - t < LOGIN_WINDOW_SECONDS]
    LOGIN_ATTEMPTS[ip] = recent
    return len(recent) >= MAX_LOGIN_ATTEMPTS


@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    return jsonify({"is_admin": is_admin()})


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    if ADMIN_PASSWORD_HASH is None:
        return jsonify({"is_admin": True})  # dev mode: nothing to check

    ip = request.remote_addr or "unknown"
    if too_many_attempts(ip):
        return jsonify({"error": "Too many attempts. Try again in a minute."}), 429

    data = request.get_json(silent=True)
    password = data.get("password") if isinstance(data, dict) else None
    if not isinstance(password, str):
        password = ""
    if not check_password_hash(ADMIN_PASSWORD_HASH, password):
        LOGIN_ATTEMPTS.setdefault(ip, []).append(time.time())
        return jsonify({"error": "Wrong password."}), 401

    session.permanent = True
    session["is_admin"] = True
    return jsonify({"is_admin": True})


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    session.clear()
    return jsonify({"is_admin": False})


# Color ids the frontend palette offers; the first is the default.
COLORS = [
    "green", "blue", "orange", "purple", "teal", "rose",
    "red", "amber", "indigo", "cyan", "lime", "slate",
]

# Tile layouts a topic can use for its entry list; the first is the default.
LAYOUTS = ("photo-top", "thumbnail")

ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_BODY_BYTES = 1_000_000  # serialized cap; well under the 5 MB request limit

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
    doc = db.load_post(slug, entry["id"])
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


def referenced_images():
    """Every image URL still referenced anywhere, across all topics: hero
    images plus in-body figures. Callers deleting an entry must compute this
    AFTER the row delete, or the entry being removed still counts as a
    reference and nothing is ever cleaned up.
    """
    urls = set(db.all_entry_images())
    for doc in db.all_post_docs():
        urls |= image_urls_in(doc)
    return urls


# --- Topics API ------------------------------------------------------------

@app.route("/api/topics", methods=["GET"])
def get_topics():
    return jsonify(db.load_topics())


@app.route("/api/topics", methods=["POST"])
@admin_required
def add_topic():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    slug = slugify(name)
    if not slug:
        return jsonify({"error": "A topic name is required."}), 400
    if db.find_topic(slug):
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
    db.add_topic(topic)
    return jsonify(topic), 201


@app.route("/api/topics/<slug>", methods=["PATCH"])
@admin_required
def update_topic(slug):
    topic = db.find_topic(slug)
    if not topic:
        return jsonify({"error": "Unknown topic."}), 404

    data = request.get_json(force=True)
    if "layout" in data:
        if data["layout"] not in LAYOUTS:
            return jsonify({"error": "Invalid layout."}), 400
        topic = db.set_topic_layout(slug, data["layout"])

    return jsonify(topic)


# --- Uploads API -----------------------------------------------------------

@app.route("/api/uploads", methods=["POST"])
@admin_required
def upload_file():
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "No file provided."}), 400
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXT:
        return jsonify({"error": "Unsupported file type."}), 400
    name = f"{uuid.uuid4().hex}.{ext}"
    url = storage.upload_bytes(name, file.read(), file.mimetype or "application/octet-stream")
    return jsonify({"url": url}), 201


# --- Entries API -----------------------------------------------------------

@app.route("/api/topics/<slug>/entries", methods=["GET"])
def get_entries(slug):
    if not db.find_topic(slug):
        return jsonify({"error": "Unknown topic."}), 404
    return jsonify([with_body(slug, e) for e in db.load_entries(slug)])


@app.route("/api/topics/<slug>/entries", methods=["POST"])
@admin_required
def add_entry(slug):
    topic = db.find_topic(slug)
    if not topic:
        return jsonify({"error": "Unknown topic."}), 404

    data = request.get_json(force=True)
    entry = {
        "id": db.next_entry_id(slug),
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

    db.save_entry(slug, entry)
    return jsonify(entry), 201


@app.route("/api/topics/<slug>/entries/<int:entry_id>", methods=["GET"])
def get_entry(slug, entry_id):
    if not db.find_topic(slug):
        return jsonify({"error": "Unknown topic."}), 404
    entry = db.find_entry(slug, entry_id)
    if not entry:
        return jsonify({"error": "Unknown entry."}), 404
    return jsonify(with_body(slug, entry))


@app.route("/api/topics/<slug>/entries/<int:entry_id>", methods=["PATCH"])
@admin_required
def update_entry(slug, entry_id):
    topic = db.find_topic(slug)
    if not topic:
        return jsonify({"error": "Unknown topic."}), 404

    entry = db.find_entry(slug, entry_id)
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
        db.save_post(slug, entry_id, body)

    db.save_entry(slug, entry)
    return jsonify(with_body(slug, entry))


@app.route("/api/topics/<slug>/entries/<int:entry_id>", methods=["DELETE"])
@admin_required
def delete_entry(slug, entry_id):
    if not db.find_topic(slug):
        return jsonify({"error": "Unknown topic."}), 404

    entry = db.find_entry(slug, entry_id)
    if not entry:
        return jsonify({"error": "Unknown entry."}), 404

    # Gather this entry's images before it's gone, so we know what *might*
    # become orphaned.
    candidates = image_urls_in(db.load_post(slug, entry_id))
    if entry.get("image"):
        candidates.add(entry["image"])

    db.delete_entry(slug, entry_id)  # posts row cascades with it

    # Only now, with the row already gone, can "is this still referenced?"
    # be answered correctly -- otherwise the entry being deleted would count
    # as its own reference and nothing would ever be cleaned up.
    orphaned = candidates - referenced_images()
    for url in orphaned:
        name = storage.object_name_for(url)
        if not name:  # not one of our own objects (or an unsafe key) -- skip
            continue
        try:
            storage.delete_object(name)
        except Exception as exc:
            # The row is already gone; a 500 here would be a lie. Best-effort
            # cleanup, logged so orphaned files can be found later.
            app.logger.warning("failed to delete storage object %s: %s", name, exc)

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=ADMIN_PASSWORD_HASH is None, port=5000)
