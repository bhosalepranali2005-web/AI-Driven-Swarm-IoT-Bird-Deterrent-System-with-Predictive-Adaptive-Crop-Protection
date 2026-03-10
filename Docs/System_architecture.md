# System Architecture

Webcam → Raspberry Pi → Bird Detection → ESP32 → Buzzer

1. Webcam captures live video
2. Raspberry Pi processes frames using OpenCV
3. Birds are detected using motion detection
4. Signal is sent to ESP32
5. ESP32 activates buzzer deterrent
6. Dashboard shows live data and logs