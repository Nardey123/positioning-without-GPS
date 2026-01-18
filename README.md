Géolocalisation sans GPS : WiFi sniffing via LoRaWAN (ESP32)
===========================================================

Présentation rapide
-------------------
- Objectif : estimer la position d'un nœud ESP32 sans GPS en sniffant les réseaux WiFi, puis en envoyant les BSSID/RSSI via LoRaWAN vers The Things Network (TTN).
- Chaîne complète : ESP32 (sniff) → TTN → webhook ngrok → Flask backend → base SQLite → dashboard web.

Architecture des dossiers
-------------------------
- [WIFI-CAPTURED-TO-LORAWAN/WIFI-CAPTURED-TO-LORAWAN.ino](WIFI-CAPTURED-TO-LORAWAN/WIFI-CAPTURED-TO-LORAWAN.ino) : firmware ESP32 qui scanne le WiFi et envoie ap1/ap2/ap3 ayant une plus forte intensité que les autres (bssid, rssi) via LoRaWAN.
- [server/dashboard_server.py](server/dashboard_server.py) : serveur Flask qui reçoit les uplinks TTN, écrit dans la base `wifi_data_live.db` et calcule la position.
- [server/templates/dashboard.html](server/templates/dashboard.html) : front affichant la trace et les derniers scans.
- [scripts/build_ap_db.py](scripts/build_ap_db.py) : construit la base des points d'accès connus à partir du CSV Wigle.
- [src/localization/update_position.py](src/localization/update_position.py) : calcule la position à partir du dernier scan WiFi (moyenne pondérée des AP connus).
- [src/localization/weights.py](src/localization/weights.py) : fonction de poids RSSI utilisée par le calcul.
- Données :
  - [data/raw/wigle_jussieu.csv](data/raw/wigle_jussieu.csv) (ou `wiggle_data_app_phone.csv`) : export Wigle. (Via requete API + application Wigle sur Android)
  - [data/processed/ap_jussieu.db](data/processed/ap_jussieu.db) : base des AP connus (bssid, ssid, lat, lon).
  - [data/processed/wifi_data_live.db](data/processed/wifi_data_live.db) : base temps réel des scans et positions calculées.

Pré-requis
----------
- Python 3.10+ recommandé.
- Flask, sqlite3 (standard), dépendances listées dans le projet (install via `pip install flask` + ce qu'il manque si erreur).
- ngrok pour exposer le webhook TTN (exemple : `ngrok http 5000`).
- Compte TTN et application configurée pour l'ESP32 LoRaWAN.

Initialisation des données
--------------------------
1) Construire la base des AP connus depuis le CSV Wigle :

```bash
python scripts/build_ap_db.py
```

Par défaut, lit `data/raw/wigle_jussieu.csv` et écrit `data/processed/ap_jussieu.db`. Vous pouvez surcharger via variables d'environnement : `RAW_WIGLE` (CSV) et `AP_DB` (chemin DB AP).

2) (Optionnel) Vérifier la base :

```bash
sqlite3 data/processed/ap_jussieu.db "SELECT COUNT(*) FROM access_points;"
```

Lancement du backend et du dashboard
------------------------------------
1) Démarrer ngrok pour créer une URL publique vers le port 5000 :

```bash
ngrok http 5000
```

2) Copier l'URL https fournie par ngrok dans la configuration Webhook TTN (route POST vers `/ttn`).

3) Lancer le serveur Flask :

```bash
python server/dashboard_server.py
```

Le serveur :
- initialise `data/processed/wifi_data_live.db` (tables `wifi_scans` et `node_positions`),
- reçoit les uplinks TTN sur `/ttn`,
- enregistre les AP reçus (`wifi_scans`),
- calcule la position via `localize_last_scan()` (moyenne pondérée des AP connus) et enregistre dans `node_positions`,
- expose l'API `/api/history` et le dashboard sur `/`.

4) Ouvrir le dashboard : http://localhost:5000/

ESP32 / firmware
----------------
- Flasher [WIFI-CAPTURED-TO-LORAWAN/WIFI-CAPTURED-TO-LORAWAN.ino](WIFI-CAPTURED-TO-LORAWAN/WIFI-CAPTURED-TO-LORAWAN.ino) avec vos clés LoRaWAN (DevEUI/AppEUI/AppKey).
- Le firmware scanne et envoie jusqu'à 3 AP (ap1, ap2, ap3) dans `decoded_payload` côté TTN.

API utiles (backend)
--------------------
- POST `/ttn` : point d'entrée Webhook TTN (JSON uplink).
- GET `/api/history` : retourne les dernières positions calculées (table `node_positions`).
- GET `/api/logs` : retourne les derniers scans WiFi (table `wifi_scans`).

Flux de données (résumé)
------------------------
1) ESP32 → LoRaWAN → TTN : envoi des BSSID/RSSI.
2) TTN → ngrok → Flask `/ttn` : réception du JSON.
3) Écriture `wifi_scans` + localisation (poids RSSI) → `node_positions` dans `wifi_data_live.db`.
4) Dashboard lit `/api/history` et affiche la position estimée.

Dépannage rapide
----------------
- Pas de point sur la carte : vérifier que `node_positions` contient des lignes (`sqlite3 data/processed/wifi_data_live.db "SELECT * FROM node_positions LIMIT 5;"`).
- Aucun AP inséré : s'assurer que les BSSID reçus existent dans `access_points` (sinon pas de position calculable).
- URL Webhook TTN : vérifier l'URL ngrok utilisée et la route `/ttn`.
- En dev, on peut injecter un scan de test en postant un JSON minimal sur `/ttn` (voir structure attendue dans `dashboard_server.py`).
