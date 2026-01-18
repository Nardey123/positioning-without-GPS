import sqlite3
import csv
import os

DB_PATH = "ap_jussieu.db"          
CSV_PATH = "wigle_data_app_phone.csv"    

def main():
    # Vérifier que le CSV existe
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"Fichier CSV introuvable : {CSV_PATH}")

    # Connexion à la base
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Création de la table des points d'accès (si elle n'existe pas)
    c.execute("""
        CREATE TABLE IF NOT EXISTS access_points (
            bssid TEXT PRIMARY KEY,   -- netid / adresse MAC
            ssid TEXT,
            lat REAL,                 -- trilat
            lon REAL,                 -- trilong
            last_seen TEXT            -- lasttime (on garde en texte ISO)
        )
    """)

    # Lecture du CSV et insertion
    with open(CSV_PATH, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            # Adaptation aux noms de colonnes que tu as donnés
            bssid = row["netid"].strip().upper()
            ssid = row.get("ssid", "").strip()

            # Gestion de lat/lon (au cas où il y aurait des valeurs vides)
            lat_str = row.get("trilat", "").strip()
            lon_str = row.get("trilong", "").strip()

            lat = float(lat_str) if lat_str else None
            lon = float(lon_str) if lon_str else None

            last_seen = row.get("lasttime", "").strip()

            c.execute(
                """
                INSERT OR REPLACE INTO access_points
                    (bssid, ssid, lat, lon, last_seen)
                VALUES (?, ?, ?, ?, ?)
                """,
                (bssid, ssid, lat, lon, last_seen)
            )

    conn.commit()
    conn.close()
    print("Import terminé : données Wigle → table access_points dans wifi_data.db")

if __name__ == "__main__":
    main()
