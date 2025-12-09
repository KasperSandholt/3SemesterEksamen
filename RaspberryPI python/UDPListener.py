import requests
import socket
import json
import time
import threading
import os

# --- Configuration (Must match sender) ---
LISTEN_PORT = 37020   # Port for receiving the broadcast
RESPONSE_PORT = 37021 # Port on the sender that is listening for the reply
# --- End Configuration ---

# Id of this client that sends the response
CLIENT_ID = "proxy_pc" 
last_message_received_time = time.time()
current_status = None
# Use absolute path for log file
log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "log.txt")
log = open(log_path, "a")

def listen_and_respond():
    """Listens for broadcasts, parses JSON, and sends a directed response."""
    
    # Start listen for broadcasts
    try:
        listener_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP Socket
        listener_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Allow address reuse
        listener_sock.bind(('0.0.0.0', LISTEN_PORT)) # be able to receive broadcasts on all subnets
        
        print(f"Client **{CLIENT_ID}** 📡 Listening for broadcasts on port {LISTEN_PORT}...")
        log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Listener started on port {LISTEN_PORT}\n")
        log.flush()
        while True:
            data, addr = listener_sock.recvfrom(1024) 
            log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Received data from {addr}, data: {data}\n")
            log.flush()  # Force write to disk immediately
            # The IP address of the broadcaster (The Raspberry Pi)
            broadcaster_ip = addr[0]
            
            # Parse the received JSON data
            try:
                json_string = data.decode('utf-8') # Decode bytes to string
                received_data = json.loads(json_string) # From string to JSON
                
                message_from_pi = received_data.get('message', 'N/A')
                last_message_received_time = received_data.get('timestamp', 0)
                print(f"[RECEIVED] Broadcast message: {message_from_pi} from {broadcaster_ip} with id: {received_data.get('id', 'N/A')}, timestamp: {received_data.get('timestamp', 'N/A')}")
                log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Parsed JSON: {received_data}\n")
                log.flush()
                
            except json.JSONDecodeError as e:
                print(f"  [ERROR] Received unreadable data from {broadcaster_ip}. Skipping.")
                log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - JSON DECODE ERROR from {broadcaster_ip}: {e}, raw data: {data}\n")
                log.flush()
                continue
            
            # hent api data
            openstatus = None
            try:
                openstatus = requests.get('http://localhost:5082/api/windows/status/1', timeout=2)
                openstatus = openstatus.json()
                print("API request successful:", openstatus)
                log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - API response: {openstatus}\n")
                log.flush()
            except requests.RequestException as e:
                print("API request failed:", e)
                log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - API REQUEST FAILED: {e}\n")
                log.flush()
            
            if (openstatus == current_status):
                print("Status unchanged, not sending response.")
                log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Status unchanged ({openstatus}), skipping response.\n")
                log.flush()
                continue
            
            response_payload = {
                "source": CLIENT_ID,
                "should_open": openstatus,
            }
            
            response_json = json.dumps(response_payload) # convert to JSON string
            response_encoded = response_json.encode('utf-8') # encode to bytes
            
            # Send the response back to the specific Raspberry Pi IP
            try:
                responder_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # Create UDP Socket
                log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Sending response to {broadcaster_ip}:{RESPONSE_PORT}, data: {response_json}\n")
                log.flush()  # Force write to disk immediately
                # Send the reply to the broadcaster's IP on the RESPONSE_PORT
                responder_sock.sendto(response_encoded, (broadcaster_ip, RESPONSE_PORT))
                
                responder_sock.close() # Close the socket after sending
                
            except Exception as e:
                print(f"  ❌ Error sending response to {broadcaster_ip}: {e}")
                log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - ERROR sending response to {broadcaster_ip}: {e}\n")
                log.flush()
            
    except KeyboardInterrupt:
        print("\n\n🛑 Receiver stopped by user (Ctrl+C).")
        log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Receiver stopped by user (Ctrl+C).\n")
        log.flush()  # Force write to disk immediately
    except Exception as e:
        print(f"\n❌ An unhandled error occurred: {e}")
        log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - An unhandled error occurred: {e}\n")
        log.flush()  # Force write to disk immediately
    finally:
        if 'listener_sock' in locals():
            listener_sock.close()
        print("Listener socket closed. Exiting.")

def check_data_timeout():
    """Check every minute if data was recently received."""
    while True:
        time.sleep(60)
        current_time = time.time()
        if current_time - last_message_received_time > 60:
            print(f"⚠️ No data received in the last minute!")
            log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - WARNING: No data received in the last minute!\n")
            log.flush()  # Force write to disk immediately

log.write("----- New Session at " + time.strftime("%Y-%m-%d %H:%M:%S") + " -----\n")
log.flush()  # Force write to disk immediately

# Start the checker thread
checker_thread = threading.Thread(target=check_data_timeout, daemon=True)
checker_thread.start()

try:
    listen_and_respond()
finally:
    log.close()  # Ensure log file is properly closed