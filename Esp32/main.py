import network
import socket
import machine
import dht
import time
import ujson  # We use JSON so the data is easy to read later

# --- CONFIGURATION ---
SSID = 'MGV2-DMU1'
PASSWORD = 'lanmagle'
BROADCAST_IP = '255.255.255.255' # This sends to everyone on the network
PORT = 37022                      # The "channel" we are shouting on
PIN_NUM = 4                     # Change this if not using Pin 4
ID = 1

# --- SETUP WIFI ---
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(SSID, PASSWORD)

print("Connecting to WiFi...", end="")
while not wlan.isconnected():
    time.sleep(1)
    print(".", end="")
print("\nConnected! IP:", wlan.ifconfig()[0])

# --- SETUP UDP SOCKET ---
# SOCK_DGRAM means UDP
# SO_BROADCAST allows us to send to 255.255.255.255
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

try:
    while True:
        sensor = dht.DHT11(machine.Pin(PIN_NUM))
        sensor.measure()
        temp = sensor.temperature()
        hum = sensor.humidity()
        
        payload_data = {
            "type": "dht11",
            "temperature": temp,
            "humidity": hum,
        }
        
        json_string = ujson.dumps(payload_data)
        encoded_data = json_string.encode('utf-8')
        
        # Send the data
        sock.sendto(encoded_data, (BROADCAST_IP, PORT))
        
        time.sleep(5)
        
except KeyboardInterrupt:
    print("\n\n Broadcast stopped by user (Ctrl+C).")
except Exception as e:
    print(f"\n An error occurred during transmission: {e}")
finally:
    sock.close()
    print("Sender socket closed. Exiting.")