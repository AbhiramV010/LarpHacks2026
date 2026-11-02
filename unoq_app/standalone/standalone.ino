// Standalone duck: runs only on the STM32, no Linux app needed.
// USB serial: 'a' = anger sequence, 'r' = reset, 'h' = help.
#include <Wire.h>
#include <Stepper.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Fonts/FreeSansBold12pt7b.h>

#define PIN_B 3
#define PIN_G 5
#define PIN_R 6
#define POT_PWR 9
#define EYE 10
#define STEPS_PER_REV 2048

Adafruit_SSD1306 oled(128, 64, &Wire, -1);
Stepper pan(STEPS_PER_REV, 2, 7, 4, 8);  // IN1, IN3, IN2, IN4

bool angry = false;
int angle = 0;  // 0 faces the laptop, 90 faces the user

void rgb(int R, int G, int B) { analogWrite(PIN_R, R); analogWrite(PIN_G, G); analogWrite(PIN_B, B); }
void setEyes(int v) { analogWrite(EYE, constrain(v, 0, 255)); }
void releaseCoils() { digitalWrite(2, LOW); digitalWrite(4, LOW); digitalWrite(7, LOW); digitalWrite(8, LOW); }

void moveTo(int deg, int rpm) {
  deg = constrain(deg, 0, 120);
  pan.setSpeed(min(rpm, 15));  // >15 RPM skips steps on a 28BYJ-48
  long steps = (long)(deg - angle) * STEPS_PER_REV / 360;
  if (steps != 0) pan.step(steps);
  angle = deg;
  releaseCoils();
}

// ---- one-line OLED: one word at a time, cycling ----
const int MAX_WORDS = 8;
const unsigned long WORD_MS = 1000;
String words[MAX_WORDS];
int wordCount = 0, wordIdx = 0;
unsigned long lastWord = 0;

void drawWord() {
  oled.clearDisplay();
  oled.setFont(&FreeSansBold12pt7b);
  oled.setTextColor(SSD1306_WHITE);
  int16_t x1, y1; uint16_t w, h;
  oled.getTextBounds(words[wordIdx].c_str(), 0, 0, &x1, &y1, &w, &h);
  oled.setCursor((128 - (int)w) / 2, 42);
  oled.print(words[wordIdx]);
  oled.setFont();
  oled.display();
}

void showText(String t) {
  wordCount = 0;
  t.trim();
  int start = 0;
  while (start < (int)t.length() && wordCount < MAX_WORDS) {
    int sp = t.indexOf(' ', start);
    if (sp < 0) sp = t.length();
    if (sp > start) words[wordCount++] = t.substring(start, sp);
    start = sp + 1;
  }
  if (wordCount == 0) { words[0] = "READY"; wordCount = 1; }
  wordIdx = 0;
  lastWord = millis();
  drawWord();
}

void cycleWords() {
  if (wordCount <= 1 || millis() - lastWord < WORD_MS) return;
  lastWord = millis();
  wordIdx = (wordIdx + 1) % wordCount;
  drawWord();
}

void anger() {
  angry = true;
  showText("SUPPORT REVOKED");
  moveTo(90, 12);
  for (int v = 0; v <= 255; v += 5) { setEyes(v); delay(10); }  // ~500 ms ramp
  for (int i = 0; i < 5; i++) {  // sword shake, LED flips off/red on each swing
    moveTo(70, 15); rgb(0, 0, 0);
    moveTo(110, 15); rgb(255, 0, 0);
  }
  moveTo(90, 15);
  setEyes(255);
}

void reset() {
  angry = false;
  setEyes(0);
  moveTo(0, 12);
  showText("READY");
}

void setup() {
  pinMode(PIN_R, OUTPUT); pinMode(PIN_G, OUTPUT); pinMode(PIN_B, OUTPUT);
  pinMode(EYE, OUTPUT);
  pinMode(POT_PWR, OUTPUT); digitalWrite(POT_PWR, HIGH);
  Serial.begin(115200);
  Wire.begin();
  oled.begin(SSD1306_SWITCHCAPVCC, 0x3C) || oled.begin(SSD1306_SWITCHCAPVCC, 0x3D);
  showText("READY");
  rgb(40, 40, 40);
  releaseCoils();
  Serial.println("duck standalone ready: a = anger, r = reset");
}

void loop() {
  if (Serial.available()) {
    char c = Serial.read();
    if (c == 'a') { Serial.println("ANGER"); anger(); }
    else if (c == 'r') { Serial.println("reset"); reset(); }
    else if (c == 'h') Serial.println("a = anger, r = reset");
  }
  if (angry) { bool on = (millis() / 50) % 2; rgb(on ? 255 : 0, 0, 0); }  // fast red flash until reset
  else rgb(40, 40, 40);
  cycleWords();
}
