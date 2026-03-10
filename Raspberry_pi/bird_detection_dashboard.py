import cv2
import time
from datetime import datetime, timedelta
import serial
from flask import Flask, render_template_string, Response
import csv
import threading

# ===== ESP32 setup =====
try:
    ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=1)
    time.sleep(2)
    esp32_connected = True
except:
    print("ESP32 not connected. Running camera-only mode.")
    esp32_connected = False

# ===== Video / Webcam =====
cap = cv2.VideoCapture(0)
fgbg = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=50, detectShadows=True)

MIN_AREA = 150
MAX_AREA = 3000

# ===== Dashboard setup =====
app = Flask(__name__)
bird_count_global = 0
buzzer_status = "OFF"
last_buzz_time = "Never"
LOG_FILE = "bird_log.csv"

# ===== Logging functions =====
def save_record(timestamp, bird_count, buzzer_status):
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, bird_count, buzzer_status])

def get_last_week_records():
    records = []
    try:
        with open(LOG_FILE, "r") as f:
            reader = csv.reader(f)
            for row in reader:
                record_time = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
                if record_time >= datetime.now() - timedelta(days=7):
                    records.append(row)
    except FileNotFoundError:
        pass
    return records

# ===== Frame generator for live video =====
def generate_frames():
    global bird_count_global, buzzer_status, last_buzz_time
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        bird_count = 0
        fgmask = fgbg.apply(frame)
        fgmask = cv2.medianBlur(fgmask, 5)
        contours, _ = cv2.findContours(fgmask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if MIN_AREA < area < MAX_AREA:
                x, y, w, h = cv2.boundingRect(cnt)
                aspect_ratio = w / h
                if 0.5 < aspect_ratio < 2.0:
                    bird_count += 1
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        bird_count_global = bird_count

        # ===== Send signal to ESP32 =====
        if esp32_connected:
            try:
                signal = '1' if bird_count > 0 else '0'
                ser.write(f"{signal}\n".encode())
                if signal == '1':
                    buzzer_status = "ON"
                    last_buzz_time = current_time
                else:
                    buzzer_status = "OFF"
            except:
                pass

        # ===== Save record =====
        save_record(current_time, bird_count, buzzer_status)

        # Encode frame for live streaming
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

# ===== Flask routes =====
template_html = '''
<html>
<head>
<title>Bird Detection Dashboard</title>
<meta http-equiv="refresh" content="5">
<style>
body { font-family: Arial; }
h1 { color: #2E8B57; }
table, th, td { border: 1px solid black; border-collapse: collapse; padding:5px;}
th { background-color: #f2f2f2;}
</style>
</head>
<body>
<h1>Bird Detection Dashboard</h1>
<p><b>Birds Detected:</b> {{ bird_count }}</p>
<p><b>Buzzer Status:</b> {{ buzzer_status }}</p>
<p><b>Last Buzzed At:</b> {{ last_buzz_time }}</p>
<img src="{{ url_for('video_feed') }}" width="640" height="480">

<h2>Past Week Records</h2>
<table>
<tr><th>Sr. No.</th><th>Time</th><th>Bird Count</th><th>Buzzer Status</th></tr>
{% for i, row in enumerate(records, start=1) %}
<tr>
<td>{{ i }}</td>
<td>{{ row[0] }}</td>
<td>{{ row[1] }}</td>
<td>{{ row[2] }}</td>
</tr>
{% endfor %}
</table>
</body>
</html>
'''

@app.route('/')
def dashboard():
    records = get_last_week_records()
    return render_template_string(template_html,
                                  bird_count=bird_count_global,
                                  buzzer_status=buzzer_status,
                                  last_buzz_time=last_buzz_time,
                                  records=records,
                                  enumerate=enumerate)  # Fix enumerate error

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# ===== Run Flask in separate thread =====
def start_flask():
    app.run(host='0.0.0.0', port=5000)

flask_thread = threading.Thread(target=start_flask)
flask_thread.daemon = True
flask_thread.start()

# ===== Keep main thread alive =====
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    cap.release()
    if esp32_connected:
        ser.close()
    print("Program terminated")