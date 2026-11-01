// Hardware sanity check, separate from the real app. Open the Serial Monitor and send a letter.
// If nothing prints, change IO to Serial (same as the real sketch).
#include <Arduino_RouterBridge.h>
#include <Wire.h>
#include <Stepper.h>

#define IO Monitor
#define PIN_B 3
#define PIN_G 5
#define PIN_R 6
#define POT_PWR 9
#define EYE 10
#define BTN 12
#define POT A2
Stepper pan(2048, 2, 7, 4, 8);

void menu() {
  IO.println("h menu | r/g/b/w colors | f random flash | e eye on, E eye off, F eye fade");
  IO.println("o OLED test | i I2C scan | p pot readings | t button | 0 pan 0 | 9 pan 90");
  IO.println("a anger sequence | x reset");
}

void color(int r, int g, int b) { analogWrite(PIN_R, r); analogWrite(PIN_G, g); analogWrite(PIN_B, b); }

void setup() {
  IO.begin(115200);
  pinMode(PIN_R, OUTPUT); pinMode(PIN_G, OUTPUT); pinMode(PIN_B, OUTPUT);
  pinMode(POT_PWR, OUTPUT); digitalWrite(POT_PWR, HIGH);
  pinMode(EYE, OUTPUT); pinMode(BTN, INPUT_PULLUP);
  Wire.begin();
  pan.setSpeed(12);
  menu();
}

void loop() {
  if (!IO.available()) return;
  char c = IO.read();
  switch (c) {
    case 'h': menu(); break;
    case 'r': color(255, 0, 0); IO.println("red"); break;
    case 'g': color(0, 255, 0); IO.println("green"); break;
    case 'b': color(0, 0, 255); IO.println("blue"); break;
    case 'w': color(255, 255, 255); IO.println("white"); break;
    case 'f': for (int i = 0; i < 10; i++) { color(random(256), random(256), random(256)); delay(random(40, 90)); } color(0, 0, 0); break;
    case 'e': analogWrite(EYE, 255); IO.println("eye on"); break;
    case 'E': analogWrite(EYE, 0); IO.println("eye off"); break;
    case 'F': for (int i = 0; i <= 255; i++) { analogWrite(EYE, i); delay(4); } for (int i = 255; i >= 0; i--) { analogWrite(EYE, i); delay(4); } break;
    case 'i': for (byte a = 1; a < 127; a++) { Wire.beginTransmission(a); if (Wire.endTransmission() == 0) { IO.print("I2C 0x"); IO.println(a, HEX); } } IO.println("scan done"); break;
    case 'p': for (int i = 0; i < 100; i++) { IO.print("pot "); IO.println(analogRead(POT)); delay(50); } break;
    case 't': for (int i = 0; i < 100; i++) { IO.println(digitalRead(BTN) == LOW ? "pressed" : "released"); delay(100); } break;
    case '0': pan.step(-(long)2048 * 90 / 360); digitalWrite(2, LOW); digitalWrite(4, LOW); digitalWrite(7, LOW); digitalWrite(8, LOW); IO.println("pan 0 (approx)"); break;
    case '9': pan.step((long)2048 * 90 / 360); digitalWrite(2, LOW); digitalWrite(4, LOW); digitalWrite(7, LOW); digitalWrite(8, LOW); IO.println("pan 90 (approx)"); break;
    case 'a':
      color(255, 0, 0);
      for (int i = 0; i < 5; i++) { pan.step(2048 * 20 / 360); pan.step(-2048 * 40 / 360); pan.step(2048 * 20 / 360); }
      for (int i = 0; i <= 255; i += 5) { analogWrite(EYE, i); delay(10); }
      IO.println("anger done");
      break;
    case 'x': analogWrite(EYE, 0); color(40, 40, 40); IO.println("reset"); break;
  }
}
