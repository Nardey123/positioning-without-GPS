from flask import Flask, request, jsonify
import sqlite3
import datetime
import os
from pathlib import Path

# Pour exposer localement via ngrok (dans le terminal²)     :
#ngrok http --domain=cartable-grittily-beatriz.ngrok-free.dev 5000

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # PROJET/
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "processed" / "wifi_data_live.db"

env_db = os.getenv("WIFI_DB")
if env_db:
    candidate = Path(env_db)
    WIFI_DB = str(candidate if candidate.is_absolute() else PROJECT_ROOT / candidate)
else:
    WIFI_DB = str(DEFAULT_DB_PATH)

app = Flask(__name__)

def get_db():
    Path(WIFI_DB).parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(WIFI_DB)

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS wifi_scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            bssid TEXT,
            rssi INTEGER,
            ap_index INTEGER
        )
        """
    )
    conn.commit()
    conn.close()

init_db()

@app.post("/ttn")
def ttn_handler():
    data = request.json
    payload = data["uplink_message"]["decoded_payload"]
    aps = [
        ("ap1", payload["ap1"]),
        ("ap2", payload["ap2"]),
        ("ap3", payload["ap3"])
    ]

    conn = get_db()
    c = conn.cursor()
    timestamp = datetime.datetime.utcnow().isoformat()

    for index, (name, ap) in enumerate(aps):
        c.execute(
            "INSERT INTO wifi_scans (timestamp, bssid, rssi, ap_index) VALUES (?, ?, ?, ?)",
            (timestamp, ap["bssid"], ap["rssi"], index)
        )

    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "received": aps})

@app.get("/")
def index():
    return "Serveur TTN OK"

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    print(f"[TTN SERVER] Using DB: {WIFI_DB}")
    app.run(port=port, debug=True)
