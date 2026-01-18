import sqlite3
import os
import sys
import time
from pathlib import Path

# Ensure imports work when run as a script or module
PROJECT_ROOT = Path(__file__).resolve().parents[2]  # PROJET/
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    # When executed as a module: python -m src.localization.update_position
    from .weights import rssi_weight
except ImportError:
    # When executed directly: python src/localization/update_position.py
    from src.localization.weights import rssi_weight

DEFAULT_WIFI_DB = PROJECT_ROOT / "data" / "processed" / "wifi_data_live.db"
DEFAULT_AP_DB = PROJECT_ROOT / "data" / "processed" / "wiggle_data_app_phone.db"


env_wifi = os.getenv("WIFI_DB")
env_ap = os.getenv("AP_DB")
WIFI_DB = str(Path(env_wifi) if env_wifi and Path(env_wifi).is_absolute() else (PROJECT_ROOT / Path(env_wifi) if env_wifi else DEFAULT_WIFI_DB))
AP_DB = str(Path(env_ap) if env_ap and Path(env_ap).is_absolute() else (PROJECT_ROOT / Path(env_ap) if env_ap else DEFAULT_AP_DB))

def localize_last_scan():
    Path(WIFI_DB).parent.mkdir(parents=True, exist_ok=True)
    if not os.path.exists(WIFI_DB):
        raise FileNotFoundError(WIFI_DB)
    if not os.path.exists(AP_DB):
        raise FileNotFoundError(AP_DB)

    conn = sqlite3.connect(WIFI_DB)
    c = conn.cursor()
    # Assurer l'existence de la table node_positions dès le début
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS node_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT UNIQUE,
            est_lat REAL,
            est_lon REAL
        )
        """
    )
    c.execute("SELECT timestamp FROM wifi_scans ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    if row is None:
        conn.close(); return
    last_ts = row[0]
    c.execute(f"ATTACH DATABASE '{AP_DB}' AS apdb;")
    c.execute(
        """
        SELECT s.bssid, s.rssi, ap.lat, ap.lon
        FROM wifi_scans AS s
        JOIN apdb.access_points AS ap
             ON UPPER(s.bssid) = ap.bssid
        WHERE s.timestamp = ?
        ORDER BY s.ap_index ASC
        """,
        (last_ts,)
    )
    aps = c.fetchall()
    if not aps:
        conn.close(); print(f"[LOCALISATION] {last_ts} → aucun BSSID trouvé"); return
    weights = []; lats = []; lons = []
    for bssid, rssi, lat, lon in aps:
        if lat is None or lon is None: continue
        w = rssi_weight(rssi)
        weights.append(w); lats.append(lat); lons.append(lon)
    if not weights:
        conn.close(); print(f"[LOCALISATION] {last_ts} → AP sans coords"); return
    sumw = sum(weights)
    est_lat = sum(w * la for w, la in zip(weights, lats)) / sumw
    est_lon = sum(w * lo for w, lo in zip(weights, lons)) / sumw
    # Upsert simple: IGNORE si déjà présent pour ce timestamp
    c.execute(
        "INSERT OR IGNORE INTO node_positions (timestamp, est_lat, est_lon) VALUES (?, ?, ?)",
        (last_ts, est_lat, est_lon)
    )
    conn.commit(); conn.close()
    print(f"[LOCALISATION] {last_ts} → lat={est_lat:.6f}, lon={est_lon:.6f}")

if __name__ == "__main__":
    interval = float(os.getenv("LOCALIZE_INTERVAL", "10"))  # secondes
    print(f"[LOCALISATION LOOP] Interval = {interval}s | WIFI_DB={WIFI_DB} | AP_DB={AP_DB}")
    try:
        while True:
            localize_last_scan()
            time.sleep(interval)
    except KeyboardInterrupt:
        print("[LOCALISATION LOOP] Arrêt demandé (Ctrl+C).")
