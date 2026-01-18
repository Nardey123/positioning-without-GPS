#include <WiFi.h>
#include <HardwareSerial.h>

// --- Configuration TTN ---
const char* devEui = "70B3D57ED007366D";
const char* appEui = "0000000000000000";
const char* appKey = "DD6383350277F8AEA65FCF59D122B17F"; 

// --- Configuration LoRa-E5 ---
#define LORA_TX 17
#define LORA_RX 16
HardwareSerial LoRaSerial(2);

// --- Intervalle d'envoi ---
const unsigned long LORAWAN_TX_INTERVAL = 15000; // 15 secondes

// --- Statut de la connexion ---
bool isJoined = false;

// --- Envoi commande AT + lecture réponse ---
void sendAndRead(const String& command, unsigned long timeout) {
    Serial.println("-> Sending: " + command);
    LoRaSerial.println(command);
    
    unsigned long startTime = millis();
    while (millis() - startTime < timeout) {
        if (LoRaSerial.available()) {
            Serial.write(LoRaSerial.read());
        }
    }
    Serial.println();
}

// --- Conversion "AA:BB:CC:DD:EE:FF" -> 6 octets ---
void macStringToBytes(const String& macStr, uint8_t* byte_array) {
    sscanf(macStr.c_str(), "%hhx:%hhx:%hhx:%hhx:%hhx:%hhx", 
           &byte_array[0], &byte_array[1], &byte_array[2], 
           &byte_array[3], &byte_array[4], &byte_array[5]);
}

// --- Test si MAC est globalement administrée (U/L = 0) ---
// bit 1 du premier octet = 0 → universelle ; 1 → locale/random
bool isGloballyAdministered(const uint8_t* bssid) {
    return (bssid[0] & 0x02) == 0;
}

void setup() {
    Serial.begin(115200);
    LoRaSerial.begin(9600, SERIAL_8N1, LORA_RX, LORA_TX);
    
    Serial.println("--- Démarrage du programme de scan WiFi LoRaWAN ---");

    // --- Config LoRaWAN ---
    sendAndRead("AT", 1000);
    sendAndRead("AT+ID=DevEui,\"" + String(devEui) + "\"", 1000);
    sendAndRead("AT+ID=AppEui,\"" + String(appEui) + "\"", 1000);
    sendAndRead("AT+KEY=APPKEY,\"" + String(appKey) + "\"", 1000);
    sendAndRead("AT+MODE=LWOTAA", 1000);
    sendAndRead("AT+DR=EU868", 1000);
    sendAndRead("AT+CLASS=A", 1000);

    // --- Join réseau ---
    Serial.println("Tentative de connexion au réseau...");
    while (!isJoined) {
        LoRaSerial.println("AT+JOIN");
        unsigned long joinStartTime = millis();
        String response = "";
        while (millis() - joinStartTime < 20000) { // Timeout 20s
            if (LoRaSerial.available()) {
                char c = LoRaSerial.read();
                Serial.write(c);
                response += c;
                if (response.indexOf("Joined") > -1 || response.indexOf("joined") > -1) {
                    isJoined = true;
                    break;
                }
            }
        }

        if (isJoined) {
            Serial.println("\nConnexion au réseau réussie !");
        } else {
            Serial.println("\nÉchec de la connexion, nouvelle tentative dans 10s...");
            delay(10000);
        }
    }

    // --- Init WiFi (scan uniquement) ---
    Serial.println("Initialisation du WiFi pour le scan...");
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();
    delay(100);
    Serial.println("Setup terminé. Entrée dans la boucle principale.");
}

