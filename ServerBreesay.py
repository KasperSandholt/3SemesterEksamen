import socket
import time
import Adafruit_DHT

# DHT Sensor setup
DHT_SENSOR = Adafruit_DHT.DHT22  # brug DHT11 hvis relevant
DHT_PIN = 4  # GPIO pin

HOST = "0.0.0.0"
PORT = 5000

MIN_CM = 0.5
MAX_CM = 15
HUMIDITY_LIMIT = 60  # %

window_position = 0  # gemmer aktuel position


def set_window(cm):
    global window_position
    if cm < MIN_CM:
        cm = MIN_CM
    elif cm > MAX_CM:
        cm = MAX_CM
    window_position = cm
    print(f"[WINDOW] Sat til {cm} cm")
    return f"WINDOW SET TO {cm} cm"


def get_humidity():
    humidity, temp = Adafruit_DHT.read_retry(DHT_SENSOR, DHT_PIN)
    return humidity


def handle_command(cmd):
    cmd = cmd.strip()

    if cmd.startswith("POSITION:"):
        try:
            pos = float(cmd.split(":")[1])
            return set_window(pos)
        except:
            return "ERROR: INVALID POSITION"

    elif cmd == "HUMIDITY":
        humidity = get_humidity()
        if humidity is not None:
            return f"HUMIDITY:{humidity:.1f}%"
        return "ERROR: HUMIDITY READ FAIL"

    elif cmd == "STATUS":
        return f"POSITION:{window_position}cm"

    elif cmd == "QUIT":
        return "CLOSING CONNECTION"

    return "UNKNOWN COMMAND"


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
    server.bind((HOST, PORT))
    server.listen(1)
    print(f"[SERVER] Lytter på {HOST}:{PORT}")

    conn, addr = server.accept()
    print(f"[SERVER] Forbundet til {addr}")

    with conn:
        while True:
            # Automatisk fugt-check hvert loop
            humidity = get_humidity()
            if humidity and humidity > HUMIDITY_LIMIT:
                set_window(MAX_CM)

            data = conn.recv(1024).decode()
            if not data:
                break

            print("[CMD]", data)
            response = handle_command(data)
            conn.sendall(response.encode())

            if data.strip() == "QUIT":
                break

print("[SERVER] Shutdown")
