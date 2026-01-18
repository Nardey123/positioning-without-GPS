import os, shutil
from pathlib import Path
import sqlite3
import csv

RAW_CSV = os.getenv("RAW_WIGLE", "data/raw/wigle_jussieu.csv")
AP_DB = os.getenv("AP_DB", "data/processed/ap_jussieu.db")

COL_BSSID = "netid"; COL_SSID = "ssid"; COL_LAT = "trilat"; COL_LON = "trilong"

def build_ap_db():
    if not Path(RAW_CSV).exists():
        raise FileNotFoundError(RAW_CSV)
    Path(AP_DB).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(AP_DB)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS access_points (
            bssid TEXT PRIMARY KEY,
            ssid TEXT,
            lat REAL,
            lon REAL
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_access_points_lat_lon ON access_points(lat, lon)")
    rows = []
    skipped = 0
    with open(RAW_CSV, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                bssid = row.get(COL_BSSID, '').strip().upper()
                if not bssid: skipped += 1; continue
                ssid = row.get(COL_SSID, '').strip()
                if ssid == '<hidden ssid>': ssid = ''
                lat = row.get(COL_LAT, '').strip(); lon = row.get(COL_LON, '').strip()
                if not lat or not lon: skipped += 1; continue
                rows.append((bssid, ssid, float(lat), float(lon)))
            except Exception:
                skipped += 1
                continue
    if rows:
        c.executemany("INSERT OR REPLACE INTO access_points (bssid, ssid, lat, lon) VALUES (?, ?, ?, ?)", rows)
    conn.commit()
    c.execute("SELECT COUNT(*) FROM access_points")
    total = c.fetchone()[0]
    conn.close()
    print(f"AP DB construite: {len(rows)} insérées, {skipped} ignorées, total={total}")

if __name__ == '__main__':
    build_ap_db()
