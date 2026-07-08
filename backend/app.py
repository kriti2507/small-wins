import json
import os
import re
from flask import Flask, jsonify, request

# API only: the React frontend is served separately (Vite in dev, a static
# host in prod). This app exposes just the /api/* contract.
app = Flask(__name__, static_folder=None)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
TOPICS_FILE = os.path.join(DATA_DIR, "topics.json")


# Color ids the frontend palette offers; the first is the default.
COLORS = [
    "green", "blue", "orange", "purple", "teal", "rose",
    "red", "amber", "indigo", "cyan", "lime", "slate",
]


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

    topic = {"slug": slug, "name": name, "color": color, "fields": fields}
    topics.append(topic)
    save_json(TOPICS_FILE, topics)
    save_json(entries_path(slug), [])
    return jsonify(topic), 201


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


if __name__ == "__main__":
    app.run(debug=True, port=5000)
