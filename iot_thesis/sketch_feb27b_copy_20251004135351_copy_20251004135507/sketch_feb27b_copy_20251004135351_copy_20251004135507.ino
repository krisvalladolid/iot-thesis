#include <WiFi.h>
#include <FirebaseESP32.h>
#include <time.h>
#include <DHT.h>

// WiFi credentials
#define WIFI_SSID "GlobeAtHome_949E1_2.4"
#define WIFI_PASSWORD "HjvdGK7x112804"

// Firebase credentials
#define DATABASE_URL "https://iot-final-project-989bf-default-rtdb.firebaseio.com"
#define DATABASE_SECRET "2wnTAxpgtHd4fzUFL3V1cZzBBcYa7BL0XOC77Dj4"

// Hardware pins
#define SENSOR_POWER_PIN 12
#define SENSOR_READ_PIN 34
#define PUMP_PIN 26
#define DHT_PIN 4      // DHT11 Data Pin
#define DHT_TYPE DHT11 // DHT Sensor Type

// Calibration values
const int AIR_DRY = 2149;
const int SOIL_WET = 800;
const int SEMI_WET = 1409;
const int SOIL_DRY = 1731;

// Firebase objects
FirebaseData firebaseData;
FirebaseAuth auth;
FirebaseConfig config;

// DHT Sensor
DHT dht(DHT_PIN, DHT_TYPE);

// Timezone for Philippines (UTC+8)
const long gmtOffset_sec = 28800;
const int daylightOffset_sec = 0;

void setup() {
  Serial.begin(115200);
  pinMode(SENSOR_POWER_PIN, OUTPUT);
  pinMode(PUMP_PIN, OUTPUT);
  digitalWrite(SENSOR_POWER_PIN, LOW);
  digitalWrite(PUMP_PIN, LOW);
  
  // Initialize DHT
  dht.begin();
  
  delay(1000);
  Serial.println("Soil Moisture & DHT Sensor with Firebase");
  
  // Connect to WiFi
  connectWiFi();
  
  // Initialize time
  configTime(gmtOffset_sec, daylightOffset_sec, "pool.ntp.org", "time.nist.gov");
  Serial.println("Waiting for time sync...");
  delay(2000);
  
  // Configure Firebase
  config.database_url = DATABASE_URL;
  config.signer.tokens.legacy_token = DATABASE_SECRET;
  
  Firebase.begin(&config, &auth);
  Firebase.reconnectWiFi(true);
  
  Serial.println("Firebase initialized!");
}

void loop() {
  // Check WiFi connection
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }
  
  // Power on sensor
  digitalWrite(SENSOR_POWER_PIN, HIGH);
  delay(100);
  
  // Read sensor
  int sensorValue = analogRead(SENSOR_READ_PIN);
  
  // Power off sensor
  digitalWrite(SENSOR_POWER_PIN, LOW);
  
  // Read DHT Sensor
  float humidity = dht.readHumidity();
  float temperature = dht.readTemperature();

  // Check if any reads failed and exit early (to try again).
  if (isnan(humidity) || isnan(temperature)) {
    Serial.println(F("Failed to read from DHT sensor!"));
    return;
  }
  
  // Calculate moisture and status
  int moisturePercent;
  String soilStatus;
  String pumpStatus;
  bool pumpState;

  // First calculate the moisture percentage
  if (sensorValue <= SOIL_WET) {
    moisturePercent = 100;
  } else if (sensorValue < SEMI_WET) {
    moisturePercent = map(sensorValue, SOIL_WET, SEMI_WET, 100, 60);
  } else if (sensorValue < SOIL_DRY) {
    moisturePercent = map(sensorValue, SEMI_WET, SOIL_DRY, 60, 25);
  } else {
    moisturePercent = map(sensorValue, SOIL_DRY, AIR_DRY, 25, 0);
  }
  moisturePercent = constrain(moisturePercent, 0, 100);

  // Then determine status based on moisture percentage
  if (moisturePercent >= 85) {
    soilStatus = "Too Wet";
    digitalWrite(PUMP_PIN, LOW);
    pumpStatus = "OFF";
    pumpState = false;
  } else if (moisturePercent >= 50) {
    soilStatus = "Ideal";
    digitalWrite(PUMP_PIN, LOW);
    pumpStatus = "OFF";
    pumpState = false;
  } else if (moisturePercent >= 25) {
    soilStatus = "Getting Dry";
    digitalWrite(PUMP_PIN, HIGH);
    pumpStatus = "ON";
    pumpState = true;
  } else {
    soilStatus = "Very Dry";
    digitalWrite(PUMP_PIN, HIGH);
    pumpStatus = "ON";
    pumpState = true;
  }

  // Get timestamp
  String timestamp = getTimestamp();

  // Display on Serial
  Serial.print("Moisture: ");
  Serial.print(moisturePercent);
  Serial.print("% | Temp: ");
  Serial.print(temperature);
  Serial.print("°C | Hum: ");
  Serial.print(humidity);
  Serial.print("% | Status: ");
  Serial.print(soilStatus);
  Serial.print(" | Pump: ");
  Serial.println(pumpStatus);
  Serial.print("Timestamp: ");
  Serial.println(timestamp);

  // Send to Firebase
  sendToFirebase(soilStatus, pumpState, moisturePercent, temperature, humidity, timestamp);

  Serial.println("--------------------");
  delay(5000); // Increased delay slightly
}

void connectWiFi() {
  Serial.print("Connecting to WiFi");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("\nWiFi connected!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
}

String getTimestamp() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) {
    return "Time not set";
  }
  
  char buffer[30];
  strftime(buffer, sizeof(buffer), "%Y-%m-%d %H:%M:%S", &timeinfo);
  return String(buffer);
}

void sendToFirebase(String status, bool pumpState, int moisture, float temp, float hum, String timestamp) {
  // Create JSON object with all data
  FirebaseJson json;
  json.set("status", status);
  json.set("pump", pumpState);
  json.set("moisturePercent", moisture);
  json.set("temperature", temp);
  json.set("humidity", hum);
  json.set("timestamp", timestamp);
  
  // Upload current reading as single batch
  String path = "/sensorData/current";
  if (Firebase.setJSON(firebaseData, path, json)) {
    Serial.println("✓ Current data uploaded successfully");
  } else {
    Serial.println("✗ Current upload failed: " + firebaseData.errorReason());
  }
  
  // Store historical data using pushJSON (generates unique ID)
  String historyPath = "/sensorData/history";
  if (Firebase.pushJSON(firebaseData, historyPath, json)) {
    Serial.println("✓ History data pushed successfully");
  } else {
    Serial.println("✗ History push failed: " + firebaseData.errorReason());
  }
}
