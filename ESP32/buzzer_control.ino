int buzzer = 13;

void setup() {
  Serial.begin(115200);
  pinMode(buzzer, OUTPUT);
}

void loop() {

  if (Serial.available()) {
    String data = Serial.readStringUntil('\n');

    if (data == "1") {
      digitalWrite(buzzer, HIGH);
    }
    else if (data == "0") {
      digitalWrite(buzzer, LOW);
    }
  }

}