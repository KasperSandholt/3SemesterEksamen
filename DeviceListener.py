from logging import log
from socket import *
import json
import time
import threading
import requests
import os


# --- CONFIGURATION ---
LISTEN_PORT = 37020          # Port for receiving the broadcast
RESPONSE_PORT = 37021        # Port to send instructions to the Raspberry Pi
CLIENT_ID = "proxy_pc"       # Unique ID for this client
LAST_MESSAGE_ESP32_TIME = 0  # Time of last message from ESP32
LAST_MESSAGE_PI_TIME = 0     # Time of last message from Raspberry Pi

# Set up logging by creating/opening a log file in append mode
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),  "log.txt")
LOG = open(LOG_PATH, "a")

OPEN_STATUS = None           # status if the window is open
OPEN_BY_HUMIDITY = False     # status for if the window is opened by humidity

# map of addresses to be able to send command to right device
IP_ADDRESS_MAP = {}
# --- End Configuration ---


def listen():
    """
    Listens for broadcasts from devices and processes the received data.
    if the type is dht11, it updates the humidity and possibly opens/closes the window.
    else if the type is window controller it checks for status changes and sends instructions accordingly.
    """
    
    # get the global variables
    global OPEN_STATUS
    global OPEN_BY_HUMIDITY
    global LAST_MESSAGE_ESP32_TIME
    global LAST_MESSAGE_PI_TIME
    
    # initial fetch of window status for the window controller with id 1
    OPEN_STATUS = get_windows_status(1)
    while True:
        # Start listen for broadcasts
        try:
            listener_sock = socket(AF_INET, SOCK_DGRAM)             # Initialize UDP socket
            listener_sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)   # Allow address reuse
            listener_sock.bind(('0.0.0.0', LISTEN_PORT))            # Bind to all interfaces on the specified port
            
            # Listen for incoming data
            data, addr = listener_sock.recvfrom(1024)
            
            # Log the received data
            LOG.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Received data from {addr}, data: {data}\n")
            LOG.flush()

            broadcaster_ip = addr[0]                               # Extract broadcaster's IP address
            
            # Parse the received JSON data
            try:
                JSON_string = data.decode('utf-8')                 # Decode bytes to string
                received_data = json.loads(JSON_string)            # From string to JSON
                
                # update ip address map to save the ip address of the device
                IP_ADDRESS_MAP[received_data.get('type', 'N/A')] = broadcaster_ip
                
                # handle data from esp32(sensor dht11)
                if(received_data.get("type") == "dht11"):
                    # get data from the json
                    sensor_type = received_data.get('type', 'N/A')
                    sensor_id = received_data.get('id', 'N/A')
                    temperature = received_data.get('temperature', 'N/A')
                    humidity = received_data.get('humidity', 'N/A')
                    last_updated = received_data.get('last_updated', 'N/A')
                    
                    # convert unix time to readable format
                    if last_updated != 'N/A':
                        last_updated += 946684800                       # Adjust from ESP32 epoch to Unix epoch
                        LAST_MESSAGE_ESP32_TIME = last_updated          # update last message time
                        last_updated = time.gmtime(last_updated)        # convert to struct_time
                        last_updated_str = time.strftime("%d-%m-%Y %H:%M:%S", last_updated) # format to string
                        
                    print(f"[RECEIVED] Sensor type: {sensor_type}, id: {sensor_id} from {broadcaster_ip}")
                    print(f"Temperature: {temperature}C, Humidity: {humidity}%, last update: {last_updated_str}")
                    # update humidity via api
                    update_room_humidity(sensor_id, humidity)
                    update_room_temperature(sensor_id, temperature)
                    
                    # open window if humidity is too high
                    if(humidity >= 60 and OPEN_BY_HUMIDITY == False):
                        print("High humidity detected, sending open instruction")
                        send_instruction(True, IP_ADDRESS_MAP.get("window_controller"))
                        update_window_status(sensor_id, True)
                        OPEN_BY_HUMIDITY = True
                    # close window if humidity is back to normal
                    if(humidity < 50 and OPEN_BY_HUMIDITY == True):
                        print("Humidity back to normal, sending close instruction")
                        send_instruction(False, IP_ADDRESS_MAP.get("window_controller"))
                        update_window_status(sensor_id, False)
                        OPEN_BY_HUMIDITY = False

                # handle messages from raspberry pi
                elif(received_data.get("type") == "window_controller"):
                    
                    # get data from the json
                    message_from_pi = received_data.get('message', 'N/A')
                    last_updated = received_data.get('last_updated', 0)
                    print(f"[RECEIVED] Broadcast message: {message_from_pi} from {broadcaster_ip} with id: {received_data.get('id', 'N/A')}, last_updated: {last_updated}")
                    
                    LAST_MESSAGE_PI_TIME = last_updated # update last message time
                    
                    # fetch current window status from api
                    window_status = get_windows_status(received_data.get('id', 'N/A'))
                    print(f"Window status for id {received_data.get('id', 'N/A')}: {window_status}")
                    
                    # check if status has changed
                    if OPEN_STATUS != window_status:
                        print("Status changed, sending instruction")
                        send_instruction(window_status, broadcaster_ip)
                        OPEN_STATUS = window_status
                else: 
                    # handle unknown type
                    LOG.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - VALUE ERROR from {broadcaster_ip}: Unknown type received, raw data: {data}\n")
                    LOG.flush()
                    raise ValueError("Unknown type received")
                
            except json.JSONDecodeError as e:
                print(f"  [ERROR] Received unreadable data from {broadcaster_ip}. Skipping.")
                LOG.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - JSON DECODE ERROR from {broadcaster_ip}: {e}, raw data: {data}\n")
                LOG.flush()
                
            except ValueError as ve:
                print(f"  [ERROR] {ve} from {broadcaster_ip}. Skipping.")
                LOG.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - VALUE ERROR from {broadcaster_ip}: {ve}, raw data: {data}\n")
                LOG.flush()
                
        except KeyboardInterrupt:
            print("\n\n Receiver stopped by user (Ctrl+C).")

    