void loop() {
    Serial.println("\n--- DÉBUT DE LA BOUCLE ---");

    Serial.println("1. Lancement du scan WiFi...");
    int n = WiFi.scanNetworks();
    Serial.print("2. Scan terminé. ");
    Serial.print(n);
    Serial.println(" réseaux trouvés.");

    // Affichage complet + info global/local
    int globalCount = 0;
    for (int i = 0; i < n; i++) {
        uint8_t* bssid = WiFi.BSSID(i);
        bool globalMac = isGloballyAdministered(bssid);

        if (globalMac) globalCount++;

        Serial.print("Réseau #");
        Serial.print(i);
        Serial.print("  SSID: ");
        Serial.print(WiFi.SSID(i));
        Serial.print("  BSSID: ");
        Serial.print(WiFi.BSSIDstr(i));
        Serial.print("  RSSI: ");
        Serial.print(WiFi.RSSI(i));
        Serial.print(" dBm  Canal: ");
        Serial.print(WiFi.channel(i));
        Serial.print("  Sécurité: ");
        wifi_auth_mode_t auth = WiFi.encryptionType(i);
        Serial.print(auth == WIFI_AUTH_OPEN ? "OPEN" : "SECURE");
        Serial.print("  MAC globale: ");
        Serial.println(globalMac ? "OUI" : "NON");
    }

    if (globalCount < 3) {
        Serial.print("Moins de 3 réseaux à MAC globale. Trouvés: ");
        Serial.println(globalCount);
        Serial.println("Attente...");
        delay(LORAWAN_TX_INTERVAL);
        return;
    }

    Serial.println("3. Recherche des 3 meilleurs signaux (MAC globales uniquement)...");
    int best_rssi[3]    = {-128, -128, -128};
    int best_indices[3] = {-1, -1, -1};

    for (int i = 0; i < n; ++i) {
        uint8_t* bssid = WiFi.BSSID(i);
        if (!isGloballyAdministered(bssid)) {
            // MAC locale/random → on ignore pour la localisation
            continue;
        }

        int rssi = WiFi.RSSI(i);

        if (rssi > best_rssi[0]) {
            // Décale 0 -> 1, 1 -> 2
            best_rssi[2] = best_rssi[1];
            best_indices[2] = best_indices[1];

            best_rssi[1] = best_rssi[0];
            best_indices[1] = best_indices[0];

            best_rssi[0] = rssi;
            best_indices[0] = i;
        }
        else if (rssi > best_rssi[1]) {
            // Décale 1 -> 2
            best_rssi[2] = best_rssi[1];
            best_indices[2] = best_indices[1];

            best_rssi[1] = rssi;
            best_indices[1] = i;
        }
        else if (rssi > best_rssi[2]) {
            best_rssi[2] = rssi;
            best_indices[2] = i;
        }
    }

    // Sécurité : vérifier qu'on a bien 3 indices valides
    if (best_indices[0] < 0 || best_indices[1] < 0 || best_indices[2] < 0) {
        Serial.println("Erreur: impossible de sélectionner 3 AP à MAC globale valides.");
        delay(LORAWAN_TX_INTERVAL);
        return;
    }

    Serial.printf("4. AP1: %s, RSSI: %d\n", WiFi.BSSIDstr(best_indices[0]).c_str(), best_rssi[0]);
    Serial.printf("   AP2: %s, RSSI: %d\n", WiFi.BSSIDstr(best_indices[1]).c_str(), best_rssi[1]);
    Serial.printf("   AP3: %s, RSSI: %d\n", WiFi.BSSIDstr(best_indices[2]).c_str(), best_rssi[2]);

    Serial.println("5. Construction du payload (3 MAC + 3 RSSI)...");
    uint8_t payload[21];

    // AP1 : MAC (0..5) + RSSI (6)
    macStringToBytes(WiFi.BSSIDstr(best_indices[0]), &payload[0]);
    payload[6] = (int8_t)best_rssi[0];

    // AP2 : MAC (7..12) + RSSI (13)
    macStringToBytes(WiFi.BSSIDstr(best_indices[1]), &payload[7]);
    payload[13] = (int8_t)best_rssi[1];

    // AP3 : MAC (14..19) + RSSI (20)
    macStringToBytes(WiFi.BSSIDstr(best_indices[2]), &payload[14]);
    payload[20] = (int8_t)best_rssi[2];

    // Conversion en hex pour AT+MSGHEX
    String hexPayload = "";
    for (int i = 0; i < 21; i++) {
        char hex[3];
        sprintf(hex, "%02X", payload[i]);
        hexPayload += hex;
    }

    Serial.println("6. Envoi des données LoRaWAN : AT+MSGHEX=" + hexPayload);
    sendAndRead("AT+MSGHEX=" + hexPayload, 10000);
    
    Serial.println("7. Données envoyées. Attente de 15 secondes.");
    delay(LORAWAN_TX_INTERVAL);
}
