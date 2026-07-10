import json
import os
import re
import time
import uuid
from datetime import timedelta
from functools import wraps
from flask import Flask, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

# API only: the React frontend is served separately (Vite in dev, a static
# host in prod). This app exposes just the /api/* contract.
app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB per upload

# --- Auth ------------------------------------------------------------------
# Single-admin auth. If ADMIN_PASSWORD_HASH is unset (local dev), every
# request is treated as admin. In production, set:
#   ADMIN_PASSWORD_HASH  werkzeug hash of the admin password
#   SECRET_KEY           random string that signs the session cookie
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH")
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-not-secret")
app.permanent_session_lifetime = timedelta(days=30)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = bool(ADMIN_PASSWORD_HASH)

# Failed-login timestamps per IP, pruned to the last minute.
LOGIN_ATTEMPTS = {}
MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 60


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

    password = (request.get_json(force=True).get("password") or "")
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


DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
TOPICS_FILE = os.path.join(DATA_DIR, "topics.json")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "webp"}


# Color ids the frontend palette offers; the first is the default.
COLORS = [
    "green", "blue", "orange", "purple", "teal", "rose",
    "red", "amber", "indigo", "cyan", "lime", "slate",
]

# Tile layouts a topic can use for its entry list; the first is the default.
LAYOUTS = ("photo-top", "thumbnail")


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def save_json(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(value, f, indent=2)


DEFAULT_TOPICS = [
    {
        "slug": "runs",
        "name": "Runs",
        "color": "green",
        "fields": [
            {"key": "title", "label": "Title", "type": "text", "direction": "none"},
            {"key": "distance", "label": "Distance (km)", "type": "number", "direction": "higher"},
            {"key": "pace", "label": "Pace", "type": "pace", "direction": "lower"},
            {"key": "heart_rate", "label": "Heart rate (bpm)", "type": "number", "direction": "none"},
        ],
    }
]


def ensure_seed():
    if not os.path.exists(TOPICS_FILE):
        save_json(TOPICS_FILE, DEFAULT_TOPICS)


def load_topics():
    ensure_seed()
    return load_json(TOPICS_FILE, [])


def find_topic(slug):
    return next((t for t in load_topics() if t["slug"] == slug), None)


def entries_path(slug):
    return os.path.join(DATA_DIR, f"{slug}.json")


def load_entries(slug):
    return load_json(entries_path(slug), [])


# --- Topics API ------------------------------------------------------------

@app.route("/api/topics", methods=["GET"])
def get_topics():
    return jsonify(load_topics())


@app.route("/api/topics", methods=["POST"])
def add_topic():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    slug = slugify(name)
    if not slug:
        return jsonify({"error": "A topic name is required."}), 400

    topics = load_topics()
    if any(t["slug"] == slug for t in topics):
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
    topics.append(topic)
    save_json(TOPICS_FILE, topics)
    save_json(entries_path(slug), [])
    return jsonify(topic), 201


@app.route("/api/topics/<slug>", methods=["PATCH"])
def update_topic(slug):
    topics = load_topics()
    topic = next((t for t in topics if t["slug"] == slug), None)
    if not topic:
        return jsonify({"error": "Unknown topic."}), 404

    data = request.get_json(force=True)
    if "layout" in data:
        if data["layout"] not in LAYOUTS:
            return jsonify({"error": "Invalid layout."}), 400
        topic["layout"] = data["layout"]

    save_json(TOPICS_FILE, topics)
    return jsonify(topic)


# --- Uploads API -----------------------------------------------------------

@app.route("/api/uploads", methods=["POST"])
def upload_file():
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "No file provided."}), 400
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXT:
        return jsonify({"error": "Unsupported file type."}), 400
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    name = secure_filename(f"{uuid.uuid4().hex}.{ext}")
    file.save(os.path.join(UPLOADS_DIR, name))
    return jsonify({"url": f"/api/uploads/{name}"}), 201


@app.route("/api/uploads/<path:filename>", methods=["GET"])
def serve_upload(filename):
    return send_from_directory(UPLOADS_DIR, filename)


# --- Entries API -----------------------------------------------------------

@app.route("/api/topics/<slug>/entries", methods=["GET"])
def get_entries(slug):
    if not find_topic(slug):
        return jsonify({"error": "Unknown topic."}), 404
    return jsonify(load_entries(slug))


@app.route("/api/topics/<slug>/entries", methods=["POST"])
def add_entry(slug):
    topic = find_topic(slug)
    if not topic:
        return jsonify({"error": "Unknown topic."}), 404

    data = request.get_json(force=True)
    entries = load_entries(slug)
    entry = {
        "id": (max((e["id"] for e in entries), default=0) + 1),
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

    entries.append(entry)
    save_json(entries_path(slug), entries)
    return jsonify(entry), 201


def find_entry(entries, entry_id):
    return next((e for e in entries if e["id"] == entry_id), None)


MAX_BODY_BYTES = 1_000_000  # serialized cap; well under the 5 MB request limit


def valid_body(body):
    """A post body is a TipTap doc: {"type": "doc", "content": [...]}."""
    if not isinstance(body, dict) or body.get("type") != "doc":
        return False
    if not isinstance(body.get("content", []), list):
        return False
    return len(json.dumps(body)) <= MAX_BODY_BYTES


@app.route("/api/topics/<slug>/entries/<int:entry_id>", methods=["GET"])
def get_entry(slug, entry_id):
    if not find_topic(slug):
        return jsonify({"error": "Unknown topic."}), 404
    entry = find_entry(load_entries(slug), entry_id)
    if not entry:
        return jsonify({"error": "Unknown entry."}), 404
    return jsonify(entry)


@app.route("/api/topics/<slug>/entries/<int:entry_id>", methods=["PATCH"])
def update_entry(slug, entry_id):
    if not find_topic(slug):
        return jsonify({"error": "Unknown topic."}), 404

    entries = load_entries(slug)
    entry = find_entry(entries, entry_id)
    if not entry:
        return jsonify({"error": "Unknown entry."}), 404

    data = request.get_json(force=True)
    if "body" in data:
        body = data["body"]
        if not valid_body(body):
            return jsonify({"error": "Invalid post body."}), 400
        entry["body"] = body

    save_json(entries_path(slug), entries)
    return jsonify(entry)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
