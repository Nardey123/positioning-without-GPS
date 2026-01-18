import requests
import csv
import datetime

WIGLE_USER = "AID12c056e474b9dc563493dd1be5dd177d"
WIGLE_TOKEN = "20f0d78b3c01b6d0448559bd9e665d4a"
# -----------------

# 1. Configuration des dates
today = datetime.datetime.now()
two_years_ago = today - datetime.timedelta(days=730)
date_filter_api = two_years_ago.strftime("%Y%m%d") # Pour la requête API

print(f"Filtre API : Mises à jour DB après le {date_filter_api}")
print(f"Filtre strict : Dernière vue (lasttime) après le {two_years_ago.strftime('%Y-%m-%d')}")

bbox = {
    "latrange1": 48.840,
    "latrange2": 48.854,
    "longrange1": 2.343,
    "longrange2": 2.368,
}

params = {
    "onlymine": "false",
    "freenet": "false",
    "paynet": "false",
    "lastupdt": date_filter_api, 
    "first": 0,
    "maxresults": 100,
    **bbox,
}

output = "wigle_jussieu_recent_clean.csv"

# Écriture de l’en-tête
with open(output, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["netid", "ssid", "trilat", "trilong", "lasttime"])

while True:
    r = requests.get(
        "https://api.wigle.net/api/v2/network/search",
        params=params,
        auth=(WIGLE_USER, WIGLE_TOKEN),
    )
    
    if r.status_code != 200:
        print(f"Erreur API ({r.status_code}): {r.text}")
        break

    data = r.json()
    results = data.get("results", [])
    
    if not results:
        print("Plus de résultats bruts.")
        break

    count_kept = 0
    with open(output, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for row in results:
            lasttime_str = row.get("lasttime")
            
            # --- CORRECTION ICI : FILTRAGE MANUEL ---
            if lasttime_str:
                try:
                    # Format WiGLE typique: 2024-06-09T08:22:20.000Z
                    # On ne garde que la partie date/heure YYYY-MM-DDTHH:MM:SS
                    clean_ts = lasttime_str.split(".")[0] 
                    lasttime_dt = datetime.datetime.strptime(clean_ts, "%Y-%m-%dT%H:%M:%S")
                    
                    # Si la date de vue est PLUS VIEILLE que 2 ans, on ignore
                    if lasttime_dt < two_years_ago:
                        continue 
                        
                except ValueError:
                    
                    pass
            # ----------------------------------------

            writer.writerow([
                row.get("netid"),
                row.get("ssid"),
                row.get("trilat"),
                row.get("trilong"),
                lasttime_str
            ])
            count_kept += 1

    print(f"Page traitée : {len(results)} reçus -> {count_kept} conservés (récents)")

    if len(results) < params["maxresults"]:
        break

    params["first"] += params["maxresults"]

print("Extraction terminée.")