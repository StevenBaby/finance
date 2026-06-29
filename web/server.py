"""Gold Pulse Web — Flask backend, reuses src/api.py for data."""
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_here), "src"))

from flask import Flask, jsonify, render_template
from api import fetch_all_gold

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/gold")
def api_gold():
    try:
        result = fetch_all_gold()
        # Add display labels and normalize numeric types
        for key, label in [("london", "昨结"), ("newyork", "昨收"), ("shanghai", "昨收")]:
            item = result.get(key)
            if item:
                item["label"] = label
                # api.py may return high/low as raw strings for london/newyork
                for field in ("high", "low"):
                    v = item.get(field)
                    if isinstance(v, str):
                        try:
                            item[field] = float(v) if v.strip() else 0.0
                        except ValueError:
                            item[field] = 0.0
        result["timestamp"] = None
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 18888))
    app.run(host="0.0.0.0", port=port, debug=False)
