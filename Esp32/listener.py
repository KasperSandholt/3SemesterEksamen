import socket
import json
import time

# --- Configuration (Must match sender) ---
LISTEN_PORT = 37022   # Port for receiving the broadcast
RESPONSE_PORT = 37021 # Port on the sender that is listening for the reply
# --- End Configuration ---

# Id of this client that sends the response
CLIENT_ID = "proxy_pc" 

def listen_and_respond():
    """Listens for broadcasts, parses JSON, and sends a directed response."""
    
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
                
                message_from_pi = received_data.get('message', 'N/A')
                temperature = received_data.get('temperature', 'N/A')
                humidity = received_data.get('humidity', 'N/A')
                last_update = received_data.get('last_updated', 'N/A')
                print(last_update)
                print(f"Temperature: {temperature}C, Humidity: {humidity}%, last update: {last_update}")
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

listen_and_respond()