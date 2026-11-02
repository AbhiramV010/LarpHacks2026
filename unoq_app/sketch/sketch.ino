// Duck MCU sketch: RGB state LED, laser eyes, OLED, pan stepper (sword), button, pot.
// Commands arrive from Linux via Bridge.provide("cmd"); events go back via Bridge.call("event").
#include <Arduino_RouterBridge.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Fonts/FreeSansBold12pt7b.h>
#include <Stepper.h>

#define PIN_B 3
#define PIN_G 5
#define PIN_R 6
#define POT_PWR 9   // pot + leg; OUTPUT HIGH
#define EYE 10      // single laser eye
#define BTN 12      // optional, INPUT_PULLUP
#define POT A2
#define STEPS_PER_REV 2048

Adafruit_SSD1306 oled(128, 64, &Wire, -1);
Stepper pan(STEPS_PER_REV, 2, 7, 4, 8);  // IN1, IN3, IN2, IN4 order for 28BYJ-48

// ---- command queue (filled in callback, drained in loop) ----
const int QN = 8;
String q[QN];
volatile int qHead = 0, qTail = 0;

void onCmd(String cmd) {
  int next = (qTail + 1) % QN;
  if (next == qHead) return;  // full: drop
  q[qTail] = cmd;
  qTail = next;
}

// ---- one-line OLED: one word at a time, cycling through the words ----
const int MAX_WORDS = 8;
const unsigned long WORD_MS = 1000;
String words[MAX_WORDS];
int wordCount = 0;
int wordIdx = 0;
unsigned long lastWordChange = 0;

void drawWord() {
  oled.clearDisplay();
  oled.setFont(&FreeSansBold12pt7b);
  oled.setTextColor(SSD1306_WHITE);
  int16_t x1, y1;
  uint16_t w, h;
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
  lastWordChange = millis();
  drawWord();
}

void cycleWords() {
  if (wordCount <= 1 || millis() - lastWordChange < WORD_MS) return;
  lastWordChange = millis();
  wordIdx = (wordIdx + 1) % wordCount;
  drawWord();
}

// ---- state ----
String state = "idle";
int r = 40, g = 40, b = 40;
bool typing = false;
int eyes = 0;
int angle = 0;          // 0 faces the laptop, 90 faces the user
int potMax = 0;
int lastPot = -1;
unsigned long lastPotSend = 0, lastPotRead = 0, lastBtnChange = 0, lastFlicker = 0;
int btnStable = HIGH, btnRaw = HIGH;

void rgb(int R, int G, int B) { analogWrite(PIN_R, R); analogWrite(PIN_G, G); analogWrite(PIN_B, B); }
void setEyes(int v) { eyes = constrain(v, 0, 255); analogWrite(EYE, eyes); }
void releaseCoils() { digitalWrite(2, LOW); digitalWrite(4, LOW); digitalWrite(7, LOW); digitalWrite(8, LOW); }

void moveTo(int deg, int rpm) {
  deg = constrain(deg, 0, 120);
  pan.setSpeed(min(rpm, 15));  // >15 RPM skips steps on a 28BYJ-48
  long steps = (long)(deg - angle) * STEPS_PER_REV / 360;
  if (steps != 0) pan.step(steps);
  angle = deg;
  releaseCoils();
}

void setState(String s) {
  state = s;
  typing = false;
  if (s == "idle")        { r = 40;  g = 40;  b = 40; }
  else if (s == "listening")   { r = 0;   g = 0;   b = 255; }
  else if (s == "translating") { r = 160; g = 0;   b = 255; }
  else if (s == "typing")      { r = 0;   g = 255; b = 0; }
  else if (s == "waiting")     { r = 255; g = 180; b = 0; }
  else if (s == "talking")     { r = 0;   g = 255; b = 255; }
  else if (s == "angry")       { r = 255; g = 0;   b = 0; }
  String cap = s; cap.toUpperCase();
  if (s == "typing") cap += "...";
  if (s == "idle") cap = "READY";
  showText(cap);
}

void anger() {
  setState("angry");
  showText("SUPPORT REVOKED");
  moveTo(90, 12);
  for (int i = 0; i <= 255; i += 5) { setEyes(i); delay(10); }  // ~500 ms ramp
  for (int i = 0; i < 5; i++) {  // sword shake, LED flips off/red on each swing
    moveTo(70, 15); rgb(0, 0, 0);
    moveTo(110, 15); rgb(255, 0, 0);
  }
  moveTo(90, 15);
  setEyes(255);
}

void handle(String cmd) {
  cmd.trim();
  int sp = cmd.indexOf(' ');
  String op = sp < 0 ? cmd : cmd.substring(0, sp);
  String arg = sp < 0 ? "" : cmd.substring(sp + 1);
  if (op == "STATE") setState(arg);
  else if (op == "OLED") showText(arg);
  else if (op == "PAN") moveTo(arg.toInt(), 12);
  else if (op == "EYES") setEyes(arg.toInt());
  else if (op == "TYPING") typing = arg.toInt() == 1;
  else if (op == "ANGER") anger();
  else if (op == "RESET") { setEyes(0); moveTo(0, 12); setState("idle"); }
}

void updateLed() {
  unsigned long t = millis();
  if (state == "angry") { bool on = (t / 50) % 2; rgb(on ? 255 : 0, 0, 0); }          // fast red flash
  else if (state == "translating" || state == "typing") {                              // green blink while working
    bool on = (t / 200) % 2; rgb(0, on ? 255 : 0, 0);
  }
  else rgb(r, g, b);
}

void pollInputs() {
  unsigned long t = millis();
  int raw = digitalRead(BTN);
  if (raw != btnRaw) { btnRaw = raw; lastBtnChange = t; }
  if (t - lastBtnChange > 30 && btnRaw != btnStable) {
    btnStable = btnRaw;
    Bridge.call("event", String(btnStable == LOW ? "BTN DOWN" : "BTN UP"));
  }
  if (t - lastPotRead >= 50) {
    lastPotRead = t;
    int v = analogRead(POT);
    if (v > potMax) potMax = v;
    if (potMax > 1023) v = (long)v * 1023 / 4095;  // 12-bit ADC (confirm with test_sketch "p")
    if (abs(v - lastPot) > 20 && t - lastPotSend >= 100) {
      lastPot = v; lastPotSend = t;
      Bridge.call("event", "POT " + String(v));
    }
  }
}

void setup() {
  pinMode(PIN_R, OUTPUT); pinMode(PIN_G, OUTPUT); pinMode(PIN_B, OUTPUT);
  pinMode(EYE, OUTPUT);
  pinMode(POT_PWR, OUTPUT); digitalWrite(POT_PWR, HIGH);
  pinMode(BTN, INPUT_PULLUP);
  pinMode(LED_BUILTIN, OUTPUT); digitalWrite(LED_BUILTIN, HIGH);  // LED3 active LOW: off
  Wire.begin();
  if (!oled.begin(SSD1306_SWITCHCAPVCC, 0x3C)) oled.begin(SSD1306_SWITCHCAPVCC, 0x3D);
  oled.setTextColor(SSD1306_WHITE);
  showText("READY");
  rgb(r, g, b);
  releaseCoils();
  Bridge.begin();
  Bridge.provide("cmd", onCmd);
}

void loop() {
  Bridge.update();
  if (qHead != qTail) {  // one command per pass keeps the loop responsive
    String c = q[qHead];
    qHead = (qHead + 1) % QN;
    handle(c);
  }
  updateLed();
  pollInputs();
  cycleWords();
}
