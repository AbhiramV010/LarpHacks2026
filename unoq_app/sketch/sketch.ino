// Duck MCU sketch: RGB state LED, laser eyes, OLED, pan stepper (sword), button, pot.
// Commands arrive from Linux via Bridge.provide("cmd"); events go back via Bridge.call("event").
#include <Arduino_RouterBridge.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Fonts/FreeSansBold9pt7b.h>
#include <Fonts/FreeSans9pt7b.h>
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

// ---- state ----
String state = "idle";
String line1 = "DUCK", line2 = "booting";
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

void drawOled() {
  oled.clearDisplay();
  oled.setFont(&FreeSansBold9pt7b);
  oled.setCursor(0, 22);           // font cursor is the baseline
  oled.print(line1.substring(0, 14));
  oled.setFont(&FreeSans9pt7b);
  oled.setCursor(0, 56);
  oled.print(line2.substring(0, 18));
  oled.setFont();                  // back to the built-in font
  oled.display();
}

void setOled(String a, String c) { line1 = a; line2 = c; drawOled(); }

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
  line1 = cap;
  drawOled();
}

void anger() {
  setState("angry");
  setOled("SUPPORT", "REVOKED");
  moveTo(90, 12);
  for (int i = 0; i <= 255; i += 5) { setEyes(i); delay(10); }  // ~500 ms ramp
  for (int i = 0; i < 5; i++) { moveTo(70, 15); moveTo(110, 15); }
  moveTo(90, 15);
  setEyes(255);
}

void handle(String cmd) {
  cmd.trim();
  int sp = cmd.indexOf(' ');
  String op = sp < 0 ? cmd : cmd.substring(0, sp);
  String arg = sp < 0 ? "" : cmd.substring(sp + 1);
  if (op == "STATE") setState(arg);
  else if (op == "OLED") {
    int bar = arg.indexOf('|');
    setOled(bar < 0 ? arg : arg.substring(0, bar), bar < 0 ? "" : arg.substring(bar + 1));
  }
  else if (op == "LINE2") { line2 = arg; drawOled(); }
  else if (op == "PAN") moveTo(arg.toInt(), 12);
  else if (op == "EYES") setEyes(arg.toInt());
  else if (op == "TYPING") typing = arg.toInt() == 1;
  else if (op == "ANGER") anger();
  else if (op == "RESET") { setEyes(0); moveTo(0, 12); setState("idle"); line2 = ""; drawOled(); }
}

void updateLed() {
  unsigned long t = millis();
  if (state == "angry") { bool on = (t / 150) % 2; rgb(on ? 255 : 0, 0, 0); }
  else if (state == "translating") { float k = 0.3 + 0.7 * (0.5 + 0.5 * sin(t / 400.0)); rgb(r * k, g * k, b * k); }
  else if (state == "typing" && typing) {
    if (t - lastFlicker > (unsigned long)random(40, 90)) { lastFlicker = t; rgb(0, random(2) ? 255 : 30, 0); }
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
  drawOled();
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
}
