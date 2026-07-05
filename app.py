import json
import os
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder="static", static_url_path="")

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "runs.json")


def load_runs():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE) as f:
        return json.load(f)


def save_runs(runs):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(runs, f, indent=2)


@app.route("/")
def home():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/runs")
def runs_page():
    return send_from_directory(app.static_folder, "runs.html")


@app.route("/api/runs", methods=["GET"])
def get_runs():
    return jsonify(load_runs())


@app.route("/api/runs", methods=["POST"])
def add_run():
    data = request.get_json(force=True)
    runs = load_runs()
    run = {
        "id": (max((r["id"] for r in runs), default=0) + 1),
        "title": data.get("title", ""),
        "distance": float(data.get("distance", 0)),
        "pace": float(data.get("pace", 0)),
        "heart_rate": float(data.get("heart_rate", 0)) if data.get("heart_rate") else None,
        "date": data.get("date", ""),
    }
    runs.append(run)
    save_runs(runs)
    return jsonify(run), 201


if __name__ == "__main__":
    app.run(debug=True, port=5000)
