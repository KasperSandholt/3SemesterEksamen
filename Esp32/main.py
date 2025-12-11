import network
import socket
import machine
import dht
import time
import ujson

# --- CONFIGURATION ---
SSID = 'MGV2-DMU1'
PASSWORD = 'lanmagle'
BROADCAST_IP = '255.255.255.255'  # This sends to everyone on the network
PORT = 37020                      # Broadcast port
PIN_NUM = 4                       # Pin where the DHT11 is connected
ID = 1                            # Unique ID for this sensor        

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
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

# Broadcast data every 5 seconds
try:
    while True:
        # Read data from DHT11 sensor
        sensor = dht.DHT11(machine.Pin(PIN_NUM))
        sensor.measure()
        temp = sensor.temperature()
        hum = sensor.humidity()
        
        # Prepare payload
        payload_data = {
            "type": "dht11",
            "id": ID,
            "temperature": temp,
            "humidity": hum,
            "last_updated": time.time()
        }
        
        # Serialize to JSON and encode to bytes
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