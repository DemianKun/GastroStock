#include <WiFi.h>
#include <HTTPClient.h>
#include <HX711.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <ArduinoJson.h>

// --- CONFIGURACIÓN DE RED ---
const char* ssid = "MARQUEZ";
const char* password = "carlosmarquez66";
const char* serverUrl = "http://192.168.1.25:8000/api/sensores";

// --- CONFIGURACIÓN DE TEMPERATURA ---
const int ONE_WIRE_BUS = 15;
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

// --- CONFIGURACIÓN DE 6 BASCULAS ---
HX711 scale1, scale2, scale3, scale4, scale5, scale6;

const int DOUT1 = 23, SCK1 = 22;
const int DOUT2 = 21, SCK2 = 19;
const int DOUT3 = 18, SCK3 = 5;
const int DOUT4 = 17, SCK4 = 16;
const int DOUT5 = 27, SCK5 = 26;
const int DOUT6 = 32, SCK6 = 33;

// --- FACTORES DE CALIBRACIÓN ---
float cal_factors[] = {-1000.0, -10000.0, -10000.0, -10000.0, -10000.0, -10000.0};

unsigned long lastTime = 0;
const unsigned long timerDelay = 30000;