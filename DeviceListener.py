from socket import *
import json
import time
import threading
import requests
import os

listen_port = 37020   # Port for receiving the broadcast
response_port = 37021 # Port on the sender that is listening for the reply

client_id = "proxy_pc"

last_message_esp32_time = time.time()
last_message_pi_time = time.time()

log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),  "log.txt")
log = open(log_path, "a")

openstatus = None
opened_by_humidity = False

ip_address_map = {}

def listen():
    """Listens for broadcasts, parses JSON."""
    global openstatus
    global opened_by_humidity
    openstatus = get_windows_status(1)
    while True:
        # Start listen for broadcasts
        try:
            listener_sock = socket(AF_INET, SOCK_DGRAM) # UDP Socket
            listener_sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1) # Allow address reuse
            listener_sock.bind(('0.0.0.0', listen_port))
            
            data, addr = listener_sock.recvfrom(1024)
            log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Received data from {addr}, data: {data}\n")
            log.flush()
            
            broadcaster_ip = addr[0]
            
            try:
                JSON_string = data.decode('utf-8') # Decode bytes to string
                received_data = json.loads(JSON_string) # From string to JSON
                ip_address_map[received_data.get('type', 'N/A')] = broadcaster_ip
                # handle data from esp32
                if(received_data.get("type") == "dht11"):
                    sensor_type = received_data.get('type', 'N/A')
                    sensor_id = received_data.get('id', 'N/A')
                    temperature = received_data.get('temperature', 'N/A')
                    humidity = received_data.get('humidity', 'N/A')
                    last_updated = received_data.get('last_updated', 'N/A')
                    
                    if last_updated != 'N/A':
                        last_updated += 946684800  # Adjust from ESP32 epoch to Unix epoch
                        last_message_esp32_time = last_updated
                        last_updated = time.gmtime(last_updated)
                        last_updated_str = time.strftime("%d-%m-%Y %H:%M:%S", last_updated)
                    print(f"[RECEIVED] Sensor type: {sensor_type}, id: {sensor_id} from {broadcaster_ip}")
                    print(f"Temperature: {temperature}C, Humidity: {humidity}%, last update: {last_updated_str}")
                    # update humidity via api
                    update_room_humidity(sensor_id, humidity)
                    
                    # open window if humidity is too high
                    if(humidity >= 60 and opened_by_humidity == False):
                        print("High humidity detected, sending open instruction")
                        send_instruction(True, ip_address_map.get("window_controller"))
                        update_window_status(sensor_id, True)
                        opened_by_humidity = True
                    # close window if humidity is back to normal
                    if(humidity < 50 and opened_by_humidity == True):
                        print("Humidity back to normal, sending close instruction")
                        send_instruction(False, ip_address_map.get("window_controller"))
                        update_window_status(sensor_id, False)
                        opened_by_humidity = False
                # handle messages from raspberry pi
                elif(received_data.get("type") == "window_controller"):
                    message_from_pi = received_data.get('message', 'N/A')
                    last_updated = received_data.get('last_updated', 0)
                    print(f"[RECEIVED] Broadcast message: {message_from_pi} from {broadcaster_ip} with id: {received_data.get('id', 'N/A')}, last_updated: {last_updated}")
                    last_message_pi_time = last_updated
                    window_status = get_windows_status(received_data.get('id', 'N/A'))
                    print(f"Window status for id {received_data.get('id', 'N/A')}: {window_status}")
                    if openstatus != window_status:
                        print("Status changed, sending instruction")
                        send_instruction(window_status, broadcaster_ip)
                        openstatus = window_status
                else: 
                    raise ValueError("Unknown type received")
            except json.JSONDecodeError as e:
                print(f"  [ERROR] Received unreadable data from {broadcaster_ip}. Skipping.")
                log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - JSON DECODE ERROR from {broadcaster_ip}: {e}, raw data: {data}\n")
                log.flush()
            except ValueError as ve:
                print(f"  [ERROR] {ve} from {broadcaster_ip}. Skipping.")
                log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - VALUE ERROR from {broadcaster_ip}: {ve}, raw data: {data}\n")
                log.flush()
        except KeyboardInterrupt:
            print("\n\n Receiver stopped by user (Ctrl+C).")
                

def check_data_timeout():
    """Check every minute if data was recently received."""
    while True:
        time.sleep(60)
        current_time = time.time()
        if current_time - last_message_esp32_time + 946684800 > 60:
            print(f"No data received in the last minute!")
            log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - WARNING: No data received in the last minute!\n")
            log.flush()  # Force write to disk immediately
        if current_time - last_message_pi_time > 60:
            print(f"No data received from Raspberry Pi in the last minute!")
            log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - WARNING: No data received from Raspberry Pi in the last minute!\n")
            log.flush()  # Force write to disk immediately

def get_windows_status(id):
    """Fetches window status from the local API."""
    try:
        response = requests.get(f'https://breeasy.azurewebsites.net/api/windows/status/{id}')
        if response.status_code == 200:
            status_data = response.json()
            return status_data
        else:
            print(f"[API ERROR] Failed to fetch window status. Status code: {response.status_code}")
            return None
    except requests.RequestException as e:
        print(f"[API ERROR] Exception occurred while fetching window status: {e}")
        return None

def update_window_status(id, should_open):
    """Updates the window status via API."""
    try:
        response = requests.get(f'https://breeasy.azurewebsites.net/api/Windows/{id}')
        if response.status_code == 200:
            window_data = response.json()
            window_data['isOpen'] = should_open
            put_response = requests.put(f'https://breeasy.azurewebsites.net/api/Windows/{id}', json=window_data)
        else:
            print(f"[API ERROR] Failed to fetch window data for id {id}. Status code: {response.status_code}")
    except requests.RequestException as e:
        print(f"[API ERROR] Exception occurred while updating window status for id {id}: {e}")

def send_instruction(window_status, broadcaster_ip):
    """Sends instruction to the Raspberry Pi based on window status."""
    try:
        reply_sock = socket(AF_INET, SOCK_DGRAM)
        reply_sock.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
        
        if window_status is None:
            print("[SEND ERROR] Cannot send instruction due to unknown window status.")
            return
        
        instruction_payload = {
            "source": client_id,
            "should_open": window_status,
        }
        
        instruction_json = json.dumps(instruction_payload)
        instruction_encoded = instruction_json.encode('utf-8')
        
        log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Sending instruction to {broadcaster_ip}:{response_port}, data: {instruction_json}\n")
        log.flush()
        
        reply_sock.sendto(instruction_encoded, (broadcaster_ip, response_port))
        
    except Exception as e:
        print(f"[SEND ERROR] Error sending instruction: {e}")
    finally:
        if 'reply_sock' in locals():
            reply_sock.close()

def update_room_humidity(id, humidity):
    """Updates the room humidity via API."""
    try:
        response = requests.put(f'https://breeasy.azurewebsites.net/api/Locations/humidity/{id}?humidity={humidity}')
        if response.status_code == 200:
            print(f"[API] Successfully updated humidity for room {id} to {humidity}%.")
        else:
            print(f"[API ERROR] Failed to update humidity for room {id}. Status code: {response.status_code}")
    except requests.RequestException as e:
        print(f"[API ERROR] Exception occurred while updating humidity for room {id}: {e}")
        
checker_thread = threading.Thread(target=check_data_timeout, daemon=True)
checker_thread.start()
listen()