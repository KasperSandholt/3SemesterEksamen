import socket
import sys
import time
import json
import threading
from gpiozero import Motor

# --- Configuration ---
BROADCAST_IP = '255.255.255.255'
PORT = 37020                # Port for sending the broadcast
RESPONSE_PORT = 37021       # Port for receiving the directed reply
SEND_INTERVAL_SECONDS = 5   # Interval between broadcasts     
ID = 1                      # Unique ID for this controller

# Motor setup to control a window
motor = Motor(forward=27, backward=22, enable=17, pwm=True)
# --- End Configuration ---

def receive_replies():
    """Listens for directed replies from all responders."""
    try:
        reply_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)    # Create UDP socket
        reply_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Allow address reuse
        reply_sock.bind(('0.0.0.0', RESPONSE_PORT))                      # Ready to receive on RESPONSE_PORT
        
        print(f"\n[Reply Listener] Listening for replies on port {RESPONSE_PORT}...")
        
        while True:
            data, addr = reply_sock.recvfrom(1024)  # waits for data
            sender_ip = addr[0]                     # Extract sender's IP address
            
            try:
                reply_json = data.decode('utf-8')   # Decode bytes to string
                reply_data = json.loads(reply_json) # Parse JSON
                
                # open motor if should_open is true, else close motor
                if reply_data.get('should_open'):
                    print("Motor forward")
                    motor.forward()
                    time.sleep(1.5)
                    motor.stop()
                    
                if not reply_data.get('should_open'):
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
    """
    Starts the listener and sends continuous JSON broadcasts.
    """
    
    # starts the reply listener thread
    listener_thread = threading.Thread(target=receive_replies)
    listener_thread.daemon = True # Daemon thread will exit when main program exits
    listener_thread.start()

    # Setup the broadcasting socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)   # Create UDP socket
    except socket.error as err:
        print(f"Error creating socket: {err}")
        sys.exit(1)

    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)    # Enable broadcasting
    
    print(f" Starting continuous JSON broadcast to {BROADCAST_IP}:{PORT}...")
    
    # Continuous boroadcast loop
    try:
        while True:
            payload_data = {
                "id": ID,
                "last_updated": time.time(),
                "message": "should i open?",
                "type": "window_controller"
            }
            
            json_string = json.dumps(payload_data)           # Serialize to JSON
            encoded_data = json_string.encode('utf-8')       # Encode to bytes
            
            # Send the data
            sock.sendto(encoded_data, (BROADCAST_IP, PORT))
            
            # Wait before sending the next broadcast
            time.sleep(SEND_INTERVAL_SECONDS) 
            
    except KeyboardInterrupt:
        print("\n\n Broadcast stopped by user (Ctrl+C).")
    except Exception as e:
        print(f"\n An error occurred during transmission: {e}")
    finally:
        sock.close()
        print("Sender socket closed. Exiting.")

send_continuous_broadcast()