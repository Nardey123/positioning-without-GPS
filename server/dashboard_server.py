from flask import Flask, jsonify, render_template, request
import datetime
import sqlite3
import os
import sys
from pathlib import Path

# --- CONFIGURATION DES CHEMINS ---
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
TEMPLATE_DIR = CURRENT_DIR / "templates"
DB_PATH = PROJECT_ROOT / "data" / "processed" / "wifi_data_live.db"
AP_DB_PATH = PROJECT_ROOT / "data" / "processed" / "wiggle_data_app_phone.db"

# Ajout du dossier racine au path pour importer src
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.localization.update_position import localize_last_scan


app = Flask(__name__, template_folder=str(TEMPLATE_DIR))

def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def check_ap_known(bssid):
    if not AP_DB_PATH.exists(): return False
    try:
        with sqlite3.connect(str(AP_DB_PATH)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM access_points WHERE lower(bssid) = lower(?)", (bssid,))
            return cursor.fetchone() is not None
    except:
        return False

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # --- NETTOYAGE (Gardé pour le dev) ---
    print("[INIT] Suppression des anciennes données...")
    c.execute("DROP TABLE IF EXISTS wifi_scans")
    c.execute("DROP TABLE IF EXISTS node_positions")

    c.execute("""CREATE TABLE wifi_scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        bssid TEXT,
        rssi INTEGER,
        ap_index INTEGER
    )""")
    
    c.execute("""CREATE TABLE node_positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        est_lat REAL,
        est_lon REAL
    )""")

    # --- AJOUT D'UNE POSITION DE TEST ICI ---
    
    import datetime
    now = datetime.datetime.utcnow().isoformat()
    #c.execute("INSERT INTO node_positions (timestamp, est_lat, est_lon) VALUES (?, ?, ?)", 
    #          (now, 48.8470, 2.3574))
    #print("[INIT] Position de test insérée (Le bonhomme devrait apparaître).")
    # ----------------------------------------

    conn.commit()
    conn.close()
    print("[INIT] Base de données réinitialisée.")

# On lance le nettoyage dès le démarrage du script
init_db()

# --- RECEPTION TTN ---

@app.post("/ttn")
def ttn_ingest():
    try:
        data = request.json
        uplink = data.get("uplink_message", {})
        payload = uplink.get("decoded_payload", {})
        
        # On récupère les APs
        aps = []
        if payload:
            for key in ["ap1", "ap2", "ap3"]:
                if payload.get(key): aps.append(payload[key])

        conn = get_db()
        c = conn.cursor()
        ts = datetime.datetime.utcnow().isoformat()
        
        # --- MODIFICATION ICI ---
        if not aps:
            # Cas où aucune MAC n'est trouvée : On écrit quand même une ligne d'alerte
            # On met ap_index à -1 pour le reconnaître plus tard dans le HTML
            c.execute("INSERT INTO wifi_scans (timestamp, bssid, rssi, ap_index) VALUES (?, ?, ?, ?)",
                      (ts, "AUCUNE DONNÉE", 0, -1))
            print(f"[TTN] Message reçu mais AUCUN réseau WiFi (Log enregistré).")
        else:
            # Vérifier si au moins un AP est connu
            known_found = False
            for ap in aps:
                if "bssid" in ap and check_ap_known(ap["bssid"]):
                    known_found = True
                    break
            
            if not known_found:
                 c.execute("INSERT INTO wifi_scans (timestamp, bssid, rssi, ap_index) VALUES (?, ?, ?, ?)",
                      (ts, "Reseaux inconnus dans le dataset", 0, -2))

            # Cas normal : on enregistre les réseaux trouvés
            for idx, ap in enumerate(aps):
                if "bssid" in ap:
                    c.execute("INSERT INTO wifi_scans (timestamp, bssid, rssi, ap_index) VALUES (?, ?, ?, ?)",
                              (ts, ap["bssid"], ap["rssi"], idx))
            print(f"[TTN] Reçu {len(aps)} points WiFi.")

        conn.commit()
        conn.close()

        # --- CALCUL DE LA POSITION ---
        try:
            localize_last_scan()
        except Exception as e:
            print(f"[ERROR] Localisation failed: {e}")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 500
    
# --- APIS FRONTEND ---

@app.get("/api/history")
def api_history():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT timestamp, est_lat, est_lon FROM node_positions ORDER BY id DESC LIMIT 50")
    rows = c.fetchall()
    conn.close()
    return jsonify([{"time": r["timestamp"], "lat": r["est_lat"], "lon": r["est_lon"]} for r in rows])

@app.get("/api/logs")
def api_logs():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT timestamp, bssid, rssi, ap_index FROM wifi_scans ORDER BY id DESC LIMIT 50")
    rows = c.fetchall()
    conn.close()
    
    logs = []
    for r in rows:
        try: clean_time = r["timestamp"].split("T")[1].split(".")[0]
        except: clean_time = r["timestamp"]
        logs.append({
            "time": clean_time, "bssid": r["bssid"], "rssi": r["rssi"], "ap": r["ap_index"]
        })
    return jsonify(logs)

@app.route("/")
def index():
    return render_template("dashboard.html")

if __name__ == "__main__":
    print(f"[INFO] Serveur prêt sur port 5000")
    app.run(port=5000, debug=True)