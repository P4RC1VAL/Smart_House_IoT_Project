
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <ThreeWire.h>
#include <RtcDS1302.h>
#include <Wire.h>
#include <Adafruit_BMP085.h>
#include <MQ135.h>
#include <SPI.h>          // Добавлено для SPI
#include <MFRC522.h>      // Добавлено для RFID

// Настройки сети
#define WIFI_SSID "TP-LINK_05E0"
#define WIFI_PASSWORD "84965641062"
#define FIREBASE_HOST "smarthouse-3760c-default-rtdb.asia-southeast1.firebasedatabase.app"  
#define FIREBASE_SECRET "d8658807c28b752a11383c56a94e570942e3000f"

// Пины для DS1302
#define DS1302_RST  14  // D5 (GPIO14)
#define DS1302_DAT  12  // D6 (GPIO12)
#define DS1302_CLK  13  // D7 (GPIO13)

// Датчики
#define DHTPIN 2         // D1 (GPIO5) - измененный пин для DHT
#define DHTTYPE DHT11
#define BMP_SDA 4        // D2 (GPIO4)
#define BMP_SCL 5        // D3 (GPIO0)
#define MQ135_PIN A0     // Аналоговый пин
#define RZERO 76.63      // Калибровочное значение

//Реле
#define RELAY_PIN 15       // GPIO15 (D8)
#define RFID_SDA  D3      // D3 (GPIO0) 
#define RFID_RST  D0     // D0 (GPIO16)


// Интервалы
#define FAST_INTERVAL 10000    // 10 секунд
#define SLOW_INTERVAL 60000    // 1 минута
#define CONFIG_INTERVAL 30000 // 5 минут

// Объекты
ThreeWire wire(DS1302_DAT, DS1302_CLK, DS1302_RST);
RtcDS1302<ThreeWire> rtc(wire);
DHT dht(DHTPIN, DHT11);
Adafruit_BMP085 bmp;
MQ135 mq135(MQ135_PIN);
MFRC522 mfrc522(RFID_SDA, RFID_RST);
WiFiClientSecure wifiClient;

// Таймеры
unsigned long prevFastSend = 0;
unsigned long prevSlowSend = 0;
unsigned long prevConfigCheck = 0;
bool systemActive = false;  // Флаг активности системы

void setup() {
  Serial.begin(115200);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);

  // Инициализация датчиков
  dht.begin();
  Wire.begin(BMP_SDA, BMP_SCL);
  if (!bmp.begin()) Serial.println("BMP180 error!");
  rtc.Begin();
 // Serial.println("RTC data invalid! Setting time...");
  // Установка времени компиляции
  //RtcDateTime compiled = RtcDateTime(__DATE__, __TIME__);
  //rtc.SetDateTime(compiled);
  
  // Инициализация RFID
  SPI.begin();           // Инициализация SPI
  mfrc522.PCD_Init();    // Инициализация RC522
  delay(4);
  mfrc522.PCD_DumpVersionToSerial();

  // Подключение к WiFi
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED){
    delay(500);
    Serial.print(".");
  } 
  wifiClient.setInsecure();
  Serial.println("\nConnected! IP: " + WiFi.localIP().toString());
}

String getSensorData() {
  RtcDateTime now = rtc.GetDateTime();
  float humidity = dht.readHumidity();
  float temperature = dht.readTemperature();
  float pressure = bmp.readPressure()/100.0;
  float co2 = mq135.getCorrectedPPM(temperature, humidity);

  // Проверка ошибок
  if (isnan(humidity)) humidity = 0;
  if (isnan(temperature)) temperature = 0;
  if (isnan(pressure)) pressure = 0;
  if (isnan(co2)) co2 = 0;

  // Формирование JSON
  String jsonData = "{"
    "\"timestamp\":\"" + formatTimestamp(now) + "\","
    "\"temperature\":" + String(temperature) + ","
    "\"humidity\":" + String(humidity) + ","
    "\"pressure\":" + String(pressure) + ","
    "\"co2\":" + String(co2) + 
  "}";

  return jsonData;
}

void sendData(String path, String data, String customKey) {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  
  // Формируем URL с проверкой слешей
  String url = "https://" + String(FIREBASE_HOST) + path + customKey + ".json?auth=" + String(FIREBASE_SECRET);

  Serial.print("URL: ");
  Serial.println(url); // Для отладки
  
  http.begin(wifiClient, url);
  http.addHeader("Content-Type", "application/json");
  
  int code = http.PUT(data);
  
  if (code == 405) {
    Serial.println("Ошибка: метод POST не разрешен для этого пути");
  }
  
  http.end();
}

void checkRelayConfig() {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  String url = String("https://") + 
               FIREBASE_HOST + 
               String("/sensors/relay.json?auth=") + 
               FIREBASE_SECRET;
  
  http.begin(wifiClient, url);
  int code = http.GET();
  Serial.println("Code: " + String(code));
  
  if (code == 200) {
    String payload = http.getString();
    Serial.println("payload: " + payload);
    StaticJsonDocument<50> doc;
    deserializeJson(doc, payload);
    bool state = doc["State"];
    digitalWrite(RELAY_PIN, state ? HIGH : LOW);
    Serial.println("Relay state: " + String(state));
  }
  
  http.end();
}

String formatTimestamp(const RtcDateTime& dt) {
  char buf[20];
  snprintf(buf, sizeof(buf), "%04d-%02d-%02dT%02d:%02d:%02d",
           dt.Year(), dt.Month(), dt.Day(),
           dt.Hour(), dt.Minute(), dt.Second());
  return String(buf);
}

bool lastCardState = false;
bool currentCardState= false;
int stap = 0;

void loop() {
  unsigned long currentMillis = millis();
  
  // Проверка RFID-карты
  currentCardState = mfrc522.PICC_IsNewCardPresent() && mfrc522.PICC_ReadCardSerial(); //mfrc522.PICC_IsNewCardPresent() mfrc522.PICC_ReadCardSerial()
  //Serial.println("before currentCardState" + String(currentCardState));
  //Serial.println("before lastCardState" + String(lastCardState));

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  // Обновление состояния системы
  if (currentCardState != lastCardState) {
    systemActive = currentCardState;
    lastCardState = currentCardState;
    Serial.println(systemActive ? "Система активирована" : "Система остановлена");
    
    
    // Выключение реле при снятии карты
    if (!systemActive) digitalWrite(RELAY_PIN, LOW);
  }

 // Serial.println("after currentCardState" + String(currentCardState));
 // Serial.println("after lastCardState" + String(lastCardState));

  // Работа системы только с активной картой
  if (systemActive) {
    // Быстрая отправка (10 сек)
    if (currentMillis - prevFastSend >= FAST_INTERVAL) {
      sendData("/sensors/", getSensorData(), "RT");
      prevFastSend = currentMillis;
    }

    // Медленная отправка (1 мин)
    if (currentMillis - prevSlowSend >= SLOW_INTERVAL) {
      sendData("/sensors/HIST/", getSensorData(), String(stap));
      prevSlowSend = currentMillis;
      stap++;
    }

    // Проверка конфигурации (5 мин)
    if (currentMillis - prevConfigCheck >= CONFIG_INTERVAL) {
      checkRelayConfig();
      prevConfigCheck = currentMillis;
    }
  }

  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();
  SPI.end();
  SPI.begin();
  mfrc522.PCD_Init();

  delay(5000);
}