def check_data_timeout():
    """
    Check every minute if data was recently received from devices.
    if not, ½ a warning.
    """
    global LAST_MESSAGE_ESP32_TIME
    global LAST_MESSAGE_PI_TIME
    while True:
        time.sleep(60)
        
        current_time = time.time()
        # check if more than a minute has passed since last message from esp32
        if current_time - LAST_MESSAGE_ESP32_TIME > 60:
            print(f"No data received in the last minute!")
            LOG.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - WARNING: No data received in the last minute!\n")
            LOG.flush()
        # check if more than a minute has passed since last message from raspberry pi
        if current_time - LAST_MESSAGE_PI_TIME > 60:
            print(f"No data received from Raspberry Pi in the last minute!")
            LOG.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - WARNING: No data received from Raspberry Pi in the last minute!\n")
            LOG.flush()

def get_windows_status(id):
    """
    Fetches window status from the local API.
    
    returns: True if window is open, False if closed, None if error.
    """
    try:
        # Make GET request to fetch window status
        response = requests.get(f'https://breeasy.azurewebsites.net/api/windows/status/{id}')
        # if the request was successful, parse the JSON response
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
    """
    Updates the window status in the database via API.
    
    id: window id
    
    should_open: True if window is open, False if closed
    """
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
    """
    Sends instruction to the Raspberry Pi to either open or close the window.
    
    window_status: True to open, False to close
    
    broadcaster_ip: IP address of the Raspberry Pi
    """
    try:
        # Initialize UDP socket for sending reply
        reply_sock = socket(AF_INET, SOCK_DGRAM)
        reply_sock.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
        
        # Ensure we have a valid window status to send
        if window_status is None:
            print("[SEND ERROR] Cannot send instruction due to unknown window status.")
            return
        
        # Prepare instruction payload
        instruction_payload = {
            "source": CLIENT_ID,
            "should_open": window_status,
        }
        
        # Convert payload to JSON and encode to bytes
        instruction_json = json.dumps(instruction_payload)
        instruction_encoded = instruction_json.encode('utf-8')
        
        # Log the sending action
        LOG.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Sending instruction to {broadcaster_ip}:{RESPONSE_PORT}, data: {instruction_json}\n")
        LOG.flush()
        
        # Send the instruction to the broadcaster's IP and response port
        reply_sock.sendto(instruction_encoded, (broadcaster_ip, RESPONSE_PORT))
        
    except Exception as e:
        print(f"[SEND ERROR] Error sending instruction: {e}")
    finally:
        if 'reply_sock' in locals():
            reply_sock.close()

def update_room_humidity(id, humidity):
    """
    Updates the humidity of a room via API.
    
    id: room id
    
    humidity: new humidity value
    """
    try:
        response = requests.put(f'https://breeasy.azurewebsites.net/api/Locations/humidity/{id}?humidity={humidity}')
        if response.status_code == 200:
            print(f"[API] Successfully updated humidity for room {id} to {humidity}%.")
        else:
            print(f"[API ERROR] Failed to update humidity for room {id}. Status code: {response.status_code}")
    except requests.RequestException as e:
        print(f"[API ERROR] Exception occurred while updating humidity for room {id}: {e}")

def update_room_temperature(id, temperature):
    """Updates the room temperature via API."""
    try:
        response = requests.put(f'https://breeasy.azurewebsites.net/api/Locations/temperature/{id}?temperature={temperature}')
        if response.status_code == 200:
            print(f"[API] Successfully updated temperature for room {id} to {temperature}°C.")
        else:
            print(f"[API ERROR] Failed to update temperature for room {id}. Status code: {response.status_code}")
    except requests.RequestException as e:
        print(f"[API ERROR] Exception occurred while updating temperature for room {id}: {e}")

# start timeout checker thread
checker_thread = threading.Thread(target=check_data_timeout, daemon=True)
checker_thread.start()

# start listening for broadcasts
listen()