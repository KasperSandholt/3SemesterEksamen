import socket
import json
import time

# --- Configuration (Must match sender) ---
LISTEN_PORT = 37020   # Port for receiving the broadcast

# --- End Configuration ---

def listen():
    """Listens for broadcasts, parses JSON."""
    
    # Start listen for broadcasts
    try:
        listener_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP Socket
        listener_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Allow address reuse
        listener_sock.bind(('0.0.0.0', LISTEN_PORT)) # be able to receive broadcasts on all subnets
        
        while True:
            data, addr = listener_sock.recvfrom(1024) 
            
            # The IP address of the broadcaster (The Raspberry Pi)
            broadcaster_ip = addr[0]
            
            # Parse the received JSON data
            try:
                json_string = data.decode('utf-8') # Decode bytes to string
                received_data = json.loads(json_string) # From string to JSON
                
                sensor_type = received_data.get('type', 'N/A')
                sensor_id = received_data.get('id', 'N/A')
                temperature = received_data.get('temperature', 'N/A')
                humidity = received_data.get('humidity', 'N/A')
                last_update = received_data.get('last_updated', 'N/A')
                # convert unix time to readable format
                if last_update != 'N/A':
                    last_update += 946684800  # Adjust from ESP32 epoch to Unix epoch
                    last_update = time.gmtime(last_update)
                    last_update_str = time.strftime("%d-%m-%Y %H:%M:%S", last_update)
                print(f"[RECEIVED] Sensor type: {sensor_type}, id: {sensor_id} from {broadcaster_ip}")
                print(f"Temperature: {temperature}C, Humidity: {humidity}%, last update: {last_update_str}")
            except json.JSONDecodeError:
                print(f"  [ERROR] Received unreadable data from {broadcaster_ip}. Skipping.")
                continue
            
    except KeyboardInterrupt:
        print("\n\n Receiver stopped by user (Ctrl+C).")
    except Exception as e:
        print(f"\n An unhandled error occurred: {e}")
    finally:
        if 'listener_sock' in locals():
            listener_sock.close()
        print("Listener socket closed. Exiting.")

listen()