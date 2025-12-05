import socket
import sys
import time
import json
import threading
from gpiozero import Motor

motor = Motor(forward=27, backward=22, enable=17, pwm=True)

# --- Configuration ---
BROADCAST_IP = '255.255.255.255'
PORT = 37020                # Port for sending the broadcast
RESPONSE_PORT = 37021       # Port for receiving the directed reply
SEND_INTERVAL_SECONDS = 5 
MAX_BUFFER_SIZE = 1024

id = 1
# --- End Configuration ---

def receive_replies():
    """Listens for directed replies from all responders."""
    try:
        reply_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        reply_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Bind to the RESPONSE_PORT on all interfaces
        reply_sock.bind(('0.0.0.0', RESPONSE_PORT))
        
        print(f"\n[Reply Listener] Listening for replies on port {RESPONSE_PORT}...")
        
        while True:
            # This thread blocks here until a reply is received
            data, addr = reply_sock.recvfrom(MAX_BUFFER_SIZE)
            sender_ip = addr[0]
            
            try:
                reply_json = data.decode('utf-8')
                reply_data = json.loads(reply_json)
                
                if reply_data.get('should_open', False):
                    print("Motor forward")
                    motor.forward()
                    time.sleep(1.5)
                    motor.stop()
                    
                if reply_data.get('should_open', True):
                    print("Motor backward")
                    motor.backward()
                    time.sleep(1.5)
                    motor.stop()
                    
                # print if the window should open or not
                print(f"[Reply Listener] window should open: {reply_data.get('should_open', False)} from {sender_ip}")
            except json.JSONDecodeError:
                print(f"[Reply Listener] Received invalid JSON from {sender_ip}.")
                
    except Exception as e:
        print(f"[Reply Listener] Listener error: {e}")
    finally:
        if 'reply_sock' in locals():
            reply_sock.close()

def send_continuous_broadcast():
    """Starts the listener and sends continuous JSON broadcasts."""
    
    # 1. Start the reply listener in a separate thread
    listener_thread = threading.Thread(target=receive_replies)
    listener_thread.daemon = True # Allows the main program to exit cleanly
    listener_thread.start()

    # 2. Setup the broadcasting socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    except socket.error as err:
        print(f"Error creating socket: {err}")
        sys.exit(1)

    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    
    print(f" Starting continuous JSON broadcast to {BROADCAST_IP}:{PORT}...")
    
    # 3. Continuous Sending Loop
    try:
        while True:
            payload_data = {
                "id": id,
                "timestamp": time.time(),
                "message": "should i open?",
            }
            
            json_string = json.dumps(payload_data)
            encoded_data = json_string.encode('utf-8')
            
            # Send the data
            sock.sendto(encoded_data, (BROADCAST_IP, PORT))
            
            time.sleep(SEND_INTERVAL_SECONDS)
            
    except KeyboardInterrupt:
        print("\n\n Broadcast stopped by user (Ctrl+C).")
    except Exception as e:
        print(f"\n An error occurred during transmission: {e}")
    finally:
        sock.close()
        print("Sender socket closed. Exiting.")

send_continuous_broadcast()