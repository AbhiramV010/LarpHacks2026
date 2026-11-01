// Hardware sanity check, separate from the real app. Open the Serial Monitor and send a letter.
// If nothing prints, change IO to Serial (same as the real sketch).
#include <Wire.h>
#include <Stepper.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Fonts/FreeSansBold12pt7b.h>
#include "Arduino_RouterBridge.h"

#define IO Monitor  // if the Serial Monitor shows nothing, change to Serial

const int R = 6, G = 5, B = 3;
const int EYE_L = 10, EYE_R = 11;
const int BTN = 12, POT = A2, POT_PWR = 9;
const int COILS[] = {2, 4, 7, 8};

Stepper pan(2048, 2, 7, 4, 8);
Adafruit_SSD1306 oled(128, 64, &Wire, -1);
bool oledOk = false;
int pos = 0;  // duck must face the laptop at power-on

void rgb(int r, int g, int b) { analogWrite(R, r); analogWrite(G, g); analogWrite(B, b); }
void eyes(int v) { analogWrite(EYE_L, v); analogWrite(EYE_R, v); }
void releaseCoils() { for (int p : COILS) digitalWrite(p, LOW); }

void turnTo(int a, int rpm = 12) {
  a = constrain(a, 0, 120);
  pan.setSpeed(rpm);
  pan.step((int)((long)(a - pos) * 2048 / 360));
  pos = a;
  releaseCoils();
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

void show(String t) {
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
  if (oledOk) drawWord();
}

void cycleWords() {
  if (!oledOk || wordCount <= 1 || millis() - lastWordChange < WORD_MS) return;
  lastWordChange = millis();
  wordIdx = (wordIdx + 1) % wordCount;
  drawWord();
}

void help() {
  IO.println("r g b w o : RGB red/green/blue/white/off");
  IO.println("x         : RGB random flash 3 s");
  IO.println("e E f     : eyes on / off / fade");
  IO.println("d         : OLED test");
  IO.println("i         : I2C scan");
  IO.println("p         : pot readings 5 s");
  IO.println("k         : button test 10 s");
  IO.println("0 9       : pan to 0 (laptop) / 90 (user)");
  IO.println("a         : anger sequence");
  IO.println("z         : reset (pan 0, all off)");
}

void setup() {
  pinMode(R, OUTPUT); pinMode(G, OUTPUT); pinMode(B, OUTPUT);
  pinMode(EYE_L, OUTPUT); pinMode(EYE_R, OUTPUT);
  pinMode(BTN, INPUT_PULLUP);
  pinMode(POT_PWR, OUTPUT); digitalWrite(POT_PWR, HIGH);
  for (int p : COILS) pinMode(p, OUTPUT);

  Bridge.begin();
  IO.begin();
  Wire.begin();
  oledOk = oled.begin(SSD1306_SWITCHCAPVCC, 0x3C) || oled.begin(SSD1306_SWITCHCAPVCC, 0x3D);
  show("READY");
  IO.println(oledOk ? "OLED ok" : "OLED not found");
  help();
}

void loop() {
  cycleWords();
  if (!IO.available()) return;
  char c = IO.read();
  if (c == '\n' || c == '\r' || c == ' ') return;

  switch (c) {
    case 'r': rgb(255, 0, 0); IO.println("red"); break;
    case 'g': rgb(0, 255, 0); IO.println("green"); break;
    case 'b': rgb(0, 0, 255); IO.println("blue"); break;
    case 'w': rgb(255, 255, 255); IO.println("white"); break;
    case 'o': rgb(0, 0, 0); IO.println("off"); break;

    case 'x':
      IO.println("random flash");
      for (int i = 0; i < 30; i++) { rgb(random(256), random(256), random(256)); delay(100); }
      rgb(0, 0, 0);
      break;

    case 'e': eyes(255); IO.println("eyes on"); break;
    case 'E': eyes(0); IO.println("eyes off"); break;
    case 'f':
      IO.println("eyes fade");
      for (int v = 0; v <= 255; v += 5) { eyes(v); delay(15); }
      for (int v = 255; v >= 0; v -= 5) { eyes(v); delay(15); }
      break;

    case 'd':
      IO.println(oledOk ? "OLED: showing QUACK" : "OLED not found, try i");
      show("hello world, this scrolls");
      break;

    case 'i':
      IO.println("I2C scan:");
      for (uint8_t a = 1; a < 127; a++) {
        Wire.beginTransmission(a);
        if (Wire.endTransmission() == 0) IO.println(String("  found 0x") + String(a, HEX));
      }
      IO.println("scan done");
      break;

    case 'p': {
      IO.println("turn the knob end to end");
      int lo = 99999, hi = 0;
      for (int i = 0; i < 25; i++) {
        int v = analogRead(POT);
        lo = min(lo, v); hi = max(hi, v);
        IO.println(String("pot ") + v);
        delay(200);
      }
      IO.println(String("range seen: ") + lo + " to " + hi);
      break;
    }

    case 'k': {
      IO.println("press the button (10 s)");
      bool last = HIGH;
      unsigned long end = millis() + 10000;
      while (millis() < end) {
        bool now = digitalRead(BTN);
        if (now != last) { delay(30); now = digitalRead(BTN); }
        if (now != last) { IO.println(now == LOW ? "BTN DOWN" : "BTN UP"); last = now; }
      }
      IO.println("button test done");
      break;
    }

    case '0': turnTo(0); IO.println("pan 0"); break;
    case '9': turnTo(90); IO.println("pan 90"); break;

    case 'a':
      IO.println("ANGER");
      rgb(255, 0, 0);
      show("SUPPORT REVOKED");
      turnTo(90);
      for (int v = 0; v <= 255; v += 15) { eyes(v); delay(30); }
      for (int i = 0; i < 5; i++) {
        turnTo(70, 15); rgb(0, 0, 0);
        turnTo(110, 15); rgb(255, 0, 0);
      }
      turnTo(90);
      IO.println("anger done");
      break;

    case 'z':
      turnTo(0); rgb(0, 0, 0); eyes(0); show("READY");
      IO.println("reset");
      break;

    case 'h': help(); break;
    default: IO.println(String("unknown: ") + c);
  }
}
